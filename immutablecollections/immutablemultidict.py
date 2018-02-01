from abc import ABCMeta
from collections import defaultdict
from typing import Iterable, Mapping, TypeVar, Iterator, Generic, Callable, Any, MutableMapping, \
    Optional

from attr import attrs, attrib
from frozendict import frozendict

from flexnlp.utils.immutablecollections import ImmutableSet
from flexnlp.utils.immutablecollections.immutablecollection import ImmutableCollection
from flexnlp.utils.preconditions import check_isinstance

KT = TypeVar('KT')
VT = TypeVar('VT')

# cannot share type variables between out and inner classes
KT2 = TypeVar('KT2')
VT2 = TypeVar('VT2')

SelfType = TypeVar('SelfType')  # pylint:disable=invalid-name


# TODO: it is incorrect to implement mapping because we don't want .values() to return
# a collection of sets (but rather a collection of VTs). If this is fixed, update
# DocumentBuilder.build() (at least)
class ImmutableMultiDict(ImmutableCollection[KT], Mapping[KT, Iterable[VT]], metaclass=ABCMeta):
    __slots__ = ()

    @staticmethod
    def empty() -> 'ImmutableMultiDict[KT, VT]':
        return ImmutableSetMultiDict.empty()


# needs tests: issue #127
class ImmutableSetMultiDict(ImmutableMultiDict[KT, VT], Mapping[KT, ImmutableSet[VT]],
                            metaclass=ABCMeta):
    __slots__ = ()

    # of() does not allow a value_comparator to be passed in, since it's not clear what
    # the correct behavior would be if passed an existing ImmutableSetMultiDict and a
    # (possibly inconsistent) value_comparator. Use the builder() directly if you
    # want to specify a sorting method.

    # Signature of the of method varies by collection
    # pylint: disable = arguments-differ
    @staticmethod
    def of(dict_: Mapping[KT, Iterable[VT]]) -> 'ImmutableSetMultiDict[KT, VT]':
        if isinstance(dict_, ImmutableSetMultiDict):
            return dict_
        else:
            return ImmutableSetMultiDict.builder().put_all(dict_).build()  # type: ignore

    @staticmethod
    def empty() -> 'ImmutableSetMultiDict[KT, VT]':
        return _EMPTY

    @staticmethod
    def builder(value_order_key: Callable[[VT], Any] = None) \
            -> 'ImmutableSetMultiDict.Builder[KT, VT]':
        return ImmutableSetMultiDict.Builder(order_key=value_order_key)

    def modified_copy_builder(self) -> 'ImmutableSetMultiDict.Builder[KT, VT]':
        return ImmutableSetMultiDict.Builder(source=self)

    def filter_keys(self, predicate: Callable[[KT], bool]) -> 'ImmutableSetMultiDict[KT, VT]':
        """
        Filters an ImmutableSetMultiDict by a predicate on its keys.

        Returns an ImmutableSetMultiDict just like this one but with keys for which the predicate
        returns a false value removed.

        While you can filter with a comprehension, this maintains order (or will when/if
        ImmutableDict in general is updated to maintain order) and allows us not to do any
        copying if all keys pass the filter
        """
        retained_keys = [key for key in self.keys() if predicate(key)]
        if len(retained_keys) == len(self.keys()):
            return self
        else:
            ret: ImmutableSetMultiDict.Builder[KT, VT] = ImmutableSetMultiDict.builder()
            for key in retained_keys:
                for val in self[key]:
                    ret.put(key, val)
            return ret.build()

    def __getitem__(self, k: KT) -> ImmutableSet[VT]:
        raise NotImplementedError()

    def __repr__(self):
        return 'i' + str(self)

    def __str__(self):
        # we use %s for the value position because we know these are ImmutableSets and don't
        # need the "i" prefix they add with repr
        return "{%s}" % ", ".join("%r: %s" % item for item in self.items())

    class Builder(Generic[KT2, VT2]):
        def __init__(self, *, source: 'Optional[ImmutableMultiDict[KT2,VT2]]' = None,
                     order_key: Callable[[VT2], Any] = None) -> None:
            self._dict: MutableMapping[KT2, ImmutableSet.Builder[VT2]] = defaultdict(
                lambda: ImmutableSet.builder(order_key=order_key))
            self._source = source
            self._dirty = False

        def put(self: SelfType, key: KT2, value: VT2) -> SelfType:
            if self._source:
                # we only lazily copy the contents of source because if no changes are ever made
                # we can just reuse it
                # we need the temporary variable because the call to put_all below will
                # call this put method again and we need self.source to be None to avoid an
                # infinite loop
                tmp_source = self._source
                # Defend against multithreading scenario where another thread has cleared
                # self.source already. Not that this code is meant to be thread-safe anyway,
                # but at least you won't get non-deterministic crashes
                if tmp_source is not None:
                    self._source = None
                    for k in tmp_source.keys():
                        for v in tmp_source[k]:
                            self.put(k, v)

            self._dict[key].add(value)
            self._dirty = True
            return self

        def put_all(self: SelfType, dict_: Mapping[KT2, Iterable[VT2]]) -> SelfType:
            for (k, values) in dict_.items():
                for v in values:
                    self.put(k, v)
            return self

        def build(self) -> 'ImmutableSetMultiDict[KT2, VT2]':
            if self._dirty or self._source is None:
                return FrozenDictBackedImmutableSetMultiDict(
                    {k: v.build() for (k, v) in self._dict.items()})
            else:
                return self._source  # type: ignore


def _freeze_set_multidict(x: Mapping[KT, Iterable[VT]]) -> Mapping[KT, ImmutableSet[VT]]:
    for (_, v) in x.items():
        check_isinstance(v, Iterable)
    return frozendict({k: ImmutableSet.of(v) for (k, v) in x.items()})


@attrs(frozen=True, slots=True, repr=False)
class FrozenDictBackedImmutableSetMultiDict(ImmutableSetMultiDict[KT, VT]):
    _dict = attrib(convert=_freeze_set_multidict)

    def __getitem__(self, k: KT) -> ImmutableSet[VT]:
        return self._dict.get(k, ImmutableSet.empty())

    def __len__(self) -> int:
        return self._dict.__len__()

    def __iter__(self) -> Iterator[KT]:
        return self._dict.__iter__()

    # Could allow the Mapping ABC to do this for us, but this is more direct
    def __contains__(self, x: object) -> bool:
        return self._dict.__contains__(x)


# Singleton instance for empty
_EMPTY: ImmutableSetMultiDict = FrozenDictBackedImmutableSetMultiDict({})
