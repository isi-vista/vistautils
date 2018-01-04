from abc import ABCMeta
from typing import Iterable, Sequence, TypeVar, Tuple, Iterator

from attr import attrs, attrib

from flexnlp.utils.immutablecollections.immutablecollection import ImmutableCollection

T = TypeVar('T')


class ImmutableList(ImmutableCollection[T], Sequence[T], metaclass=ABCMeta):
    __slots__ = ()

    # Signature of the of method varies by collection
    # pylint: disable = arguments-differ
    @staticmethod
    def of(seq: Iterable[T]) -> 'ImmutableList[T]':
        if isinstance(seq, ImmutableList):
            return seq
        else:
            return _TupleBackedImmutableList(seq)

    @staticmethod
    def empty() -> 'ImmutableList[T]':
        return _EMPTY

    def __repr__(self):
        return 'i' + str(self)

    def __str__(self):
        return "%s" % list(self)


@attrs(frozen=True, slots=True, repr=False)
class _TupleBackedImmutableList(ImmutableList[T]):

    _list: Tuple[T, ...] = attrib(convert=tuple)

    def __getitem__(self, index: int) -> T:
        return self._list.__getitem__(index)

    def __iter__(self) -> Iterator[T]:
        return self._list.__iter__()

    def __len__(self):
        return self._list.__len__()


# Singleton instance for empty
_EMPTY: ImmutableList = _TupleBackedImmutableList(())
