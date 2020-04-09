import inspect
from types import ModuleType
from typing import Any, Union, cast


def fully_qualified_name(class_or_module: Union[type, ModuleType]) -> str:
    """
    Gets the fully-qualified name of a class or module.

    For a module, this is the package name and module name.

    For a class, this is the package name, plus the module name, plus the class name
    (including parent classes for nested classes), joined by `.`s.
    For builtin types or module-less types, the package and module portions are omitted.

    This implementation is indebted to https://stackoverflow.com/a/13653312/413345
    """
    # Modules do not themselves have modules, so we need to check for that first.
    if inspect.ismodule(class_or_module):
        return class_or_module.__name__
    else:
        clazz = cast(type, class_or_module)
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
