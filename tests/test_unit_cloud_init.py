"""Unit tests for app.services.cloud_init — cloud-init ISO generation."""

import os
import tempfile
from unittest.mock import patch, MagicMock


CI_DIR = tempfile.mkdtemp()

import app.services.cloud_init
app.services.cloud_init._get_cloudinit_dir = lambda: CI_DIR

from app.services.cloud_init import build_cloudinit_iso, cleanup_cloudinit_iso


def _geniso_side_effect(args, **kw):
    """Mock genisoimage: find -output arg and create stub file."""
    for i, a in enumerate(args):
        if a == "-output" and i + 1 < len(args):
            os.makedirs(os.path.dirname(args[i + 1]), exist_ok=True)
            open(args[i + 1], "w").close()
            return MagicMock()
    raise RuntimeError(f"unexpected genisoimage call: {args}")


class TestCloudInitISO:
    def test_build_with_ssh_key(self):
        with patch("subprocess.check_call", side_effect=_geniso_side_effect):
            iso_path = build_cloudinit_iso(
                vm_name="test-vm",
                ssh_public_key="ssh-ed25519 AAAAC3... user@host",
                username="admin",
            )
        assert iso_path.endswith("test-vm-cloudinit.iso")
        assert os.path.exists(iso_path)

    def test_build_with_user_data(self):
        with patch("subprocess.check_call", side_effect=_geniso_side_effect):
            iso_path = build_cloudinit_iso(
                vm_name="vm-ud",
                user_data_raw="#cloud-config\nruncmd:\n  - echo hello",
            )
        assert os.path.exists(iso_path)

    def test_build_with_root_password(self):
        with patch("subprocess.check_call", side_effect=_geniso_side_effect):
            iso_path = build_cloudinit_iso(
                vm_name="vm-pass",
                ssh_public_key="ssh-ed25519 KEY",
                root_password="myrootpass123",
            )
        assert os.path.exists(iso_path)

    def test_build_with_network_config(self):
        with patch("subprocess.check_call", side_effect=_geniso_side_effect):
            iso_path = build_cloudinit_iso(
                vm_name="vm-net",
                ssh_public_key="ssh-ed25519 KEY",
                network_config="version: 2\nethernets:\n  eth0:\n    dhcp4: true",
            )
        assert os.path.exists(iso_path)

    def test_build_no_ssh_no_user_data(self):
        with patch("subprocess.check_call", side_effect=_geniso_side_effect):
            iso_path = build_cloudinit_iso(vm_name="vm-minimal")
        assert os.path.exists(iso_path)

    def test_build_failure_logs_error(self):
        import subprocess
        with patch("subprocess.check_call", side_effect=subprocess.CalledProcessError(1, "genisoimage")):
            import pytest
            with pytest.raises(Exception):
                build_cloudinit_iso(vm_name="vm-fail", ssh_public_key="ssh-ed25519 KEY")

    def test_cleanup_removes_iso(self):
        with patch("subprocess.check_call", side_effect=_geniso_side_effect):
            iso_path = build_cloudinit_iso(vm_name="vm-cleanup", ssh_public_key="key")
        assert os.path.exists(iso_path)
        cleanup_cloudinit_iso("vm-cleanup")
        assert not os.path.exists(iso_path)

    def test_cleanup_nonexistent(self):
        cleanup_cloudinit_iso("nonexistent-vm")

    def test_get_cloudinit_dir(self):
        from app.services.cloud_init import _get_cloudinit_dir
        ci_dir = _get_cloudinit_dir()
        assert ci_dir == CI_DIR
        assert os.path.isdir(ci_dir)

    def test_build_with_hostname(self):
        with patch("subprocess.check_call", side_effect=_geniso_side_effect):
            iso_path = build_cloudinit_iso(
                vm_name="vm-hn",
                ssh_public_key="key",
                hostname="my-custom-host",
            )
        assert iso_path.endswith("vm-hn-cloudinit.iso")
        assert os.path.exists(iso_path)
