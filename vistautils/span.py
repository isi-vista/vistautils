from typing import Iterable, Optional, Sized, Tuple, TypeVar
from typing_extensions import Protocol

from attr import attrs, attrib
from immutablecollections import (
    ImmutableSet,
    ImmutableSetMultiDict,
    immutablesetmultidict,
)

from vistautils.attrutils import attrib_instance_of
from vistautils.preconditions import check_arg
from vistautils.range import Range


@attrs(frozen=True, slots=True, repr=False)
class Span(Sized):
    """
    A range of character offsets.

    Inclusive of `start`, exclusive of `end`.

    You can test sub-span containment with the `in` operator: `Span(1,5) in Span(0, 6)`.
    For checking whether an offset lies in a span, use `contains_offset`
    """

    start: int = attrib_instance_of(int)
    end: int = attrib_instance_of(int)

    # noinspection PyUnusedLocal
    @start.validator
    def _validate_start(self, attr, val):  # pylint:disable=unused-argument
        check_arg(
            self.start < self.end,
            "Start offset must be strictly less then end offset but " "got [%s,%s)",
            (self.start, self.end),
        )

    @staticmethod
    def from_inclusive_to_exclusive(start_inclusive: int, end_exclusive: int) -> "Span":
        """
        Same as the constructor.

        But the more explicit name increases readability and reduces off-by-one errors.
        """
        return Span(start_inclusive, end_exclusive)

    def contains_offset(self, i: int) -> bool:
        return self.start <= i < self.end

    def contains_span(self, other: "Span") -> bool:
        return self.start <= other.start and other.end <= self.end

    def precedes(self, other: "Span") -> bool:
        """
        Get whether this span precedes another.

        To be judged as preceding, this span must end before other begins.
        """
        return self.end <= other.start

    def follows(self, other: "Span") -> bool:
        """
        Get whether this span follows another.

        To be judged as following, this span must start after the other ends.
        """
        return self.start >= other.end

    def overlaps(self, other: "Span") -> bool:
        """
        Get whether this span overlaps another.

        Two spans overlap if at least one offset position is in
        both of them.
        """
        # if they don't overlap, one must precede the other
        return not (self.precedes(other) or other.precedes(self))

    def as_range(self) -> Range[int]:
        return Range.closed(self.start, self.end - 1)

    def __contains__(self, item: "Span") -> bool:
        return self.contains_span(item)

    def __len__(self) -> int:
        return self.end - self.start

    def clip_to(self, enclosing: "Span") -> Optional["Span"]:
        """
        Get a copy of this span clipped to be entirely enclosed by another span.

        If this span lies entirely outside `enclosing`, then
        `None` is returned.
        """
        if not enclosing.overlaps(self):
            return None
        if enclosing.contains_span(self):
            return self
        return Span(max(self.start, enclosing.start), min(self.end, enclosing.end))

    def shift(self, shift_amount: int) -> "Span":
        """
        Get a copy of this span with both endpoints shifted.

        Negative values shift the span to the left, positive to the right.
        """
        return Span(self.start + shift_amount, self.end + shift_amount)

    @staticmethod
    def minimal_enclosing_span(spans: Iterable["Span"]) -> "Span":
        """
        Get the minimal span enclosing all given spans.

        This will raise a `ValueError` if `spans` is empty.
        """
        return Span(min(span.start for span in spans), max(span.end for span in spans))

    @staticmethod
    def earliest_then_longest_first_key(x: "Span") -> Tuple[int, int]:
        length = x.end - x.start
        return x.start, -length

    def __repr__(self):
        return "[%s:%s)" % (self.start, self.end)


class HasSpan(Protocol):
    __slots__: tuple = ()
    span: Span

    @property
    def start(self) -> int:
        return self.span.start

    @property
    def end(self) -> int:
        return self.span.end

    def contains_offset(self, i) -> bool:
        return self.span.contains_offset(i)

    def contains_span(self, other) -> bool:
        return self.span.contains_span(other)


T = TypeVar("T", bound=HasSpan)


class HasSpanIndex(Protocol[T]):
    """
    Support efficient lookup of items with spans.
    """

    def exactly_matching(self, span: Span) -> ImmutableSet[T]:
        """
        Gets all contained items whose spans match *span* exactly.
        """

    @staticmethod
    def index(items: Iterable[T]) -> "HasSpanIndex[T]":
        """
        Creates a ``HasSpanIndex`` for the given items.
        """
        return _OverLappingHasSpanIndex(
            immutablesetmultidict(((item.span, item) for item in items))
        )


@attrs(frozen=True, slots=True)
class _OverLappingHasSpanIndex(HasSpanIndex[T]):
    """
    An implementation of ``HasSpanIndex`` for items whose spans may overlap.
    """

    _span_to_item_index: ImmutableSetMultiDict[Span, T] = attrib(
        converter=immutablesetmultidict, default=immutablesetmultidict()  # type: ignore
    )

    def exactly_matching(self, span: Span) -> ImmutableSet[T]:
        return self._span_to_item_index[span]
