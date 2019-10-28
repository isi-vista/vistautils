"""
Code for applying HTML-like markup to text.

This is useful for rendering NLP annotations to users.

Adapted from ``edu.isi.nlp.strings.formatting`` from https://github.com/isi-vista/nlp-util, which
is itself derived from code from BBN Technologies.
"""
import io
import itertools
from typing import Collection, Iterable, List, Mapping, Optional

from attr import attrib, attrs, evolve
from attr.validators import instance_of

from immutablecollections import immutabledict

from vistautils.preconditions import check_arg
from vistautils.span import Span

DIV = "div"
SPAN = "span"


@attrs(frozen=True, slots=True)
class AnnotatedSpan:
    """
    An HTML-like annotation applied to a span of offsets.

    The label is the primary label to be applied to the region.
    Additionally, key-value metadata (attributes) can be applied.

    When rendered as HTML, the primary label will become the tag and the metadata will
    becomes attributes.
    """

    label: str = attrib(validator=instance_of(str))
    span: Span = attrib(validator=instance_of(Span))
    attributes: Mapping[str, str] = attrib(
        default=immutabledict(), converter=immutabledict
    )

    @staticmethod
    def create_div_of_class(span: Span, clazz: str) -> "AnnotatedSpan":
        return AnnotatedSpan(DIV, span, {"class": clazz})

    @staticmethod
    def create_span_of_class(span: Span, clazz: str) -> "AnnotatedSpan":
        return AnnotatedSpan(SPAN, span, {"class": clazz})


def to_start_tag(annotated_range: AnnotatedSpan) -> str:
    """
    Make the start tag of an HTML element from an `AnnotatedSpan`
    """
    key_value_string = " ".join(
        f'{k}="{v}"' for (k, v) in sorted(annotated_range.attributes.items())
    )
    attributes_string = (" " + key_value_string) if annotated_range.attributes else ""
    return f"<{annotated_range.label}{attributes_string}>"


def to_end_tag(annotated_range: AnnotatedSpan) -> str:
    """
    Make the end tag of an HTML element from an `AnnotatedOffsetRange`
    """
    return f"</{annotated_range.label}>"


@attrs(frozen=True, slots=True)
class HTMLStyleAnnotationFormatter:
    def annotated_text(
        self,
        text: str,
        annotations: Collection[AnnotatedSpan],
        *,
        text_offsets: Optional[Span] = None,
    ) -> str:
        """
        Mark annotations on text in an HTML-like style.

        Each annotation will becomes an HTML tag wrapping the text at the corresponding offsets.
        Any attributes will become HTML attributes.

        This does not add any other HTML annotations (`head`, `body`, etc.), so if desired the
        user should add them afterwards.

        If `text_offsets` is specified, the annotations are assumed to have offsets with respect
        to some larger string, where `text` is a substring of that string with offsets
        `text_offsets` relative to it.  You might use this, for example, to render a single
        paragraph from a document.
        """
        if not text_offsets:
            text_offsets = Span.from_inclusive_to_exclusive(0, len(text))
        check_arg(
            len(text_offsets) == len(text),
            f"Text offsets length {len(text_offsets)} "
            f"does not match text length {len(text)}",
        )

        # we process the annotations to (a) ensure they all fit within the requested snippet
        # and (b) shift their offsets so that all offsets are relative to the text being
        # formatted
        processed_annotations = self._clip_to_offsets_and_shift(annotations, text_offsets)

        ret = io.StringIO()
        last_uncopied_offset = 0
        for tag in self._tag_sequence(processed_annotations):
            if last_uncopied_offset < tag.offset:
                ret.write(text[last_uncopied_offset : tag.offset])
                last_uncopied_offset = tag.offset

            ret.write(tag.string)

        # get any trailing text after last tag
        if last_uncopied_offset < text_offsets.end:
            ret.write(text[last_uncopied_offset : text_offsets.end])
        return ret.getvalue()

    @staticmethod
    def _clip_to_offsets_and_shift(
        unclipped_annotations: Collection[AnnotatedSpan], text_offsets: Span
    ) -> List[AnnotatedSpan]:
        """
        Clip or filter out annotations to ensure all are within the text being formatted.
        """
        # there are three cases:
        #    (a) an annotation is entirely contained in the text range being formatted and
        #              doesn't need alteration.
        #    (b) an annotation is partly contained in the text range being formatted and needs
        #              to be trimmed to git.
        #    (c) an annotation lies entirely outside the text range being formatted and should
        #              be omitted
        ret: List[AnnotatedSpan] = []
        for unclipped_annotation in unclipped_annotations:
            clipped_annotation_span = unclipped_annotation.span.clip_to(text_offsets)
            if clipped_annotation_span:
                # this is both cases a and b - in case (a) `clip_to` above returns the span
                # unchanged
                # we now need to shift the annotation offsets so that they are relative to the
                # snippet being formatted
                shifted_annotation_span = clipped_annotation_span.shift(
                    -text_offsets.start
                )
                ret.append(evolve(unclipped_annotation, span=shifted_annotation_span))
            # otherwise, we are in case (c) and we drop the annotation
        return ret

    @attrs(frozen=True, slots=True)
    class Tag:
        string: str = attrib(validator=instance_of(str))
        is_start: bool = attrib(validator=instance_of(bool))
        offset: int = attrib(validator=instance_of(int))

    @staticmethod
    def _tag_sequence(
        annotations: Collection[AnnotatedSpan]
    ) -> Iterable["HTMLStyleAnnotationFormatter.Tag"]:
        """
        Provide the tags in order of their occurrence in the formatted text.

        Each step yields a triple of a tag name, whether or not it is a start tag (a boolean),
        and the offset of the beginning of the tag.
        """

        # for start tags, we want to break ties by longest length so that tags which end later
        # start first. This preserves proper nesting.
        def start_tag_key(annotation):
            return annotation.span.start, -len(annotation.span)

        # for end tags, we want to break ties by shortest length so that tags which start later
        # end earlier. This preserves proper nesting.
        def end_tag_key(annotation):
            return annotation.span.end, len(annotation.span)

        start_tags = (
            HTMLStyleAnnotationFormatter.Tag(to_start_tag(ann), True, ann.span.start)
            for ann in sorted(annotations, key=start_tag_key)
        )
        end_tags = (
            HTMLStyleAnnotationFormatter.Tag(to_end_tag(ann), False, ann.span.end)
            for ann in sorted(annotations, key=end_tag_key)
        )

        # interleave the start and end tag lists
        # when start and end tags are attached to the same offset, put the ends tags first
        # to avoid crossing elements
        # "sorted" is stable so the relative order of start and end tags is maintained
        return sorted(
            itertools.chain(end_tags, start_tags),
            # True is less than False, which is fine because we want end tags
            # before start tags,
            key=lambda tag: (tag.offset, tag.is_start),
        )
