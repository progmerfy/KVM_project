"""Unit tests for app.infrastructure.storage — disk creation/preparation/removal."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from app.infrastructure.storage import create_blank_disk, prepare_disk, remove_disk


class TestCreateBlankDisk:
    def test_create_qcow2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("subprocess.check_call") as mock_qemu:
                path = create_blank_disk("test-vm", 10, dest_dir=tmpdir)
                assert path == os.path.join(tmpdir, "test-vm.qcow2")
                mock_qemu.assert_called_once_with([
                    "qemu-img", "create", "-f", "qcow2", path, "10G"
                ])

    def test_create_raises_on_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = os.path.join(tmpdir, "dup.qcow2")
            open(existing, "w").close()
            with pytest.raises(FileExistsError):
                create_blank_disk("dup", 10, dest_dir=tmpdir)

    def test_create_creates_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "nested", "dirs")
            with patch("subprocess.check_call") as mock_qemu:
                path = create_blank_disk("deep", 5, dest_dir=subdir)
                assert os.path.isdir(subdir)
                mock_qemu.assert_called_once()


class TestPrepareDisk:
    def test_prepare_from_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "base.qcow2")
            open(base, "w").close()

            with patch("subprocess.check_call") as mock_qemu:
                target = prepare_disk(base, "clone-vm", 20)
                assert target == os.path.join(tmpdir, "clone-vm.qcow2")
                mock_qemu.assert_called_once_with([
                    "qemu-img", "create", "-f", "qcow2", "-b", base,
                    target, "20G",
                ])

    def test_prepare_fallback_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "base.qcow2")
            open(base, "w").close()

            with patch("subprocess.check_call", side_effect=Exception("qemu-img failed")):
                with patch("shutil.copy") as mock_copy:
                    target = prepare_disk(base, "fallback-vm", 10)
                    mock_copy.assert_called_once_with(base, target)

    def test_prepare_base_not_found(self):
        with pytest.raises(FileNotFoundError):
            prepare_disk("/nonexistent/base.qcow2", "vm", 10)

    def test_prepare_target_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "base.qcow2")
            open(base, "w").close()
            target = os.path.join(tmpdir, "vm.qcow2")
            open(target, "w").close()
            with pytest.raises(FileExistsError):
                prepare_disk(base, "vm", 10)


class TestRemoveDisk:
    def test_remove_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "remove-me.qcow2")
            open(fpath, "w").close()
            assert os.path.exists(fpath)
            remove_disk(fpath)
            assert not os.path.exists(fpath)

    def test_remove_nonexistent(self):
        remove_disk("/nonexistent/path.qcow2")
        # Should not raise

    def test_remove_none(self):
        remove_disk(None)
        # Should not raise
