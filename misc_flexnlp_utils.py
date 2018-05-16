import re
import time
from typing import Any, Type

from flexnlp.model.document import Document
from flexnlp.model.theory import Theory

_WHITESPACE_RE = re.compile(r'\s+')


def normalize_whitespace(s):
    """
    Normalizes newlines to spaces, squishes consecutive spaces into a
    single space, and trims leading/trailing whitespace.
    :param s: input string
    :return: normalized string
    """
    return _WHITESPACE_RE.sub(' ', s).strip()


def get_utf8_to_char_map(utf8_bytes):
    """
    Returns a map of utf-8 byte offsets to character offsets for the start
    of each character.  The map also includes an entry for one past the end
    of the last character.

    This is useful for things like syntaxnet which return offsets in terms
    of utf-8 bytes.

    :param utf8_bytes:
    :return: map of utf-8 offsets to character offsets
    """
    byte_offset = 0
    char_offset = 0
    m = {0: 0}
    while byte_offset < len(utf8_bytes):
        m[byte_offset] = char_offset
        b = utf8_bytes[byte_offset]
        if b & 0b10000000 == 0b00000000:
            continuation_bytes = 0
        elif b & 0b11100000 == 0b11000000:
            continuation_bytes = 1
        elif b & 0b11110000 == 0b11100000:
            continuation_bytes = 2
        elif b & 0b11111000 == 0b11110000:
            continuation_bytes = 3
        else:
            raise Exception('invalid utf-8 at offset {}: {}'.format(
                byte_offset, utf8_bytes))
        for i in range(1, continuation_bytes):
            b = utf8_bytes[byte_offset + i]
            if b & 0b11000000 != 0b10000000:
                raise Exception('invalid utf-8 at offset {}: {}'.format(
                    byte_offset + 1, utf8_bytes))
        byte_offset += 1 + continuation_bytes
        char_offset += 1
    m[byte_offset] = char_offset
    return m


def get_utf16_to_char_map(s):
    """
    Returns a map of utf-16 element offsets to character offsets for the start
    of each character.  The map also includes an entry for one past the end
    of the last character.

    This is useful for interfacing to things like CoreNLP, which return
    offsets in terms of utf-16 elements.

    :param s:
    :return: map of utf-16 element offsets to character offsets
    """
    m = {0: 0}
    utf16_offset = 0
    i = 0
    while i < len(s):
        c = s[i]
        m[utf16_offset] = i
        if ord(c) & 0xffff0000:
            utf16_offset += 1
        utf16_offset += 1
        i += 1
    m[utf16_offset] = i
    return m


def get_char_to_utf16_map(s):
    """
    Returns a map of character offsets to utf-16 element offset.  The map also
    includes an entry for one past the end of the last character.

    This is useful for interfacing to things like CoreNLP, which return
    offsets in terms of utf-16 elements.

    :param s:
    :return: map of character offsets to utf-16 element offsets
    """
    return {v: k for k, v in get_utf16_to_char_map(s).items()}


def fully_qualified_name(obj: Any) -> str:
    if isinstance(obj, type):
        cls = obj
    elif hasattr(obj, '__class__'):
        cls = obj.__class__
    else:
        raise TypeError('not a class or instance')
    return '{}.{}'.format(cls.__module__, cls.__qualname__)


# TODO: Use correct type hint for input_theory_ids (circular import problem with TheoryIdMap)
def text_span_iterator(doc: Document, use_regions: bool, use_sentences: bool):
    """
    Return an iterator over consecutive, ordered spans of text.

    The returned spans cover the entire doc.text.  If region
    theory ids are passed, no span cross the boundary of a region
    with ``region.breaking == True``.  If sentence theory ids are
    passed, no span will cross a sentence boundary.

    :param doc:
    :param input_theory_ids:
    :param use_regions:
    :param use_sentences:
    :return: iterator over spans of text that do not cross
     region or sentence boundaries. Spans are inclusive on both ends.
    """
    boundary_set = {0, len(doc.text.text)}
    if use_regions:
        for regions in doc.all_regions():
            for r in regions:
                if r.breaking:
                    boundary_set.add(r.start)
                    boundary_set.add(r.end)
    if use_sentences:
        for s in doc.sentences():
            boundary_set.add(s.start)
            boundary_set.add(s.end)

    boundary_list = list(boundary_set)
    boundary_list.sort()
    spans = [(boundary_list[i], boundary_list[i + 1])
             for i in range(len(boundary_list) - 1)]
    return iter(spans)


# from Python Cookbook 13.13
class Timer:
    def __init__(self, func=time.perf_counter):
        self.elapsed = 0.0
        self._func = func
        self._start = None

    def start(self):
        if self._start is not None:
            raise RuntimeError('Already started')
        self._start = self._func()

    def stop(self):
        if self._start is None:
            raise RuntimeError('Not started')
        end = self._func()
        self.elapsed += end - self._start
        self._start = None

    def reset(self):
        self.elapsed = 0.0

    @property
    def running(self):
        return self._start is not None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
