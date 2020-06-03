from typing import Iterable, Optional, Sized, Tuple, TypeVar, Union

from attr import attrib, attrs, validators

from immutablecollections import (
    ImmutableSet,
    ImmutableSetMultiDict,
    immutableset,
    immutablesetmultidict,
)

from vistautils.preconditions import check_arg
from vistautils.range import ImmutableRangeMap, Range, immutablerangemap

from typing_extensions import Protocol


@attrs(frozen=True, slots=True, repr=False)  # pylint:disable=inherit-non-class
# Pylint disable due to https://github.com/PyCQA/pylint/issues/2472
class Span(Sized):
    """
    A range of character offsets.

    Inclusive of `start`, exclusive of `end`.

    You can test sub-span containment with the `in` operator: `Span(1,5) in Span(0, 6)`.
    For checking whether an offset lies in a span, use `contains_offset`
    """

    start: int = attrib(validator=validators.instance_of(int))
    end: int = attrib(validator=validators.instance_of(int))

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

    def intersection(self, other: "Span") -> Optional["Span"]:
        """
        Gets the intersection of two Spans if they overlap.
        """
        if self.overlaps(other):
            range_intersection = self.as_range().intersection(other.as_range())
            return Span(
                range_intersection.lower_endpoint, range_intersection.upper_endpoint + 1
            )
        else:
            return None

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

    @staticmethod
    def index(items: Iterable[T]) -> "HasSpanIndex[T]":
        """
        Creates a ``HasSpanIndex`` for the given items.
        """
        return _OverLappingHasSpanIndex(
            # mypy is confused
            immutablesetmultidict(((item.span, item) for item in items))  # type: ignore
        )

    @staticmethod
    def index_disjoint(items: Iterable[T]) -> "HasSpanIndex[T]":
        """
        Creates a ``DisjointHasSpanIndex`` for the given items that disallows overlapping spans.
        """
        return _DisjointHasSpanIndex(
            # mypy is confused
            ((item.span, item) for item in items)  # type: ignore
        )

    def get_exactly_matching(self, span: Span) -> Union[ImmutableSet[T], Optional[T]]:
        """
        Gets all items whose spans match `span` exactly.
        """

    def get_overlapping(self, span: Span) -> ImmutableSet[T]:
        """
        Gets all items whose spans overlap `span`.
        """

    def get_contained(self, span: Span) -> ImmutableSet[T]:
        """
        Get all items whose spans are contained in the given `span`.
        """

    def get_containing(self, span: Span) -> Union[ImmutableSet[T], Optional[T]]:
        """
        Get all items whose spans contain the given `span`.
        """


def _build_range_to_item_index(
    inp: Optional[Iterable[Tuple[Span, T]]]
) -> ImmutableRangeMap[int, T]:
    if inp is None:
        return immutablerangemap()
    return immutablerangemap((span.as_range(), item) for span, item in inp)


@attrs(frozen=True, slots=True)
class _DisjointHasSpanIndex(HasSpanIndex[T]):
    """A ``HasSpanIndex`` where all member spans are guaranteed to be disjoint (non-overlapping)."""

    _range_to_item_index: ImmutableRangeMap[int, T] = attrib(
        converter=_build_range_to_item_index
    )

    def get_exactly_matching(self, span: Span) -> Optional[T]:
        return self._range_to_item_index.rng_to_val.get(span.as_range())

    def get_overlapping(self, span: Span) -> ImmutableSet[T]:
        return immutableset(
            self._range_to_item_index.rng_to_val[rng]
            for rng in self._range_to_item_index.range_set.ranges_overlapping(
                span.as_range()
            )
        )

    def get_contained(self, span: Span) -> ImmutableSet[T]:
        return self._range_to_item_index.get_enclosed_by(span.as_range())

    def get_containing(self, span: Span) -> Optional[T]:
        rng = span.as_range()
        if (
            self._range_to_item_index[rng.lower_endpoint]
            == self._range_to_item_index[rng.upper_endpoint]
        ):
            return self._range_to_item_index[rng.lower_endpoint]
        return None


@attrs(frozen=True, slots=True)
class _OverLappingHasSpanIndex(HasSpanIndex[T]):
    """
    An implementation of ``HasSpanIndex`` for items whose spans may overlap.
    """

    _span_to_item_index: ImmutableSetMultiDict[Span, T] = attrib(
        converter=immutablesetmultidict, default=immutablesetmultidict()  # type: ignore
    )

    def get_exactly_matching(self, span: Span) -> ImmutableSet[T]:
        return self._span_to_item_index[span]

    def get_overlapping(self, span: Span) -> ImmutableSet[T]:
        return immutableset(
            item
            for candidate_span in self._span_to_item_index
            for item in self._span_to_item_index[candidate_span]
            if candidate_span.overlaps(span)
        )

    def get_contained(self, span: Span) -> ImmutableSet[T]:
        return immutableset(
            item
            for candidate_span in self._span_to_item_index
            for item in self._span_to_item_index[candidate_span]
            if span.contains_span(candidate_span)
        )

    def get_containing(self, span: Span) -> ImmutableSet[T]:
        return immutableset(
            item
            for candidate_span in self._span_to_item_index
            for item in self._span_to_item_index[candidate_span]
            if candidate_span.contains_span(span)
        )
