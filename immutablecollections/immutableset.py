from abc import ABCMeta, abstractmethod
from typing import Iterable, TypeVar, FrozenSet, AbstractSet, Iterator, Generic, Type, List, \
    Sequence, Container, Any, Callable

import attr
from attr import attrs, attrib, validators

from flexnlp.utils.immutablecollections.immutablecollection import ImmutableCollection
from flexnlp.utils.immutablecollections.immutablelist import ImmutableList
from flexnlp.utils.preconditions import check_isinstance, check_issubclass, check_all_isinstance

T = TypeVar('T')
# necessary because inner classes cannot share typevars
T2 = TypeVar('T2')  # pylint:disable=invalid-name
SelfType = TypeVar('SelfType')  # pylint:disable=invalid-name


# typing.AbstractSet matches collections.abc.Set
class ImmutableSet(ImmutableCollection[T], AbstractSet[T], metaclass=ABCMeta):
    __slots__ = ()
    """
    A immutable set with deterministic iteration order.

    The set will be unmodifiable by normal means.

    The iteration order of the set will be the order in which elements were added. Iteration
    order is ignored when determining equality and hash codes.

    Optional top-level run-time type setting is supported (see of()).

    ImmutableSets should be created via of() or builder(), not by directly instantiating one of
    the sub-classes.

    For runtime type checks that wish to include ImmutableSet as well
    as the types set and frozenset, use collections.abc.Set or
    typing.AbstractSet. An ImmutableSet is not an instance of
    typing.Set, as that matches the built-in mutable set type.
    """

    # note to implementers: if a new implementing class is created besides the frozen set one,
    # we need to change how the equals method works

    # Signature of the of method varies by collection
    # pylint: disable = arguments-differ
    @staticmethod
    def of(seq: Iterable[T], check_top_type_matches=None,
           require_ordered_input=False) -> 'ImmutableSet[T]':  # typing: ignore
        """
        Create an immutable set with the given contents.

        The iteration order of the created set will match seq.  Note that for this reason,
        when initializing an immutable list from a constant collection expression, prefer a
        list over a set.

        If a type is provided to check_top_matches, each element of seq will be checked to
        be an instance of the provided type.

        If seq is already an ImmutableSet, seq itself will be returned.  If check_top_matches
        is specified and that ImmutableSet has already been type checked for a type which is a
        sub-class of the provided class, it is not type-checked again.

        If require_ordered_input is True (default False), an exception will be thrown if a
        non-sequence, non-ImmutableSet is used for initialization.  This is recommended to help
        encourage determinism.  A particularly common case is that ImmutableSets should not be
        initialized from set literals; prefer list literals to preserve ordering information.
        """
        # pylint:disable=protected-access
        if isinstance(seq, ImmutableSet):
            if check_top_type_matches:
                # we assume each sub-class provides _top_level_type
                if seq._top_level_type:  # type: ignore
                    check_issubclass(seq._top_level_type, check_top_type_matches)  # type: ignore
                else:
                    check_all_isinstance(seq, check_top_type_matches)
            return seq
        else:
            return (ImmutableSet.builder(check_top_type_matches=check_top_type_matches,
                                         require_ordered_input=require_ordered_input)
                .add_all(seq).build())  # pylint:disable=bad-continuation

    @staticmethod
    def empty() -> 'ImmutableSet[T]':
        """
        Get an empty ImmutableSet.
        """
        return _EMPTY

    @abstractmethod
    def as_list(self) -> ImmutableList[T]:
        """
        Get a view of this set's items as a list in insertion order.
        """
        raise NotImplementedError()

    # we would really like this to be AbstractSet[ExtendsT] but Python doesn't support it
    def union(self, other: AbstractSet[T], check_top_type_matches=None) -> 'ImmutableSet[T]':
        """
        Get the union of this set and another.

        If check top level types is provided, all elements of both sets must match the specified
        type.
        """
        check_isinstance(other, AbstractSet)
        return (ImmutableSet.builder(check_top_type_matches)
            .add_all(self).add_all(other).build())  # pylint:disable=bad-continuation

    # we deliberately tighten the type bounds from our parent
    def __or__(self, other: AbstractSet[T]) -> 'ImmutableSet[T]':  # type: ignore
        """
        Get the union of this set and another without type checking.
        """
        return self.union(self, other)

    def intersection(self, other: AbstractSet[Any]) -> 'ImmutableSet[T]':
        """
        Get the intersection of this set and another.

        If you know the set `x` is smaller then the set `y`, `x.intersection(y)` will be faster
        than `y.intersection(x)`.

        We don't provide an option to type-check here because any item in the resulting set
        should have already been in this set, so you can type check this set itself if you are
        concerned.
        """
        check_isinstance(other, AbstractSet)
        return (ImmutableSet.builder(check_top_type_matches=self._top_level_type)  # type: ignore
            .add_all(x for x in self if x in other).build())  # pylint:disable=bad-continuation

    def __and__(self, other: AbstractSet[Any]) -> 'ImmutableSet[T]':
        """
        Get the intersection of this set.
        """
        return self.intersection(other)

    def difference(self, other: AbstractSet[Any]) -> 'ImmutableSet[T]':
        """
        Gets a new set with all items in this set not in the other.
        """
        return ImmutableSet.of((x for x in self if x not in other),
                               check_top_type_matches=self._top_level_type)  # type: ignore

    def __sub__(self, other: AbstractSet[Any]) -> 'ImmutableSet[T]':
        """
        Gets a new set with all items in this set not in the other.
        """
        return self.difference(other)

    def __repr__(self):
        return 'i' + str(self)

    def __str__(self):
        # we use this rather than set() for when we add deterministic iteration order
        as_list = str(list(self))
        return "{%s}" % as_list[1:-1]

    @staticmethod
    def builder(check_top_type_matches: Type[T] = None,
                require_ordered_input=False,
                order_key: Callable[[T], Any] = None) -> 'ImmutableSet.Builder[T]':
        """
        Gets an object which can build an ImmutableSet.

        If check_top_matches is specified, each element added to this set will be
        checked to be an instance of that type.

        If require_ordered_input is True (default False), an exception will be thrown if a
        non-sequence, non-ImmutableSet is used for add_all.  This is recommended to help
        encourage determinism.

        If order_key is present, the order of the resulting set will be sorted by
        that key function rather than in the usual insertion order.

        You can check item containment before building the set by using "in" on the builder.
        """
        return ImmutableSet.Builder(top_level_type=check_top_type_matches,
                                    require_ordered_input=require_ordered_input,
                                    order_key=order_key)

    @attrs
    class Builder(Generic[T2], Container[T2]):
        _set: AbstractSet[T2] = attrib(default=attr.Factory(set))
        _iteration_order: List[T2] = attrib(default=attr.Factory(list))
        # this is messy because we can't use attrutils or we would end up with a circular import
        _top_level_type: Type = attrib(validator=validators.instance_of((Type, type(None))),
                                       default=None)
        _require_ordered_input = attrib(validator=validators.instance_of(bool), default=False)
        _order_key: Callable[[T2], Any] = attrib(default=None)

        def add(self: SelfType, item: T2) -> SelfType:
            if self._top_level_type:
                check_isinstance(item, self._top_level_type)
            if item not in self._set:
                self._set.add(item)
                self._iteration_order.append(item)
            return self

        def add_all(self: SelfType, items: Iterable[T2]) -> SelfType:
            if self._require_ordered_input and not (isinstance(items, Sequence) or isinstance(
                    items, ImmutableSet)) and not self._order_key:
                raise ValueError("Builder has require_ordered_input on, but provided collection "
                                 "is neither a sequence or another ImmutableSet.  A common cause "
                                 "of this is initializing an ImmutableSet from a set literal; "
                                 "prefer to initialize from a list instead to help preserve "
                                 "determinism.")
            for item in items:
                self.add(item)
            return self

        def __contains__(self, item):
            return self._set.__contains__(item)

        def build(self) -> 'ImmutableSet[T2]':
            if self._set:
                if self._order_key:
                    # mypy is confused
                    self._iteration_order.sort(key=self._order_key)  # type: ignore
                return _FrozenSetBackedImmutableSet(self._set, self._iteration_order,
                                                    top_level_type=self._top_level_type)
            else:
                return _EMPTY


@attrs(frozen=True, slots=True, repr=False)
class _FrozenSetBackedImmutableSet(ImmutableSet[T]):
    """
    Implementing class for the general case for ImmutableSet.

    This class should *never*
    be directly instantiated by users or the ImmutableSet contract may fail to be satisfied!
    """

    _set: FrozenSet[T] = attrib(convert=frozenset)
    # because only the set contents should matter for equality, we set cmp=False hash=False
    # on the remaining attributes
    _iteration_order: ImmutableList[T] = attrib(convert=ImmutableList.of,
                                                cmp=False, hash=False)
    _top_level_type: Type = attrib(cmp=False, hash=False)

    def as_list(self) -> ImmutableList[T]:
        return self._iteration_order

    def __iter__(self) -> Iterator[T]:
        return self._iteration_order.__iter__()

    def __len__(self) -> int:
        return self._set.__len__()

    def __contains__(self, item) -> bool:
        return self._set.__contains__(item)

    def __eq__(self, other):
        # pylint:disable=protected-access
        if isinstance(other, _FrozenSetBackedImmutableSet):
            return self._set == other._set
        else:
            return False

    def __hash__(self):
        return self._set.__hash__()


# Singleton instance for empty
_EMPTY: ImmutableSet = _FrozenSetBackedImmutableSet((), (), None)
