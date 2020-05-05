"""Python versions of Guava-like checks."""
from typing import Any, Iterable, Tuple, TypeVar, Union

# Disable naming convention warnings for type aliases
# pylint: disable=invalid-name
# Type annotation from TypeShed for classinfo argument  of isinstance and issubclass

_ClassInfo = Union[type, Tuple[Union[type, Tuple], ...]]


T = TypeVar("T")


def check_not_none(x: T, msg: str = None) -> T:
    """
    Raise an error if the given argument is None.

    This returns its input so you can do::
        self.x = check_not_none(x)

    check_arg would have the same result but is less clear to the reader
    """
    if x is None:
        if msg:
            raise ValueError(msg)
        else:
            raise ValueError()
    else:
        return x


def check_arg(result: Any, msg: str = None, msg_args: Tuple = None) -> None:
    if not result:
        if msg:
            raise ValueError(msg % (msg_args or ()))
        else:
            raise ValueError()


def check_state(result: Any, msg: str = None):
    if not result:
        if msg:
            raise AssertionError(msg)
        else:
            raise AssertionError()


def check_args_are_none(*args, msg: str = None):
    for arg in args:
        check_arg(arg is None, msg)


def check_args_not_none(*args, msg: str = None):
    for arg in args:
        check_arg(arg is not None, msg)


def check_isinstance(item: T, classinfo: _ClassInfo) -> T:
    if not isinstance(item, classinfo):
        raise TypeError(
            "Expected instance of type {!r} but got type {!r} for {!r}".format(
                classinfo, type(item), item
            )
        )
    return item


def check_opt_isinstance(item: T, classinfo: _ClassInfo) -> T:
    """
    Checks something is ether None or an instance of a given class.

    Raises a TypeError otherwise
    """
    if item and not isinstance(item, classinfo):
        raise TypeError(
            "Expected instance of type {!r} but got type {!r} for {!r}".format(
                classinfo, type(item), item
            )
        )
    return item


def check_all_isinstance(items: Iterable[Any], classinfo: _ClassInfo):
    for item in items:
        check_isinstance(item, classinfo)


def check_issubclass(item, classinfo: _ClassInfo):
    if not issubclass(item, classinfo):
        raise TypeError(
            "Expected subclass of type {!r} but got {!r}".format(classinfo, type(item))
        )
    return item


def check_in(item: Any, legal_values: Iterable[Any], item_name: str = None) -> None:
    if item not in legal_values:
        # dynamic import here to break circular dependency
        # performance impact is minimal since import only happens on precondition failure,
        # which will presumably crash the program
        import vistautils.misc_utils  # pylint:disable=import-outside-toplevel

        item_msg = " {!s} to be".format(item_name) if item_name else ""
        raise ValueError(
            "Expected{!s} one of {!s} but got {!s}".format(
                item_msg, vistautils.misc_utils.str_list_limited(legal_values, 10), item
            )
        )
