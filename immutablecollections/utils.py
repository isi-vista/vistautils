from attr.exceptions import FrozenInstanceError


class ImmutableMixin:

    def __setattr__(self, key, value):
        raise FrozenInstanceError('Object is immutable')

    def __delattr__(self, item):
        raise FrozenInstanceError('Object is immutable')
