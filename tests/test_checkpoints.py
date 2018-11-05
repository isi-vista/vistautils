import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from vistautils.checkpoints import Checkpoints


class TestCheckpoints(TestCase):
    def test_filesystem_checkpoints(self):
        tmp_dir = Path(tempfile.mkdtemp())

        checkpoints = Checkpoints.from_directory(tmp_dir)
        checkpoints.set("fred")
        checkpoints.set("bob")

        other_checkpoints = Checkpoints.from_directory(tmp_dir)
        self.assertTrue("fred" in checkpoints)
        self.assertTrue("bob" in checkpoints)
        self.assertFalse("moo" in checkpoints)
        other_checkpoints.reset_all()
        self.assertFalse("fred" in checkpoints)
        self.assertFalse("bob" in checkpoints)
        self.assertFalse("moo" in checkpoints)

        shutil.rmtree(str(tmp_dir))
