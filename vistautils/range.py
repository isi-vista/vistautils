# really needs to be totally-ordered
from abc import ABCMeta, abstractmethod
from datetime import date
from typing import (
    Any,
    Container,
    Generic,
    Hashable,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Sized,
    Tuple,
    TypeVar,
    Union,
)

from attr import attrib, attrs, validators

from immutablecollections import ImmutableDict, ImmutableSet, immutabledict, immutableset

# Port of Guava's Range data type and associated classes
from vistautils.preconditions import check_arg, check_not_none

import deprecation
from sortedcontainers import SortedDict

# will be initialized after bound type declarations
# noinspection PyTypeHints
_OPEN: "BoundType" = None  # type:ignore
# noinspection PyTypeHints
_CLOSED: "BoundType" = None  # type:ignore


class BoundType:
    """
    A possible type of boundary for a range.

    A boundary is either closed, meaning it includes its endpoint, or open, meaning it does not.
    """

    __slots__ = ()

    @staticmethod
    def open() -> "BoundType":
        return _OPEN

    @staticmethod
    def closed() -> "BoundType":
        return _CLOSED

    def flip(self):
        return _CLOSED if self is _OPEN else _OPEN


class _Open(BoundType):
    __slots__ = ()


class _Closed(BoundType):
    __slots__ = ()


# noinspection PyRedeclaration,PyTypeHints
_OPEN: BoundType = _Open()  # type: ignore
# noinspection PyRedeclaration,PyTypeHints
_CLOSED: BoundType = _Closed()  # type: ignore

# these need to be initialized after declaration of _Cut
# noinspection PyTypeHints
_BELOW_ALL: "_Cut" = None  # type:ignore
# noinspection PyTypeHints
_ABOVE_ALL: "_Cut" = None  # type:ignore

# T needs to be comparable, but Python typing seems to lack a way to specify this?
# see https://github.com/python/mypy/issues/500
# we track this with our own issue #201
T = TypeVar("T")


class _Cut(Generic[T], metaclass=ABCMeta):
    """
    Implementation detail for the internal structure of Range instances.

    Represents a unique way of "cutting" a "number line" into two sections; this can be done below
    a certain value, above a certain value, below all values or above all values.
    With this  object defined in this way, an interval can always be represented by a pair of
    Cut instances.

    This is a Python port of Guava code originally written by Kevin Bourrillion.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def endpoint(self) -> T:
        raise NotImplementedError()

    @abstractmethod
    def is_less_than(self, other: T) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def as_upper_bound(self) -> BoundType:
        raise NotImplementedError()

    @abstractmethod
    def as_lower_bound(self) -> BoundType:
        raise NotImplementedError()

    @abstractmethod
    def describe_as_lower_bound(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def describe_as_upper_bound(self) -> str:
        raise NotImplementedError()

    def compare_to(self, other: "_Cut[T]") -> int:
        # overridden by BelowAll, AboveAll
        if other is _BELOW_ALL:
            return 1
        if other is _ABOVE_ALL:
            return -1
        if self.endpoint < other.endpoint:  # type: ignore
            return -1
        elif other.endpoint < self.endpoint:  # type: ignore
            return 1
        else:
            # BelowValue precedes AboveValue
            if isinstance(self, _AboveValue):
                if isinstance(other, _AboveValue):
                    return 0
                else:
                    return 1
            else:
                if isinstance(other, _AboveValue):
                    return -1
                else:
                    return 0

    # cannot use @totalordering because we want to compare across sub-classes
    # so we need to spell out all the operators
    def __lt__(self, other) -> bool:
        return self.compare_to(other) < 0

    def __le__(self, other) -> bool:
        return self.compare_to(other) <= 0

    def __gt__(self, other) -> bool:
        return self.compare_to(other) > 0

    def __ge__(self, other) -> bool:
        return self.compare_to(other) >= 0

    def __eq__(self, other) -> bool:
        return self.compare_to(other) == 0


@attrs(frozen=True, slots=True, hash=False, eq=False)
class _BelowAll(_Cut[T]):
    # pylint:disable=protected-access
    @property
    def endpoint(self) -> T:
        raise ValueError("BelowAll cut lacks an endpoint")

    def is_less_than(self, other: T) -> bool:  # pylint:disable=unused-argument
        return True

    def as_upper_bound(self) -> BoundType:
        raise AssertionError("Should never be called")

    def as_lower_bound(self) -> BoundType:
        raise AssertionError("Should never be called")

    def describe_as_lower_bound(self) -> str:
        return "(-\u221e"  # Returns ( and a negative infinity

    def describe_as_upper_bound(self) -> str:
        raise AssertionError("Can't happen")

    def compare_to(self, other: "_Cut[T]") -> int:
        # we assume only the constant _BELOW_ALL is ever instantiated
        if other is self:
            return 0
        return -1

    def __hash__(self):
        # some arbitrary number
        return 233904909


@attrs(frozen=True, slots=True, hash=False, eq=False)
class _AboveAll(_Cut[T]):
    # pylint:disable=protected-access
    @property
    def endpoint(self) -> T:
        raise ValueError("AboveAll cut lacks an endpoint")

    def is_less_than(self, other: T) -> bool:  # pylint:disable=unused-argument
        return False

    def as_upper_bound(self) -> BoundType:
        raise AssertionError("Should never be called")

    def as_lower_bound(self) -> BoundType:
        raise AssertionError("Should never be called")

    def describe_as_lower_bound(self) -> str:
        raise AssertionError("Can't happen")

    def describe_as_upper_bound(self) -> str:
        return "+\u221e)"  # Returns positive infinity and )

    def compare_to(self, other: "_Cut[T]") -> int:
        # we assume only the constant _ABOVE_ALL is ever instantiated
        if other is self:
            return 0
        return 1

    def __hash__(self):
        # some arbitrary number
        return 9989388


# noinspection PyRedeclaration
_BELOW_ALL = _BelowAll()
# noinspection PyRedeclaration
_ABOVE_ALL = _AboveAll()


@attrs(frozen=True, slots=True, repr=False, hash=False, eq=False)
class _BelowValue(_Cut[T]):
    # pylint:disable=protected-access
    _endpoint = attrib()

    @property
    def endpoint(self) -> T:
        return self._endpoint

    def is_less_than(self, other: T) -> bool:
        return self._endpoint < other or self._endpoint == other

    def as_upper_bound(self) -> BoundType:
        return _OPEN

    def as_lower_bound(self) -> BoundType:
        return _CLOSED

    def __hash__(self):
        return hash(self._endpoint)

    def __eq__(self, other):
        if isinstance(other, _BelowValue):
            return self._endpoint == other._endpoint
        return False

    def describe_as_lower_bound(self) -> str:
        return "[%s" % self._endpoint

    def describe_as_upper_bound(self) -> str:
        return "%s)" % self._endpoint

    def __repr__(self) -> str:
        return "\\\\%s/" % self._endpoint


@attrs(frozen=True, slots=True, repr=False, hash=False, eq=False)
class _AboveValue(_Cut[T]):
    # pylint:disable=protected-access
    _endpoint = attrib()

    @property
    def endpoint(self) -> T:
        return self._endpoint

    def is_less_than(self, other: T) -> bool:
        return self._endpoint < other

    def as_upper_bound(self) -> BoundType:
        return _CLOSED

    def as_lower_bound(self) -> BoundType:
        return _OPEN

    def __hash__(self):
        # bitwise complement to distinguish it from the corresponding _BelowValue
        return ~hash(self._endpoint)

    def __eq__(self, other):
        if isinstance(other, _AboveValue):
            return self._endpoint == other._endpoint
        return False

    def describe_as_lower_bound(self) -> str:
        return "(%s" % self._endpoint

    def describe_as_upper_bound(self) -> str:
        return "%s]" % self._endpoint

    def __repr__(self) -> str:
        return "/%s\\\\" % self._endpoint


# must initialize after declaring Range
# noinspection PyTypeHints
RANGE_ALL: "Range" = None  # type: ignore


# this should have slots=True but cannot for the moment due to
# https://github.com/python-attrs/attrs/issues/313
# Pylint disable due to https://github.com/PyCQA/pylint/issues/2472
@attrs(frozen=True, repr=False, eq=False, hash=False)  # pylint: disable=inherit-non-class
class Range(Container[T], Generic[T], Hashable):
    """
    The boundaries of a contiguous span of values.

    The value must be of some type which implements `<` in a way consistent with `__eq__`.
    Note this does not provide a means of iterating over these values.

    Each end of the `Range` may be *bounded* or *unbounded*. If bounded, there is an associated
     *endpoint* value and the range is considered either *open* (does not include the endpoint
     value) or *closed* (does include the endpoint value).  With three possibilities on each
     side, this yields nine basic types of ranges, enumerated belows.
     (Notation: a square bracket (`[ ]`) indicates that the range is closed on that side;
     a parenthesis (`( )`) means it is either open or unbounded. The construct `{x | statement}`
      is read "the set of all x such that statement.")

    ========        ==========            ==============
    Notation	    Definition	          Factory method
    ========        ==========            ==============
    `(a..b)`	    `{x | a < x < b}`	      open
    `[a..b]`	    `{x | a <= x <= b}`	      closed
    `(a..b]`	    `{x | a < x <= b}`	      open_closed
    `[a..b)`	    `{x | a <= x < b}`	      closed_open
    `(a..+∞)`	    `{x | x > a}`	          greater_than
    `[a..+∞)`	    `{x | x >= a}`	          at_least
    `(-∞..b)`	    `{x | x < b}`	          less_than
    `(-∞..b]`	    `{x | x <= b}`	          at_most
    `(-∞..+∞)`	    `{x}`	                  all
    =========       ===========           ==============

    When both endpoints exist, the upper endpoint may not be less than the lower. The endpoints may
     be equal only if at least one of the bounds is closed:

     * `[a..a]` : a singleton range
     * `[a..a)`; `(a..a]` : empty ranges; also valid
     * `(a..a)` : invalid; an exception will be thrown

    ========
    Warnings
    ========

    * Use immutable value types only, if at all possible. If you must use a mutable type, do not
    allow the endpoint instances to mutate after the range is created!

    =======
    Notes
    ========
    * Instances of this type are obtained using the static factory methods in this class.
    * Ranges are convex: whenever two values are contained, all values in between them must also be
         contained. More formally, for any `c1 <= c2 <= c3` of type `C`,
         `c1 in r and c3 in r` implies `c2 in r`. This means that a `Range[int]` can never
         be used to represent, say, "all prime numbers from 1 to 100."
    * Terminology note: a range `a` is said to be the maximal range having property `P` if,
    for all ranges `b` also having property `P`, `a.encloses(b)`. Likewise, `a` is minimal when
    `b.encloses(a)` for all `b` having property `P`. See, for example, the definition of
    intersection.

    This class (including the documentation) is an almost direct translation of Guava's Range,
    which was originally authored by Kevin Bourrillion and Gregory Kick.
    """

    # pylint:disable=protected-access
    _lower_bound: _Cut[T] = attrib(validator=validators.instance_of(_Cut))
    _upper_bound: _Cut[T] = attrib(validator=validators.instance_of(_Cut))

    def __attrs_post_init__(self):
        check_arg(
            self._lower_bound <= self._upper_bound,
            "Upper bound of a range cannot be less than lower bound but got %s ",
            (self,),
        )
        check_arg(self._lower_bound is not _ABOVE_ALL)
        check_arg(self._upper_bound is not _BELOW_ALL)

    @staticmethod
    def open(lower: T, upper: T) -> "Range[T]":
        return Range(_AboveValue(lower), _BelowValue(upper))

    @staticmethod
    def closed(lower: T, upper: T) -> "Range[T]":
        return Range(_BelowValue(lower), _AboveValue(upper))

    @staticmethod
    def closed_open(lower: T, upper: T) -> "Range[T]":
        return Range(_BelowValue(lower), _BelowValue(upper))

    @staticmethod
    def open_closed(lower: T, upper: T) -> "Range[T]":
        return Range(_AboveValue(lower), _AboveValue(upper))

    @staticmethod
    def less_than(upper: T) -> "Range[T]":
        return Range(_BELOW_ALL, _BelowValue(upper))

    @staticmethod
    def at_most(upper: T) -> "Range[T]":
        return Range(_BELOW_ALL, _AboveValue(upper))

    @staticmethod
    def greater_than(lower: T) -> "Range[T]":
        return Range(_AboveValue(lower), _ABOVE_ALL)

    @staticmethod
    def at_least(lower: T) -> "Range[T]":
        return Range(_BelowValue(lower), _ABOVE_ALL)

    @staticmethod
    def all() -> "Range[T]":
        return RANGE_ALL

    @staticmethod
    def create_spanning(ranges: Sequence["Range[T]"]):
        if not ranges:
            raise ValueError("Cannot create range from span of empty range collection")
        return Range(
            min(x._lower_bound for x in ranges), max(x._upper_bound for x in ranges)
        )

    def has_lower_bound(self) -> bool:
        return self._lower_bound is not _BELOW_ALL

    def has_upper_bound(self) -> bool:
        return self._upper_bound is not _ABOVE_ALL

    @property
    def lower_bound_type(self) -> BoundType:
        return self._lower_bound.as_lower_bound()

    @property
    def upper_bound_type(self) -> BoundType:
        return self._upper_bound.as_upper_bound()

    @property
    def lower_endpoint(self) -> T:
        return self._lower_bound.endpoint

    @property
    def upper_endpoint(self) -> T:
        return self._upper_bound.endpoint

    def is_empty(self) -> bool:
        """
        Determine if a range is empty.

        Returns `True` if this range is of the form `[v..v)` or `(v..v]`.
        (This does not encompass ranges of the form (v..v), because such ranges are invalid and
        can't be constructed at all.)

        Note that certain discrete ranges such as the integer range (3..4) are not considered empty,
         even though they contain no actual values.
        """
        return self._lower_bound == self._upper_bound

    # I don't know why mypy complains about narrowing the type, which seems a reasonable thing to do
    def __contains__(self, val: T) -> bool:  # type: ignore
        check_not_none(val)
        return self._lower_bound.is_less_than(val) and not self._upper_bound.is_less_than(
            val
        )

    def encloses(self, other: "Range[T]") -> bool:
        # noinspection PyChainedComparisons
        return (
            self._lower_bound.compare_to(other._lower_bound) <= 0
            and self._upper_bound.compare_to(other._upper_bound) >= 0
        )

    def is_connected(self, other: "Range[T]") -> bool:
        """
        Determine if two ranges are connected.

        Returns `True` if there exists a (possibly empty) range which is enclosed by both this
        range and `other`. For example,

        * `[2, 4)` and `[5, 7)` are not connected
        * `[2, 4)` and `[3, 5)` are connected, because both enclose `[3, 4)`
        * `[2, 4)` and `[4, 6)` are connected, because both enclose the empty range `[4, 4)`

        Note that this range and `other` have a well-defined union and intersection (as a
        single, possibly-empty range) if and only if this method returns `True`.

        The connectedness relation is both reflexive and symmetric, but does not form an
        equivalence relation as it is not transitive.

        Note that certain discrete ranges are not considered connected, even though there are
        no elements "between them." For example, `[3, 5]` is not considered connected to
        `[6, 10]`.
        """
        return (
            self._lower_bound <= other._upper_bound
            and other._lower_bound <= self._upper_bound
        )

    def span(self, other: "Range[T]") -> "Range[T]":
        """
        Get the minimal range enclosing both this range and `other`.

         For example, the span of `[ 1..3] and (5..7)` is `[1..7)`.
        If the input ranges are connected, the returned range can also be called their union.
        If they are not, note that the span might contain values that are not contained in either
        input range.

        Like intersection, this operation is commutative, associative and idempotent. Unlike it, it
        is always well-defined for any two input ranges.
        """
        lower_cmp = self._lower_bound.compare_to(other._lower_bound)
        upper_cmp = self._upper_bound.compare_to(other._upper_bound)

        if lower_cmp <= 0 and upper_cmp >= 0:
            return self
        elif lower_cmp >= 0 and upper_cmp <= 0:
            return other
        else:
            return Range(
                self._lower_bound if lower_cmp <= 0 else other._lower_bound,
                self._upper_bound if upper_cmp >= 0 else other._upper_bound,
            )

    def intersection(self, connected_range: "Range[T]") -> "Range[T]":
        """
        Get the intersection of this range and `other`.

        Returns the maximal range enclosed by both this range and connectedRange, if such a
        range exists.

        For example, the intersection of `[1..5]` and `(3..7)` is `(3..5]`. The
        resulting range may be empty; for example, `[1..5)` intersected with `[5..7)`
        yields the empty range `[5..5)`.

        The intersection exists if and only if the two ranges are connected.  This method throws
        a `ValueError` is `connected_range` is not in fact connected.

        The intersection operation is commutative, associative and idempotent, and its identity
        element is the `all` range/
        """
        lower_cmp = self._lower_bound.compare_to(connected_range._lower_bound)
        upper_cmp = self._upper_bound.compare_to(connected_range._upper_bound)
        if lower_cmp >= 0 >= upper_cmp:
            return self
        elif lower_cmp <= 0 <= upper_cmp:
            return connected_range
        else:
            return Range(
                self._lower_bound if lower_cmp >= 0 else connected_range._lower_bound,
                self._upper_bound if upper_cmp <= 0 else connected_range._upper_bound,
            )

    def intersects(self, other_range: "Range[T]") -> bool:
        """
        Determine if this range i
        Args:
            other_range:

        Returns:

        """
        lower_cmp = self._lower_bound.compare_to(other_range._lower_bound)
        upper_cmp = self._upper_bound.compare_to(other_range._upper_bound)
        if lower_cmp >= 0 >= upper_cmp:
            return True
        elif lower_cmp <= 0 <= upper_cmp:
            return True
        else:
            intersection_lb = (
                self._lower_bound if lower_cmp >= 0 else other_range._lower_bound
            )
            intersection_ub = (
                self._upper_bound if upper_cmp <= 0 else other_range._upper_bound
            )
            return intersection_lb <= intersection_ub

    def __eq__(self, other) -> bool:
        if isinstance(other, Range):
            return (
                self._lower_bound == other._lower_bound
                and self._upper_bound == other._upper_bound
            )
        return False

    def __hash__(self) -> int:
        return hash(self._lower_bound) + 31 * hash(self._upper_bound)

    def __repr__(self) -> str:
        return (
            self._lower_bound.describe_as_lower_bound()
            + ".."
            + self._upper_bound.describe_as_upper_bound()
        )


# noinspection PyRedeclaration
RANGE_ALL = Range(_BELOW_ALL, _ABOVE_ALL)


# Pylint disable due to https://github.com/PyCQA/pylint/issues/2472
class RangeSet(
    Generic[T], Container[T], Sized, metaclass=ABCMeta
):  # pylint:disable=E0239
    """
    A set comprising zero or more nonempty, disconnected ranges of type `T`.

    Implementations that choose to support the `add(Range)` operation are required to ignore empty
    ranges and coalesce connected ranges. For example ::

         rangeSet: RangeSet[int] = TreeRangeSet();`
         rangeSet.add(Range.closed(1, 10)); // {[1, 10]}
         rangeSet.add(Range.closed_open(11, 15)); // disconnected range; {[1, 10], [11, 15)}
         rangeSet.add(Range.closed_open(15, 20)); // connected range; {[1, 10], [11, 20)}
         rangeSet.add(Range.open_closed(0, 0)); // empty range; {[1, 10], [11, 20)}
         rangeSet.remove(Range.open(5, 10)); // splits [1, 10]; {[1, 5], [10, 10], [11, 20)}


    Note that the behavior of `Range.isEmpty()` and `Range.isConnected(Range)` may not be as
    expected on discrete ranges. See the documentation of those methods for details.

    This (including the documentation) is a partial translation of Guava's RangeSet to Python.
    Guava's implementation was written by Kevin Bourrillion and Louis Wasserman.
    """

    __slots__ = ()

    @staticmethod
    def create_mutable() -> "MutableRangeSet[T]":
        return _MutableSortedDictRangeSet.create()

    @abstractmethod
    def __contains__(self, value: T) -> bool:  # type: ignore
        """
        Determine whether any of this range set's member ranges contains `value`.
        """
        raise NotImplementedError()

    @abstractmethod
    def encloses(self, rng: Range[T]) -> bool:
        """
        Check if any member range encloses `rng`
        """
        raise NotImplementedError()

    def encloses_all(self, rngs: Union["RangeSet[T]", Iterable[Range[T]]]) -> bool:
        """
        For each input range, check if any member range encloses it.
        """
        if isinstance(rngs, RangeSet):
            return self.encloses_all(rngs.as_ranges())
        for rng in rngs:
            if not self.encloses(rng):
                return False
        return True

    @abstractmethod
    def intersects(self, rng: Range[T]) -> bool:
        """
        Get whether any ranges in this set intersects `rng`

        Returns `True` if there exists a non-empty range enclosed by both a member range in
        this range set and the specified range.
        """
        raise NotImplementedError()

    @abstractmethod
    def ranges_overlapping(self, rng: Range[T]) -> ImmutableSet[Range[T]]:
        """
        Get all ranges in this set that overlap (have an intersection) with `rng`.

        Unlike Guava's `intersectRanges`, this does not truncate partially intersecting ranges to
        just the intersecting portion.
        """
        raise NotImplementedError()

    @abstractmethod
    def range_containing(self, value: T) -> Optional[Range[T]]:
        raise NotImplementedError()

    @abstractmethod
    def range_enclosing_range(self, value: Range[T]) -> Optional[Range[T]]:
        raise NotImplementedError()

    @abstractmethod
    def ranges_enclosed_by(self, rng) -> ImmutableSet[Range[T]]:
        raise NotImplementedError()

    @abstractmethod
    def rightmost_containing_or_below(self, upper_limit: T) -> Optional[Range[T]]:
        """
        Get the rightmost range in this set whose lower bound does not exceed *upper_limit*.

        Formally, this is the range `(x, y)` with minimal `y` such that `(upper_limit, +inf)`
        does not contain `(x, y)`.

        If there is no such set, `None` is returned.

        For example::

         range_set: RangeSet[int] = immutablerangeset([
             Range.open_closed(1, 10)
             Range.open(12, 15)
         ])

         // range_set: {(1, 10], (12, 15)}
         range_set.rightmost_containing_or_below(3)  // returns (1, 10]
         range_set.rightmost_containing_or_below(11) // returns (1, 10]
         range_set.rightmost_containing_or_below(12) // returns (1, 10]
         range_set.rightmost_containing_or_below(13) // returns (12, 15)
         range_set.rightmost_containing_or_below(15) // returns (12, 15)
         range_set.rightmost_containing_or_below(1)  // returns None
        """

    @abstractmethod
    def leftmost_containing_or_above(self, lower_limit: T) -> Optional[Range[T]]:
        """
        Get the leftmost range in this set whose upper bound is not below *lower_limit*.

        Formally, this is the range `(x, y)` with maximal `x` such that `(-inf, lower_limit)`
        does not contain `(x, y)`.

        If there is no such set, `None` is returned.

        For example::

         range_set: RangeSet[int] = immutablerangeset([
             Range.open(1, 10)
             Range.open_closed(12, 15)
         ])

         // range_set: {(1, 10), (12, 15]}
         range_set.leftmost_containing_or_above(1)  // returns (1, 10)
         range_set.leftmost_containing_or_above(3)  // returns (1, 10)
         range_set.leftmost_containing_or_above(10) // returns (12, 15]
         range_set.leftmost_containing_or_above(11) // returns (12, 15]
         range_set.leftmost_containing_or_above(12) // returns (12, 15]
         range_set.leftmost_containing_or_above(13) // returns (12, 15]
         range_set.leftmost_containing_or_above(15) // returns (12, 15]
         range_set.leftmost_containing_or_above(16) // returns None
        """

    @deprecation.deprecated(
        deprecated_in="0.19.0",
        removed_in=date(2020, 8, 10),
        details="Deprecated, use rightmost_containing_or_below(upper_limit). "
        "This method may be removed in a future release.",
    )
    def maximal_containing_or_below(self, upper_limit: T) -> Optional[Range[T]]:
        return self.rightmost_containing_or_below(upper_limit)

    @deprecation.deprecated(
        deprecated_in="0.19.0",
        removed_in=date(2020, 8, 10),
        details="Deprecated, use leftmost_containing_or_above(upper_limit). "
        "This method may be removed in a future release.",
    )
    def minimal_containing_or_above(self, lower_limit: T) -> Optional[Range[T]]:
        return self.leftmost_containing_or_above(lower_limit)

    @abstractmethod
    def as_ranges(self) -> Sequence[Range[T]]:
        raise NotImplementedError()

    def __eq__(self, other) -> bool:
        if isinstance(other, RangeSet):
            return ImmutableSet.of(self.as_ranges()) == ImmutableSet.of(other.as_ranges())
        else:
            return False

    def __hash__(self) -> int:
        return hash(self.as_ranges())

    @abstractmethod
    def is_empty(self) -> bool:
        """
        Determine if this range set has no ranges.
        """
        raise NotImplementedError()

    @property
    @abstractmethod
    def span(self) -> Range[T]:
        """
        The minimal range which encloses all ranges in this range set.
        """
        raise NotImplementedError()

    def __repr__(self):
        return self.__class__.__name__ + "(" + str(self.as_ranges()) + ")"

    def __getstate__(self) -> Tuple[Range[T], ...]:
        if self.is_empty():
            return ()
        return tuple(self.as_ranges())

    @abstractmethod
    def __setstate__(self, state: Iterable[Range[T]]) -> None:
        raise NotImplementedError()


T2 = TypeVar("T2")


class ImmutableRangeSet(RangeSet[T], metaclass=ABCMeta):
    """
    A RangeSet which cannot be modified.

    If you reach into its guts and modify it, its behavior is undefined.
    """

    @staticmethod
    def builder() -> "ImmutableRangeSet.Builder[T]":
        return _ImmutableSortedDictRangeSet.Builder()

    class Builder(Generic[T2], metaclass=ABCMeta):
        @abstractmethod
        def add(self, rng: Range[T2]) -> "ImmutableRangeSet.Builder[T2]":
            raise NotImplementedError()

        def add_all(self, ranges: Iterable[Range[T2]]) -> "ImmutableRangeSet.Builder[T2]":
            for rng in ranges:
                self.add(rng)
            return self

        @abstractmethod
        def build(self) -> "ImmutableRangeSet[T2]":
            raise NotImplementedError()


class MutableRangeSet(RangeSet[T], metaclass=ABCMeta):
    __slots__ = ()

    def add(self, rng: Range[T]) -> "MutableRangeSet[T]":
        """
        Add the specified range to this RangeSet (optional operation).

         For equal range sets `a` and `b`, the result of `a.add(range)` is that `a` will be the
         minimal range set for which both `a.encloses_all(b)` and `a.encloses(range)`.

        Note that `range` will be coalesced with any ranges in the range set that are connected
         with it. Moreover, if range is empty, this is a no-op.

        Returns the RangeSet itself to facilitate chaining operations, especially in tests.
         """
        raise NotImplementedError()

    def add_all(
        self, rngs: Union["RangeSet[T]", Iterable[Range[T]]]
    ) -> "MutableRangeSet[T]":
        """
        Add all the specified ranges to this RangeSet (optional operation).

        Returns the RangeSet itself to facilitate chaining operations, especially in tests.
        """
        if isinstance(rngs, RangeSet):
            return self.add_all(rngs.as_ranges())
        for rng in rngs:
            self.add(rng)
        return self

    def clear(self) -> None:
        """
        Remove all ranges from this RangeSet (optional operation).

        After this operation, `c in this_range_set` will return `False` for all `c`.

        This is equivalent to `remove(Range.all())`.
        """
        raise NotImplementedError()

    def remove(self, rng: Range[T]) -> "MutableRangeSet[T]":
        """
        Remove the specified range from this RangeSet (optional operation).

        After this operation, if `rng.contains(c)`, `self.contains(c)` will return `False`.
        If `rng` is empty, this is a no-op.

        Returns the RangeSet itself to facilitate chaining operations, especially in tests.
        """
        raise NotImplementedError()

    def remove_all(
        self, rngs: Union["RangeSet[T]", Iterable[Range[T]]]
    ) -> "MutableRangeSet[T]":
        """
        Remove each specified range.

        Returns the RangeSet itself to facilitate chaining operations, especially in tests.
        """
        if isinstance(rngs, RangeSet):
            return self.remove_all(rngs.as_ranges())
        for rng in rngs:
            self.remove(rng)
        return self


# noinspection PyProtectedMember
class _SortedDictRangeSet(RangeSet[T], metaclass=ABCMeta):
    # pylint:disable=protected-access

    def __init__(self, ranges_by_lower_bound: SortedDict) -> None:
        # we store the ranges as a map sorted by their lower bound
        # Note that because we enforce that there are no overlapping or connected ranges,
        # this sorts the ranges by upper bound as well
        self._ranges_by_lower_bound = ranges_by_lower_bound

    def range_containing(self, value: T) -> Optional[Range[T]]:
        highest_range_beginning_at_or_below = _value_at_or_below(
            self._ranges_by_lower_bound, _BelowValue(value)
        )
        if highest_range_beginning_at_or_below:
            if value in highest_range_beginning_at_or_below:
                return highest_range_beginning_at_or_below
        return None

    def range_enclosing_range(self, rng: Range[T]) -> Optional[Range[T]]:
        # this implementation can be sped up
        highest_range_beginning_at_or_below = _value_at_or_below(
            self._ranges_by_lower_bound, rng._lower_bound
        )
        if (
            highest_range_beginning_at_or_below
            and highest_range_beginning_at_or_below.encloses(rng)
        ):
            return highest_range_beginning_at_or_below
        return None

    def ranges_enclosed_by(self, query_rng: Range[T]) -> ImmutableSet[Range[T]]:
        highest_range_at_or_above = _value_at_or_above(
            self._ranges_by_lower_bound, query_rng._lower_bound
        )
        if highest_range_at_or_above:
            start_idx = self._ranges_by_lower_bound.index(
                highest_range_at_or_above._lower_bound
            )
            ret: ImmutableSet.Builder[Range[T]] = ImmutableSet.builder()
            for idx in range(start_idx, len(self._ranges_by_lower_bound)):
                rng_at_idx = self._ranges_by_lower_bound.values()[idx]
                if query_rng.encloses(rng_at_idx):
                    ret.add(rng_at_idx)
                else:
                    break
            return ret.build()
        else:
            return immutableset()

    # noinspection PyTypeHints
    def __contains__(self, value: T) -> bool:  # type: ignore
        highest_range_beginning_at_or_below = _value_at_or_below(
            self._ranges_by_lower_bound, _BelowValue(value)
        )
        return bool(
            highest_range_beginning_at_or_below
            and value in highest_range_beginning_at_or_below
        )

    def encloses(self, rng: Range[T]) -> bool:
        highest_range_beginning_at_or_below = _value_at_or_below(
            self._ranges_by_lower_bound, rng._lower_bound
        )
        return bool(
            highest_range_beginning_at_or_below
            and highest_range_beginning_at_or_below.encloses(rng)
        )

    def intersects(self, rng: Range[T]) -> bool:
        check_not_none(rng)
        ceiling_range: Optional[Range[T]] = _value_at_or_above(
            self._ranges_by_lower_bound, rng._lower_bound
        )
        if (
            ceiling_range
            and ceiling_range.is_connected(rng)
            and not ceiling_range.intersection(rng).is_empty()
        ):
            return True
        # check strictness of lowerEntry
        lower_range: Optional[Range[T]] = _value_below(
            self._ranges_by_lower_bound, rng._lower_bound
        )
        return bool(
            lower_range
            and lower_range.is_connected(rng)
            and not lower_range.intersection(rng).is_empty()
        )

    def ranges_overlapping(self, rng: Range[T]) -> ImmutableSet[Range[T]]:
        check_not_none(rng)
        if self.is_empty():
            return immutableset()
        rlb = self._ranges_by_lower_bound
        from_index = rlb.bisect(rng._lower_bound)
        # If we would insert at the end (are greater than all the elements, the only range that
        # could possibly overlap is the last one.
        if from_index == len(rlb):
            last_range: Range[T] = rlb[rlb.keys()[-1]]
            if last_range.intersects(rng):
                return immutableset([last_range])
            return immutableset()
        to_index = rlb.bisect(rng._upper_bound)
        # If we would insert at the start (are smaller than all the elements, the only range that
        # could possibly overlap is the first one.
        if to_index == 0:
            first_range: Range[T] = rlb[rlb.keys()[0]]
            if first_range.intersects(rng):
                return immutableset([first_range])
            return immutableset()
        return immutableset(
            [
                rlb[rlb.keys()[index]]
                # The ranges at the extreme indices do not necessarily overlap,
                for index in range(
                    max(0, from_index - 1), to_index
                )  # range method is not inclusive
                # so this explicit check is needed.
                if rlb[rlb.keys()[index]].intersects(rng)
            ]
        )

    def rightmost_containing_or_below(self, upper_limit: T) -> Optional[Range[T]]:
        return _value_at_or_below(self._ranges_by_lower_bound, _BelowValue(upper_limit))

    def leftmost_containing_or_above(self, lower_limit: T) -> Optional[Range[T]]:
        sorted_dict = self._ranges_by_lower_bound
        # an AboveValue cut corresponds to a closed upper interval, which catches containment
        # as desired
        # I have no idea why mypy is asking for an explicit type assignment here
        limit_as_bound: _AboveValue = _AboveValue(lower_limit)

        # insertion index into the sorted list of sets
        idx = sorted_dict.bisect_left(limit_as_bound)
        # so the index of the "latest" set with a lower bound preceding lower_limit is back one
        containing_or_below_index = idx - 1

        if containing_or_below_index >= 0:
            # if such a set exists, we need to check if we are contained in it...
            latest_beginning_before = sorted_dict[
                sorted_dict.keys()[containing_or_below_index]
            ]
            if limit_as_bound <= latest_beginning_before._upper_bound:
                return latest_beginning_before

        if idx < len(sorted_dict):
            return sorted_dict[sorted_dict.keys()[idx]]
        else:
            return None

    def as_ranges(self) -> Sequence[Range[T]]:
        return self._ranges_by_lower_bound.values()

    def is_empty(self) -> bool:
        return len(self._ranges_by_lower_bound) == 0

    @property
    def span(self) -> Range[T]:
        if self.is_empty():
            raise ValueError("Can't take span of an empty RangeSet")
        return Range(
            self._ranges_by_lower_bound.values()[0]._lower_bound,
            self._ranges_by_lower_bound.values()[-1]._upper_bound,
        )

    def immutable_copy(self) -> ImmutableRangeSet[T]:
        return _ImmutableSortedDictRangeSet(self._ranges_by_lower_bound.copy())

    def __repr__(self):
        return repr(list(self.as_ranges()))

    def __len__(self) -> int:
        return len(self._ranges_by_lower_bound)

    def __setstate__(self, state: Iterable[Range[T]]) -> None:
        self._ranges_by_lower_bound = SortedDict(
            [(rng._lower_bound, rng) for rng in state]
        )


class _MutableSortedDictRangeSet(_SortedDictRangeSet[T], MutableRangeSet[T]):
    # pylint:disable=protected-access

    @staticmethod
    def create() -> "MutableRangeSet[T]":
        return _MutableSortedDictRangeSet(SortedDict())

    def add(self, range_to_add: Range[T]) -> "MutableRangeSet[T]":
        if range_to_add.is_empty():
            return self

        # the range we actually need to add may not correspond exactly to range_to_add
        # because it may overlap or be connected to existing ranges
        # lb_to_add and ub_to_add will form the range we actually add
        lb_to_add = range_to_add._lower_bound
        ub_to_add = range_to_add._upper_bound

        range_below_lb: Optional[Range[T]] = _value_below(
            self._ranges_by_lower_bound, lb_to_add
        )

        # is there any range which begins strictly before range_to_add's lower bound?
        # if so, range_to_add's beginning might lie within that range...
        if range_below_lb and lb_to_add <= range_below_lb._upper_bound:
            # and we need to coalesce with it by extending the bounds to include
            # that range's lower bound
            lb_to_add = range_below_lb._lower_bound
            # if the upper bound exceeds ours, too, then our range to add is entirely
            # contained within range_below_lb. Since this is already in the set, we
            # have nothing to do
            if ub_to_add < range_below_lb._upper_bound:
                return self

        # now we need to check of coalescing and connectedness on the upper end
        range_below_ub: Optional[Range[T]] = _value_at_or_below(
            self._ranges_by_lower_bound, ub_to_add
        )
        if range_below_ub and ub_to_add < range_below_ub._upper_bound:
            ub_to_add = range_below_ub._upper_bound

        # any ranges which lie within the range we are getting ready to add are subsumed in it
        _clear(self._ranges_by_lower_bound, lb_to_add, ub_to_add)

        self._replace_range_with_same_lower_bound(Range(lb_to_add, ub_to_add))
        return self

    def add_all(
        self, ranges_to_add: Union["RangeSet[T]", Iterable[Range[T]]]
    ) -> "MutableRangeSet[T]":
        if isinstance(ranges_to_add, RangeSet):
            return self.add_all(ranges_to_add.as_ranges())
        for rng in ranges_to_add:
            self.add(rng)
        return self

    def clear(self) -> None:
        _clear(self._ranges_by_lower_bound, _BELOW_ALL, _ABOVE_ALL)

    def remove(self, rng: Range[T]) -> "MutableRangeSet[T]":
        raise NotImplementedError(
            "I didn't need this, so I didn't bother to implement it yet."
        )

    def _replace_range_with_same_lower_bound(self, rng: Range[T]) -> None:
        if rng.is_empty():
            del self._ranges_by_lower_bound[rng._lower_bound]
        else:
            self._ranges_by_lower_bound[rng._lower_bound] = rng


class _ImmutableSortedDictRangeSet(ImmutableRangeSet[T], _SortedDictRangeSet[T]):
    """
    An implementation of ImmutableRangeSet

    This should never be directly created by the user. In particular if something maintains
    a reference to sorted_dict, then all immutability guarantees are broken.
    """

    class Builder(ImmutableRangeSet.Builder[T2]):
        def __init__(self):
            self._mutable_builder = _MutableSortedDictRangeSet.create()

        def add(self, rng: Range[T2]) -> "ImmutableRangeSet.Builder[T2]":
            self._mutable_builder.add(rng)
            return self

        def build(self) -> "ImmutableRangeSet[T2]":
            return self._mutable_builder.immutable_copy()


K = TypeVar("K")
V = TypeVar("V")


class RangeMap(Generic[K, V], metaclass=ABCMeta):
    """
    A mapping from disjoint nonempty ranges to values.

    Queries look up the value associated with the range (if any) that contains a specified key.

    In contrast to RangeSet, no "coalescing" is done of connected ranges, even if they are mapped
    to the same value.

    Note that this does not extend `Mapping` because you can't iterate over the keys.

    This (including the documentation) is a partial translation of Guava's RangeMap to Python.
    Guava's implementation was written by Louis Wasserman.
    """

    __slots__ = ()

    @abstractmethod
    def __contains__(self, key: K) -> bool:
        """
        Determine whether any of this range set's key ranges contains `key`.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_enclosed_by(self, rng: Range[K]) -> ImmutableSet[V]:
        """
        Get values mapped to by any key in `rng`.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_from_rightmost_containing_or_below(self, key: K):
        """
        Get the value associated with the rightmost range in this set whose lower bound does not
        exceed *upper_limit*.

        Formally, this is the value associated with the range `(x, y)` with minimal `y` such that
        `(upper_limit, +inf)` does not contain `(x, y)`.

        If there is no such set, `None` is returned.

        For example::

         range_map: RangeMap[int, int] = immutablerangemap([
           (Range.open_closed(1, 10), 36),  // (1, 10) maps to 36
           (Range.open(12, 15), 17)         // (12, 13) maps to 17
         ]);`

         // range keys: {(1, 10], (12, 15)}
         range_map.get_from_rightmost_containing_or_below(1)  // returns None
         range_map.get_from_rightmost_containing_or_below(3)  // returns 36
         range_map.get_from_rightmost_containing_or_below(11) // returns 36
         range_map.get_from_rightmost_containing_or_below(12) // returns 36
         range_map.get_from_rightmost_containing_or_below(13) // returns 17
         range_map.get_from_rightmost_containing_or_below(15) // returns 17
        """

    @abstractmethod
    def get_from_leftmost_containing_or_above(self, key: K):
        """
        Get the value associated with the leftmost range in this set whose upper bound is not below
        *lower_limit*.

        Formally, this is the value associated with the range `(x, y)` with maximal `x` such that
        `(-inf, lower_limit)` does not contain `(x, y)`.

        If there is no such set, `None` is returned.

        For example::

         range_map: RangeSet[int] = immutablerangemap([
             (Range.open(1, 10), 5),
             (Range.open_closed(12, 15), 7)
         ])

         // range keys: {(1, 10), (12, 15]}
         range_map.get_from_leftmost_containing_or_above(1)  // returns 5
         range_map.get_from_leftmost_containing_or_above(3)  // returns 5
         range_map.get_from_leftmost_containing_or_above(10) // returns 7
         range_map.get_from_leftmost_containing_or_above(11) // returns 7
         range_map.get_from_leftmost_containing_or_above(12) // returns 7
         range_map.get_from_leftmost_containing_or_above(13) // returns 7
         range_map.get_from_leftmost_containing_or_above(15) // returns 7
         range_map.get_from_leftmost_containing_or_above(16) // returns None
        """

    @deprecation.deprecated(
        deprecated_in="0.19.0",
        removed_in=date(2020, 8, 10),
        details="Deprecated, use get_from_rightmost_containing_or_below(upper_limit). "
        "This method may be removed in a future release.",
    )
    def get_from_maximal_containing_or_below(self, key: K):
        return self.get_from_rightmost_containing_or_below(key)

    @deprecation.deprecated(
        deprecated_in="0.19.0",
        removed_in=date(2020, 8, 10),
        details="Deprecated, use get_from_leftmost_containing_or_below(key). "
        "This method may be removed in a future release.",
    )
    def get_from_minimal_containing_or_above(self, key: K):
        return self.get_from_leftmost_containing_or_above(key)

    def __eq__(self, other) -> bool:
        if isinstance(other, RangeMap):
            return ImmutableSet.of(self.as_dict()) == ImmutableSet.of(other.as_dict())
        else:
            return False

    @abstractmethod
    def as_dict(self) -> Mapping[Range[K], V]:
        raise NotImplementedError()

    def __hash__(self) -> int:
        return hash(self.as_dict())

    @abstractmethod
    def is_empty(self) -> bool:
        """
        Determine if this range map has no mappings.
        """
        raise NotImplementedError()

    def __repr__(self):
        return self.__class__.__name__ + "(" + str(self.as_dict()) + ")"


# necessary for builder because an inner class cannot share type variables with its outer class
K2 = TypeVar("K2")
V2 = TypeVar("V2")


# this should have slots=True but cannot for the moment due to
# https://github.com/python-attrs/attrs/issues/313
@attrs(frozen=True, repr=False)
class ImmutableRangeMap(Generic[K, V], RangeMap[K, V]):
    rng_to_val: ImmutableDict[Range[K], V] = attrib(converter=immutabledict)
    range_set: ImmutableRangeSet[K] = attrib(init=False)

    def __attrs_post_init__(self) -> None:
        if len(self.rng_to_val) != len(self.range_set):
            raise ValueError(
                "Some range keys are connected or overlapping. Overlapping keys "
                "will never be supported. Support for connected keys is tracked in "
                "https://github.com/isi-vista/vistautils/issues/37"
            )

    @staticmethod
    @deprecation.deprecated(
        deprecated_in="0.19.0",
        removed_in=date(2020, 8, 10),
        details="Deprecated - prefer the module-level factory ``immutablerangemap`` with no "
        "arguments.",
    )
    def empty() -> "ImmutableRangeMap[K, V]":
        return ImmutableRangeMap(immutabledict())

    @staticmethod
    def builder() -> "ImmutableRangeMap.Builder[K, V]":
        return ImmutableRangeMap.Builder()

    def __contains__(self, key: K) -> bool:
        return key in self.range_set

    def get_enclosed_by(self, rng: Range[K]) -> ImmutableSet[V]:
        ret: ImmutableSet.Builder[V] = ImmutableSet.builder()
        for rng_key in self.range_set.ranges_enclosed_by(rng):
            ret.add(self.rng_to_val[rng_key])
        return ret.build()

    def is_empty(self) -> bool:
        return self.range_set.is_empty()

    def __getitem__(self, k: K) -> Optional[V]:
        containing_range = self.range_set.range_containing(k)
        return self.rng_to_val[containing_range] if containing_range else None

    def as_dict(self) -> Mapping[Range[K], V]:
        return self.rng_to_val

    def get_from_rightmost_containing_or_below(self, key: K) -> Optional[V]:
        probe_range = self.range_set.rightmost_containing_or_below(key)
        return self.rng_to_val[probe_range] if probe_range else None

    def get_from_leftmost_containing_or_above(self, key: K) -> Optional[V]:
        probe_range = self.range_set.leftmost_containing_or_above(key)
        return self.rng_to_val[probe_range] if probe_range else None

    def __reduce__(self):
        # __getstate__/__setstate__ cannot be used because the implementation is frozen.
        _repr = ()
        if not self.is_empty():
            _repr = tuple(self.as_dict().items())
        return (immutablerangemap, (_repr,))

    @range_set.default  # type: ignore
    def _init_range_set(self) -> ImmutableRangeSet[K]:
        return (  # type: ignore
            ImmutableRangeSet.builder()  # type: ignore
            .add_all(self.rng_to_val.keys())  # type: ignore
            .build()  # type: ignore
        )

    class Builder(Generic[K2, V2]):
        def __init__(self):
            self.rng_to_val = ImmutableDict.builder()

        def put(self, key: Range[K2], val: V2) -> "ImmutableRangeMap.Builder[K2, V2]":
            self.rng_to_val.put(key, val)
            return self

        def build(self) -> "ImmutableRangeMap[K2, V2]":
            return ImmutableRangeMap(self.rng_to_val.build())


def immutablerangemap(
    mappings: Optional[Iterable[Tuple[Range[K], V]]] = None
) -> ImmutableRangeMap[K, V]:
    return ImmutableRangeMap(immutabledict(mappings))


# utility functions for SortedDict to give it an interface more like Java's NavigableMap
def _value_below(sorted_dict: SortedDict, key: T) -> Optional[Any]:
    """
    Get item for greatest key strictly less than the given key

    Returns None if there is no such key.
    """
    idx = sorted_dict.bisect_left(key) - 1
    if idx >= 0:
        if idx >= len(sorted_dict):
            idx = len(sorted_dict) - 1
        lb_key = sorted_dict.keys()[idx]
        return sorted_dict[lb_key]
    else:
        return None


def _value_at_or_below(sorted_dict: SortedDict, key: T) -> Optional[Any]:
    """
    Get item for greatest key less than or equal to a given key.

    Returns None if there is no such key
    """
    if not sorted_dict:
        return None

    idx = sorted_dict.bisect_left(key)

    if idx >= len(sorted_dict) or key != sorted_dict.keys()[idx]:
        if idx > 0:
            key = sorted_dict.keys()[idx - 1]
        else:
            return None
    return sorted_dict[key]


def _value_at_or_above(sorted_dict: SortedDict, key: T) -> Optional[Any]:
    if not sorted_dict:
        return None
    idx = sorted_dict.bisect_left(key)
    if idx >= len(sorted_dict):
        return None

    return sorted_dict[sorted_dict.keys()[idx]]


def _clear(
    sorted_dict: SortedDict, start_key_inclusive: T, stop_key_exclusive: T
) -> None:
    # we copy to a list first in case sorted_dict is not happy with modification during iteration
    for key_to_delete in list(
        sorted_dict.irange(
            start_key_inclusive, stop_key_exclusive, inclusive=(True, False)
        )
    ):
        del sorted_dict[key_to_delete]
