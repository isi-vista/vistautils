import shutil
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Any, Container, Union

from attr import attrib, attrs

from vistautils.preconditions import check_isinstance


class Checkpoints(Container[str], metaclass=ABCMeta):
    """
    Keep track of which tasks have been done.

    Tasks are identified by strings.  Check if a task has been done using the `in` operator.

    Particular implementations may limit what checkpoint strings are legal.
    """

    @abstractmethod
    def set(self, name: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def reset_all(self) -> None:
        raise NotImplementedError()

    @staticmethod
    def from_directory(directory: Union[Path, str]) -> "_CheckPointDirectory":
        """
        Get a checkpoint store backed by a filesystem directory.

        Checkpoint names must be legal file names on the underlying filesystem.
        """
        if isinstance(directory, str):
            directory = Path(directory)

        directory.mkdir(parents=True, exist_ok=True)
        return _CheckPointDirectory(directory)


@attrs(frozen=True, slots=True)
class _CheckPointDirectory(Checkpoints):
    """
    Track checkpoints for a program using files in a directory.

    This is not thread-safe and will not work if external factors meddle with the
    directory.
    """

    directory: Path = attrib()

    def set(self, name: str) -> None:
        check_isinstance(name, str)
        Path(self.directory, name).touch(exist_ok=True)

    def __contains__(self, item: Any) -> bool:
        check_isinstance(item, str)
        return Path(self.directory, item).is_file()

    def reset_all(self) -> None:
        shutil.rmtree(str(self.directory))
        self.directory.mkdir(parents=True, exist_ok=True)
