from abc import abstractmethod, ABCMeta
from typing import Generic, TypeVar, Iterator

T = TypeVar('T')


class ImmutableCollection(Generic[T], metaclass=ABCMeta):
    __slots__ = ()

    @abstractmethod
    def __iter__(self) -> Iterator[T]:
        raise NotImplementedError()

    # TODO: of/empty needed to avoid warnings for attrib_opt_immutable, but are they a good idea?
    @staticmethod
    @abstractmethod
    def of(seq):
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def empty():
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def builder():
        raise NotImplementedError()
