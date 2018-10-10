from operator import attrgetter
from typing import Iterable, List, Sequence, TypeVar, Any

from typing_extensions import Protocol

from flexnlp.model.protocols import HasConfidence

T = TypeVar('T')


def sorted_descending_confidence(items: Iterable[HasConfidence]) -> List[HasConfidence]:
    return sorted(items, key=attrgetter('confidence'), reverse=True)


class Sorter(Protocol[T]):
    __slots__: tuple = ()

    def sorted(self, seq: Sequence[T]) -> Sequence[T]:
        """Return a sorted version of the argument."""
        raise NotImplementedError()


class IdentitySorter(Sorter[Any]):
    def sorted(self, seq: Sequence[Any]) -> Sequence[Any]:
        return seq


class DescendingConfidence(Sorter[HasConfidence]):
    def sorted(self, seq: Sequence[HasConfidence]) -> Sequence[HasConfidence]:
        return sorted(seq, key=attrgetter('confidence'), reverse=True)
