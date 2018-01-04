from abc import ABCMeta
from typing import Iterable, Mapping, TypeVar, Tuple, Iterator, Union, Generic

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

    def __repr__(self):
        return 'i' + str(self)

    def __str__(self):
        return "{%s}" % ", ".join(["%s: %s" % item for item in self.items()])

    class Builder(Generic[KT2, VT2]):
        def __init__(self):
            self._dict = {}

        def put(self: SelfType, key: KT2, val: VT2) -> SelfType:
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
            return FrozenDictBackedImmutableDict(self._dict)


@attrs(frozen=True, slots=True, repr=False)
class FrozenDictBackedImmutableDict(ImmutableDict[KT, VT]):

    _dict = attrib(convert=frozendict)

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
