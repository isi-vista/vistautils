# why does itertools think these are useful enough to put in the documentation but not in
# the library?
from itertools import tee


# from itertools docs
def tile_with_pairs(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)
