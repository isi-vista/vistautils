from typing import Any


def fully_qualified_name(clazz: type) -> str:
    """
    Gets the fully-qualified name of a class.

    This is the package name, plus the module name, plus the class name (including parent
    classes for nested classes), joined by `.`s.  For builtin types or module-less types,
    the package and module portions are omitted.

    This implementation is indebted to https://stackoverflow.com/a/13653312/413345
    """
    module = clazz.__module__
    # we compared to str.__class__.__module__ so that we don't include the
    # "builtin." prefix for built-in types
    if module is None or module == str.__class__.__module__:
        return clazz.__qualname__
    return module + "." + clazz.__qualname__


def fully_qualified_name_of_type(obj: Any) -> str:
    """
    Gets the fully-qualified name of the type of this object.

    This is the package name, plus the module name, plus the class name (including parent
    classes for nested classes), joined by `.`s.  For builtin types or module-less types,
    the package and module portions are omitted.

    This implementation is indebted to https://stackoverflow.com/a/13653312/413345
    """
    return fully_qualified_name(obj.__class__)
