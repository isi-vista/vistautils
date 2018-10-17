import sys
import tarfile
from zipfile import ZipFile

USAGE = """
usage: tar_gz_to_zip tar_gz_file_name
    Converts a gzip'd tar file to .zip
    This is useful because .zip allows random access, but the LDC often distributes things as .tgz.
    zip version will be input name with .tar.gz/.tgz stripped (if present), .zip added
"""


def main():
    if len(sys.argv) != 2:
        print(USAGE)
        sys.exit(1)
    tar_gz_file = sys.argv[1]
    output_zip_name = _output_name(tar_gz_file)

    print(f"Copying .tar.gz file {tar_gz_file} to {output_zip_name}")
    print("WARNING: This will throw away all metadata. It also might not work if you "
          "have files with /s in the name or other odd things. Please sanity check your output")

    with ZipFile(output_zip_name, 'x') as out:
        with tarfile.open(tar_gz_file) as inp:
            for member in inp:
                if member.isfile():
                    print(f"Copying {member.name}")
                    with inp.extractfile(member) as data:
                        out.writestr(member.name, data.read())


def _output_name(filename: str) -> str:
    if filename.endswith(".tgz"):
        filename = filename[:len(filename) - len(".tgz")]
    elif filename.endswith(".tar.gz"):
        filename = filename[:len(filename) - len(".tar.gz")]

    return filename + ".zip"


if __name__ == '__main__':
    main()
