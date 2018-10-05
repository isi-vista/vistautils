from abc import ABCMeta, abstractmethod
from collections import defaultdict
from typing import AbstractSet, Any, Callable, Collection, Generic, Iterable, Iterator, Mapping, \
    MutableMapping, Optional, Tuple, TypeVar, Union, \
    ValuesView  # pylint:disable=unused-import

from attr import attrib, attrs
from frozendict import frozendict

from flexnlp.utils.immutablecollections import ImmutableList, ImmutableSet
from flexnlp.utils.immutablecollections.immutablecollection import ImmutableCollection
from flexnlp.utils.immutablecollections.immutablelist import EMPTY_IMMUTABLE_LIST
from flexnlp.utils.preconditions import check_isinstance

KT = TypeVar('KT')
VT = TypeVar('VT')
IT = Tuple[KT, VT]  # item type

# cannot share type variables between out and inner classes
KT2 = TypeVar('KT2')
VT2 = TypeVar('VT2')
IT2 = Tuple[KT2, VT2]  # item type

SelfType = TypeVar('SelfType')  # pylint:disable=invalid-name


class ImmutableMultiDict(ImmutableCollection[KT], Generic[KT, VT], metaclass=ABCMeta):
    __slots__ = ()

    def value_groups(self) -> ValuesView[Collection[VT]]:
        """
        Gets an object containing the groups of values for keys in this MultiDict.

        If you iterate over this you will get collections, where each collection contains
        the values corresponding to a single key
        """
        return self.as_dict().values()

    @abstractmethod
    def __getitem__(self, key: KT) -> Collection[VT]:
        """
        Gets the collection of values a key maps to.

        If there are not such values, an empty collection is returned.
        """

    def __contains__(self, key: KT) -> bool:
        """
        Returns true if there is at least one value associated with `key`
        """
        return key in self.as_dict()

    def keys(self) -> AbstractSet:
        """
        Gets a set-like object containing the keys of this multidict.
        """
        return self.as_dict().keys()

    def items(self):
        # inefficient default implementation
        for key in self.keys():
            for val in self[key]:
                yield (key, val)

    @abstractmethod
    def __len__(self) -> int:
        """
        Get the number of key-value mappings in this multidict.
        """

    @abstractmethod
    def as_dict(self) -> Mapping[KT, Collection[VT]]:
        """
        Gets a map where each key in this multidict is mapped to the collection of its values.

        Note to implementers: many other ImmutableMultiDict methods are defined in terms of this,
        so its implementation should be fast (either by directly exposing an internal data
        structure, when safe to do so, or by caching a map view).
        """

    def __iter__(self) -> Iterator[KT]:
        return self.as_dict().__iter__()


# needs tests: issue #127
class ImmutableSetMultiDict(ImmutableMultiDict[KT, VT], metaclass=ABCMeta):
    __slots__ = ()

    # of() does not allow a value_comparator to be passed in, since it's not clear what
    # the correct behavior would be if passed an existing ImmutableSetMultiDict and a
    # (possibly inconsistent) value_comparator. Use the builder() directly if you
    # want to specify a sorting method.

    # Signature of the of method varies by collection
    # pylint: disable = arguments-differ
    @staticmethod
    def of(data: Union[Mapping[KT, Iterable[VT]], Iterable[IT]]) -> \
            'ImmutableSetMultiDict[KT, VT]':
        """
        Creates an ImmutableSetMultiDict from existing data.

        If an existing ImmutableSetMultiDict is passed, it is simply returned.
        If a mapping from keys to sequences of values is passed, each key paired with each
        of its corresponding values it added to the mapping.
        If a sequence of key-value pair tuples is passed, each is added to the mapping.
        """
        if isinstance(data, ImmutableSetMultiDict):
            return data
        elif isinstance(data, Mapping):
            return ImmutableSetMultiDict.builder().put_all(data).build()  # type: ignore
        else:
            return ImmutableSetMultiDict.builder().put_all_items(data).build()  # type: ignore

    @staticmethod
    def empty() -> 'ImmutableSetMultiDict[KT, VT]':
        return _SET_EMPTY

    # we need to repeat all these inherited/abstract methods with specialized type signatures
    # because mypy doesn't support type parameters which are themselves generic (e.g. parameterizing
    # ImmutableMultiDict by a collection type)
    @abstractmethod
    def __getitem__(self, k: KT) -> ImmutableSet[VT]:
        """
       Gets the set of values a key maps to.

       If there are no such values, an empty collection is returned.
       """

    def value_groups(self) -> ValuesView[ImmutableSet[VT]]:
        """
        Gets an object containing the set of values for keys in this MultiDict.

        If you iterate over this you will get sets, where each set contains
        the values corresponding to a single key
        """
        return self.as_dict().values()

    @abstractmethod
    def as_dict(self) -> Mapping[KT, ImmutableSet[VT]]:
        """
        Gets a map where each key in this multidict is mapped to the collection of its values
        """

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

    def __repr__(self):
        return 'i' + str(self)

    def __str__(self):
        # we use %s for the value position because we know these are ImmutableSets and don't
        # need the "i" prefix they add with repr
        return "{%s}" % ", ".join("%r: %s" % item for item in self.as_dict().items())

    class Builder(Generic[KT2, VT2]):
        def __init__(self, *, source: Optional['ImmutableMultiDict[KT2,VT2]'] = None,
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

        def put_all(self: SelfType, data: Mapping[KT2, Iterable[VT2]]) -> SelfType:
            for (k, values) in data.items():
                for v in values:
                    self.put(k, v)
            return self

        def put_all_items(self: SelfType, data: Iterable[IT2]) -> SelfType:
            """
            Adds each key-value mapping from a sequence of key-value tuples.
            """
            for (k, v) in data:
                self.put(k, v)
            return self

        def build(self) -> 'ImmutableSetMultiDict[KT2, VT2]':
            if self._dirty or self._source is None:
                result: ImmutableSetMultiDict[KT2, VT2] = FrozenDictBackedImmutableSetMultiDict(
                    {k: v.build() for (k, v) in self._dict.items()})  # type: ignore
                return result if result else _SET_EMPTY
            else:
                # noinspection PyTypeChecker
                return self._source  # type: ignore


def _freeze_set_multidict(x: Mapping[KT, Iterable[VT]]) -> Mapping[KT, ImmutableSet[VT]]:
    for (_, v) in x.items():
        check_isinstance(v, Iterable)
    return frozendict({k: ImmutableSet.of(v) for (k, v) in x.items()})


@attrs(frozen=True, slots=True, repr=False)
class FrozenDictBackedImmutableSetMultiDict(ImmutableSetMultiDict[KT, VT]):
    _dict: Mapping[KT, ImmutableSet[VT]] = attrib(converter=_freeze_set_multidict)
    _len: Optional[int] = attrib(init=False, cmp=False, default=None)

    def as_dict(self) -> Mapping[KT, ImmutableSet[VT]]:
        """
        Gets a map where each key in this multidict is mapped to the collection of its values
        """
        return self._dict

    def value_groups(self) -> ValuesView[ImmutableSet[VT]]:
        """
        Get the sets of values for keys in this MultiDict.
        """
        return self._dict.values()

    def __len__(self) -> int:  # pylint:disable=invalid-length-returned
        """
        Get the numeber of key-value mappings in this multidict.
        """
        if self._len is None:
            object.__setattr__(self, '_len', sum((len(x) for x in self.value_groups()), 0))
        return self._len

    def __getitem__(self, k: KT) -> ImmutableSet[VT]:
        return self._dict.get(k, ImmutableSet.empty())


# Singleton instance for empty
_SET_EMPTY: ImmutableSetMultiDict = FrozenDictBackedImmutableSetMultiDict({})


# needs tests: issue #127
class ImmutableListMultiDict(ImmutableMultiDict[KT, VT], metaclass=ABCMeta):
    __slots__ = ()

    # Signature of the of method varies by collection
    # pylint: disable = arguments-differ
    @staticmethod
    def of(data: Union[Mapping[KT, Iterable[VT]], Iterable[IT]]) -> \
            'ImmutableListMultiDict[KT, VT]':
        if isinstance(data, ImmutableListMultiDict):
            return data
        elif isinstance(data, Mapping):
            return ImmutableListMultiDict.builder().put_all(data).build()  # type: ignore
        else:
            return ImmutableListMultiDict.builder().put_all_items(data).build()  # type: ignore

    @staticmethod
    def empty() -> 'ImmutableListMultiDict[KT, VT]':
        return _EMPTY_IMMUTABLE_MULTIDICT

    @staticmethod
    def builder() -> 'ImmutableListMultiDict.Builder[KT, VT]':
        return ImmutableListMultiDict.Builder()

    # we need to repeat all these inherited/abstract methods with specialized type signatures
    # because mypy doesn't support type paramters which are themselves generic (e.g. parameterizing
    # ImmutableMultiDict by a collection type)
    @abstractmethod
    def __getitem__(self, k: KT) -> ImmutableList[VT]:
        """
       Gets the list of values a key maps to.

       If there are no such values, an empty list is returned.
       """

    @abstractmethod
    def as_dict(self) -> Mapping[KT, ImmutableList[VT]]:
        """
        Gets a map where each key in this multidict is mapped to the list of its values
        """

    def value_groups(self) -> ValuesView[ImmutableList[VT]]:
        """
        Gets an object containing the list of values for keys in this MultiDict.

        If you iterate over this you will get lists, where each list contains
        the values corresponding to a single key
        """
        return self.as_dict().values()

    def modified_copy_builder(self) -> 'ImmutableListMultiDict.Builder[KT, VT]':
        return ImmutableListMultiDict.Builder(source=self)

    def filter_keys(self, predicate: Callable[[KT], bool]) -> 'ImmutableListMultiDict[KT, VT]':
        """
        Filters an ImmutableListMultiDict by a predicate on its keys.

        Returns an ImmutableListMultiDict just like this one but with keys for which the predicate
        returns a false value removed.

        While you can filter with a comprehension, this maintains order (or will when/if
        ImmutableDict in general is updated to maintain order) and allows us not to do any
        copying if all keys pass the filter
        """
        retained_keys = [key for key in self.keys() if predicate(key)]
        if len(retained_keys) == len(self.keys()):
            return self
        else:
            ret: ImmutableListMultiDict.Builder[KT, VT] = ImmutableListMultiDict.builder()
            for key in retained_keys:
                for val in self[key]:
                    ret.put(key, val)
            return ret.build()

    def __repr__(self):
        return 'i' + str(self)

    def __str__(self):
        # we use %s for the value position because we know these are ImmutableLists and don't
        # need the "i" prefix they add with repr
        return "{%s}" % ", ".join("%r: %s" % item for item in self.as_dict().items())

    class Builder(Generic[KT2, VT2]):
        def __init__(self, *, source: Optional['ImmutableMultiDict[KT2,VT2]'] = None) -> None:
            self._dict: MutableMapping[KT2, ImmutableList.Builder[VT2]] = defaultdict(
                ImmutableList.builder)
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

        def put_all_items(self: SelfType, data: Iterable[IT2]) -> SelfType:
            """
            Adds each key-value mapping from a sequence of key-value tuples.
            """
            for (k, v) in data:
                self.put(k, v)
            return self

        def build(self) -> 'ImmutableListMultiDict[KT2, VT2]':
            if self._dirty or self._source is None:
                result: ImmutableListMultiDict[KT2, VT2] = FrozenDictBackedImmutableListMultiDict(
                    {k: v.build() for (k, v) in self._dict.items()})  # type: ignore
                return result if result else _EMPTY_IMMUTABLE_MULTIDICT
            else:
                # noinspection PyTypeChecker
                return self._source  # type: ignore


def _freeze_list_multidict(x: Mapping[KT, Iterable[VT]]) -> Mapping[KT, ImmutableList[VT]]:
    for (_, v) in x.items():
        check_isinstance(v, Iterable)
    return frozendict({k: ImmutableList.of(v) for (k, v) in x.items()})


@attrs(frozen=True, slots=True, repr=False)
class FrozenDictBackedImmutableListMultiDict(ImmutableListMultiDict[KT, VT]):
    _dict: Mapping[KT, ImmutableList[VT]] = attrib(converter=_freeze_list_multidict)
    _len: Optional[int] = attrib(init=False, cmp=False, default=None)

    def as_dict(self) -> Mapping[KT, ImmutableList[VT]]:
        return self._dict

    def __getitem__(self, k: KT) -> ImmutableList[VT]:
        return self._dict.get(k, EMPTY_IMMUTABLE_LIST)

    def __len__(self) -> int:  # pylint:disable=invalid-length-returned
        """
        Get the numeber of key-value mappings in this multidict.
        """
        if self._len is None:
            object.__setattr__(self, '_len', sum((len(x) for x in self.value_groups()), 0))
        return self._len


# Singleton instance for empty
_EMPTY_IMMUTABLE_MULTIDICT: ImmutableListMultiDict = FrozenDictBackedImmutableListMultiDict({})
