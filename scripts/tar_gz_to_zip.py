import argparse
import os
import tarfile
from zipfile import ZipFile

USAGE = """
    Converts a (un)compressed tar file to .zip
    This is useful because .zip allows random access, but the LDC often distributes things as .tgz.
    zip version will be input name with .tar/.tar.gz/.tgz stripped (if present), .zip added
"""


def getargs():
    """Get command-line arguments."""
    parser = argparse.ArgumentParser(usage=USAGE)
    arg = parser.add_argument

    arg("tar_file_name", help="The input .tar/.tar.gz/.tgz file to be converted")

    arg(
        "--dont-stream",
        action="store_true",
        help="Should the tar contents be added to the zip file by unpacking "
        "them to disk first, rather than streaming them?",
    )

    arg(
        "--omit-large-files",
        action="store_true",
        help="Should large files (larger than LARGE_FILE_CUTOFF) not be "
        "transferred from the tar file to the zip file?",
    )

    arg(
        "--large-file-cutoff",
        type=float,
        default=2,
        help="Files larger than this cutoff (in gigabytes) will not be added"
        "to the zip file. The default is 2 gigabytes.",
    )

    return parser.parse_args()


def main():
    args = getargs()
    tar_file = args.tar_file_name
    output_zip_name = _output_name(tar_file)
    dont_stream = args.dont_stream
    omit_large_files = args.omit_large_files
    large_file_cutoff = args.large_file_cutoff * 1e9

    print(f"Copying tarball {tar_file} to {output_zip_name}")
    print(
        "WARNING: This will throw away all metadata. It also might not work "
        "if you have files with /s in the name or other odd things. "
        "Please sanity check your output"
    )

    if os.path.exists(output_zip_name):
        print(f"WARNING: Removing existing file at {output_zip_name}")
        os.remove(output_zip_name)

    with ZipFile(output_zip_name, "x") as out:
        with tarfile.open(tar_file) as inp:
            if dont_stream:
                inp.extractall()
                for member in inp:
                    if member.isfile():
                        out.write(member.name)
                    os.remove(member.name)
            else:
                for member in inp:
                    if member.isfile():
                        if omit_large_files and member.size > large_file_cutoff:
                            print(
                                f"WARNING: Omitting {member.name} as "
                                f"its size {member.size / 1e9:.2f} GB "
                                f"exceeds {args.large_file_cutoff:.2f} GB"
                            )
                        else:
                            print(f"Copying {member.name}")
                            with inp.extractfile(member) as data:
                                out.writestr(member.name, data.read())


def _output_name(filename: str) -> str:
    valid_extensions = [".tar", ".tgz", "tar.gz"]
    for valid_extension in valid_extensions:
        if filename.endswith(valid_extension):
            filename = filename[: len(filename) - len(valid_extension)]
            break

    return filename + ".zip"


if __name__ == "__main__":
    main()
