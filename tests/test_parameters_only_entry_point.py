from pathlib import Path

from vistautils.parameters import Parameters
from vistautils.parameters_only_entrypoint import _real_parameters_only_entry_point


def sample_main(params: Parameters):
    assert params.string("only_original") == "foo"
    assert params.string("only_cli") == "bar"
    assert params.string("overridden") == "hello"
    assert params.namespace("nested").string("overridden") == "I've been overridden"


def test_parameters_only_entry_point(tmp_path: Path):
    original_param_file = tmp_path / "test.params"

    original_param_file.write_text(
        'only_original: foo\noverridden: goodbye\nnested:\n  overridden: "I\'ve been overridden"',
        encoding="utf-8",
    )

    _real_parameters_only_entry_point(
        sample_main,
        program_name="test",
        args=[
            str(original_param_file.absolute()),
            "-p",
            "only_cli",
            "bar",
            "-p",
            "overridden",
            "hello",
            "-p",
            "nested.overridden",
            "I've been overridden",
        ],
    )
