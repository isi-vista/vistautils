import argparse

USAGE = """
    text_at_offsets.py text_file start_offset_inclusive end_offset_exclusive

    Prints the text from text_file from the given start character offset (inclusive) to the given
    end character offset (exclusive). The file is treated as UTF-8 and character offsets are counted
    as Unicode codepoints.

    We read the entire file into memory for convenience. Typically files for NLP applications
    aren't big enough for this to be a problem.
"""


def main():
    parser = argparse.ArgumentParser(description=USAGE)
    parser.add_argument("text_file_path")
    parser.add_argument("start_offset_inclusive", type=int)
    parser.add_argument("end_offset_exclusive", type=int)
    args = parser.parse_args()

    start_offset_inclusive = args.start_offset_inclusive
    end_offset_exclusive = args.end_offset_exclusive

    with open(args.text_file_path, "r", encoding="utf-8", newline="\n") as text_file:
        # we read the entire file into memory for convenience. Typically files for NLP applications
        # aren't big enough for this to be a problem.
        text = text_file.read()
        if start_offset_inclusive < 0 or start_offset_inclusive >= len(text):
            print(
                f"Inclusive start offset out-of-bounds: {start_offset_inclusive} not in "
                f"[0:{len(text)})"
            )
        if end_offset_exclusive <= start_offset_inclusive or end_offset_exclusive > len(
            text
        ):
            print(
                f"Exclusive end offset out-of-bounds: {end_offset_exclusive} not in "
                f"({start_offset_inclusive}:{len(text)}]"
            )

        print(text[start_offset_inclusive:end_offset_exclusive])


if __name__ == "__main__":
    main()
