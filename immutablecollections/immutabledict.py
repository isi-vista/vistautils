from abc import ABCMeta
from typing import Iterable, Mapping, TypeVar, Tuple, Iterator, Union, Generic, Callable, \
    MutableMapping

from attr import attrs, attrib
from frozendict import frozendict

from flexnlp.utils.immutablecollections.immutablecollection import ImmutableCollection

KT = TypeVar('KT')
VT = TypeVar('VT')
IT = Tuple[KT, VT]

# cannot share type variables between outer and inner classes
KT2 = TypeVar('KT2')
VT2 = TypeVar('VT2')
IT2 = Tuple[KT, VT]

SelfType = TypeVar('SelfType')  # pylint:disable=invalid-name


class ImmutableDict(ImmutableCollection[KT], Mapping[KT, VT], metaclass=ABCMeta):
    __slots__ = ()

    # Signature of the of method varies by collection
    # pylint: disable = arguments-differ
    @staticmethod
    def of(dict_: Union[Mapping[KT, VT], Iterable[IT]]) -> 'ImmutableDict[KT, VT]':
        if isinstance(dict_, ImmutableDict):
            return dict_
        else:
            return ImmutableDict.builder().put_all(dict_).build()  # type:ignore

    @staticmethod
    def empty() -> 'ImmutableDict[KT, VT]':
        return _EMPTY

    @staticmethod
    def builder() -> 'ImmutableDict.Builder[KT, VT]':
        return ImmutableDict.Builder()

    @staticmethod
    def index(items: Iterable[VT], key_function: Callable[[VT], KT]) -> 'ImmutableDict[KT, VT]':
        """
        Get a mapping to each value from the result of applying a key function.

        The result is an `ImmutableDict` where each given item appears as a value which
        is mapped to from the result of applying `key_function` to the value.
        """
        ret: ImmutableDict.Builder[KT, VT] = ImmutableDict.builder()

        for item in items:
            ret.put(key_function(item), item)

        return ret.build()

    def modified_copy_builder(self) -> 'ImmutableDict.Builder[KT, VT]':
        return ImmutableDict.Builder(source=self)

    def filter_keys(self, predicate: Callable[[KT], bool]) -> 'ImmutableDict[KT, VT]':
        """
        Filters an ImmutableDict by a predicate on its keys.

        Returns an ImmutableDict just like this one but with keys for which the predicate
        returns a false value removed.

        While you can filter with a comprehension, this maintains order (or will when/if
        ImmutableDict in general is updated to maintain order) and allows us not to do any
        copying if all keys pass the filter
        """
        retained_keys = [key for key in self.keys() if predicate(key)]
        if len(retained_keys) == len(self.keys()):
            return self
        else:
            ret: ImmutableDict.Builder[KT, VT] = ImmutableDict.builder()
            for key in retained_keys:
                ret.put(key, self[key])
            return ret.build()

    def __repr__(self):
        return 'i' + str(self)

    def __str__(self):
        return "{%s}" % ", ".join(["%s: %s" % item for item in self.items()])

    class Builder(Generic[KT2, VT2]):
        def __init__(self, source: 'ImmutableDict[KT2,VT2]' = None) -> None:
            self._dict: MutableMapping[KT2, VT2] = {}
            self.source = source

        def put(self: SelfType, key: KT2, val: VT2) -> SelfType:
            if self.source:
                # we only lazily copy the contents of source because if no changes are ever made
                # we can just reuse it
                # we need the temporary variable because the call to put_all below will
                # call this put method again and we need self.source to be None to avoid an
                # infinite loop
                tmp_source = self.source
                # Defend against multithreading scenario where another thread has cleared
                # self.source already. Not that this code is meant to be thread-safe anyway,
                # but at least you won't get non-deterministic crashes
                if tmp_source is not None:
                    self.source = None
                    self.put_all(tmp_source)

            self._dict[key] = val
            return self

        def put_all(self: SelfType, data: Union[Mapping[KT2, VT2], Iterable[IT2]]) -> SelfType:
            if isinstance(data, Mapping):
                for (k, v) in data.items():
                    self.put(k, v)
            elif isinstance(data, Iterable):
                # mypy is confused
                for (k, v) in data:  # type: ignore
                    self.put(k, v)
            else:
                raise TypeError("Can only initialize ImmutableDict from another dictionary or "
                                "a sequence of key-value pairs")
            return self

        def __setitem__(self, key: KT2, value: VT2) -> None:
            self.put(key, value)

        def build(self) -> 'ImmutableDict[KT2, VT2]':
            if self.source:
                # if any puts were done this will be None. If no puts were done we can return
                # the ImmutableDict we were based on because we will be identical and immutable
                # objects can be safely shared
                return self.source
            if self._dict:
                return FrozenDictBackedImmutableDict(self._dict)
            else:
                return _EMPTY


@attrs(frozen=True, slots=True, repr=False)
class FrozenDictBackedImmutableDict(ImmutableDict[KT, VT]):

    # Mypy does not believe this is a valid converter, but it is
    _dict = attrib(converter=frozendict)  # type:ignore

    def __getitem__(self, k: KT) -> VT:
        return self._dict.__getitem__(k)

    def __len__(self) -> int:
        return self._dict.__len__()

    def __iter__(self) -> Iterator[KT]:
        return self._dict.__iter__()

    # Could allow the Mapping ABC to do this for us, but this is more direct
    def __contains__(self, x: object) -> bool:
        return self._dict.__contains__(x)


# Singleton instance for empty
_EMPTY: ImmutableDict = FrozenDictBackedImmutableDict({})
