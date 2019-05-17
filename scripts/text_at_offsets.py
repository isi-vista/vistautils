import sys

USAGE = """
    text_at_offsets.py text_file start_offset_inclusive end_offset_exclusive
    
    Prints the text from text_file from the given start character offset to the given end
    character offset, inclusive. The file is treated as UTF-8 and character offsets are 
    counted as Unicode codepoints.

    We read the entire file into memory for convenience. Typically files for NLP applications
    aren't big enough for this to be a problem.
"""


def main():
    if len(sys.argv) != 4:
        print(USAGE)
        sys.exit(1)

    (_, text_file_path, start_offset_inclusive_string, end_offset_exclusive_string) = sys.argv

    try:
        start_offset_inclusive = int(start_offset_inclusive_string)
    except ValueError:
        print("The second argument must be an integer start offset (inclusive)")
        sys.exit(1)

    try:
        end_offset_exclusive = int(end_offset_exclusive_string)
    except ValueError:
        print("The third argument must be an integer end offset (inclusive)")
        sys.exit(1)

    with open(text_file_path, "r", encoding="utf-8", newline='\n') as text_file:
        # we read the entire file into memory for convenience. Typically files for NLP applications
        # aren't big enough for this to be a problem.
        text = text_file.read()
        if start_offset_inclusive < 0 or start_offset_inclusive >= len(text):
            print(f"Inclusive start offset out-of-bounds: {start_offset_inclusive} not in "
                  f"[0:{len(text)})")
        if end_offset_exclusive <= start_offset_inclusive or end_offset_exclusive > len(text):
            print(f"Exclusive end offset out-of-bounds: {end_offset_exclusive} not in "
                  f"({start_offset_inclusive}:{len(text)}]")

        print(text[start_offset_inclusive:end_offset_exclusive])


if __name__ == '__main__':
    main()
