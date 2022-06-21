from unittest import TestCase

from vistautils.annotated_text_utils import AnnotatedSpan, HTMLStyleAnnotationFormatter
from vistautils.span import Span


class TestAnnotatedTextUtils(TestCase):
    def test_format(self):
        # we show how we can format a snippet (below) when the
        # annotations are relative to a larger enclosing text
        original_text = (
            "Eliot: Time present and time past / "
            "Are both perhaps present in time future..."
        )
        snippet_text = (
            "Time present and time past / Are both perhaps present in time future..."
        )

        annotations = [
            AnnotatedSpan("SIR_NOT_APPEARING_IN_THIS_SNIPPET", Span(1, 5)),
            AnnotatedSpan("LINE", Span(7, 33)),
            AnnotatedSpan("BAR", Span(8, 9)),
            AnnotatedSpan("LINE", Span(36, 75)),
            AnnotatedSpan("PP", Span(61, 75)),
            AnnotatedSpan("ELLIPSES", Span(75, 78)),
            AnnotatedSpan("FOO", Span(7, 19)),
            AnnotatedSpan("SINGLE_CHAR", Span(61, 62)),
        ]

        expected_result = (
            "<LINE><FOO>T<BAR>i</BAR>me present</FOO> and time past</LINE> "
            "/ <LINE>Are both perhaps present <PP><SINGLE_CHAR>i</SINGLE_CHAR>n "
            "time future</PP></LINE><ELLIPSES>...</ELLIPSES>"
        )

        self.assertEqual(
            expected_result,
            HTMLStyleAnnotationFormatter().annotated_text(
                snippet_text, annotations, text_offsets=Span(7, len(original_text))
            ),
        )
