"""Unit tests for app.models and app.api.schemas — Pydantic model validation."""

import pytest
from pydantic import ValidationError

from app.models.image import ImageInfo, CloudImageInfo
from app.models.vm_spec import VMSpec
from app.api.schemas import (
    VMCreateRequest, VMActionRequest, VMISORequest, VMResizeRequest,
    VMAttachDiskRequest, VMDetachDiskRequest, VMSnapshotRequest,
    VMNetworkRequest, VMImportRequest, VMCloneRequest, VMBackupRequest,
    VMRestoreRequest,
)


class TestImageInfo:
    def test_minimal(self):
        img = ImageInfo(name="test.img", path="/tmp/test.img", format="qcow2", virtual_size_gb=10, actual_size_bytes=1073741824)
        assert img.name == "test.img"
        assert img.virtual_size_gb == 10.0

    def test_with_optional_fields(self):
        img = ImageInfo(
            name="test.img", path="/tmp/test.img", format="qcow2",
            virtual_size_gb=20, actual_size_bytes=2147483648,
            backing_file="/base.qcow2", mtime=1234567890.0, ctime=1234567890.0,
        )
        assert img.backing_file == "/base.qcow2"
        assert img.mtime == 1234567890.0

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            ImageInfo()

    def test_serialize(self):
        img = ImageInfo(name="x.iso", path="/pool/x.iso", format="iso", virtual_size_gb=4.7, actual_size_bytes=5000000000)
        d = img.model_dump()
        assert d["name"] == "x.iso"
        assert d["format"] == "iso"


class TestCloudImageInfo:
    def test_create(self):
        ci = CloudImageInfo(name="ubuntu-24.04", url="https://cloud-images.ubuntu.com/...", description="Ubuntu 24.04")
        assert ci.name == "ubuntu-24.04"


class TestVMSpec:
    def test_minimal(self):
        spec = VMSpec(name="vm1", cpu=2, memory_mb=2048, disk_gb=20, image="/img.qcow2")
        assert spec.name == "vm1"

    def test_with_optional(self):
        spec = VMSpec(
            name="vm2", cpu=4, memory_mb=4096, disk_gb=50,
            image=None, iso_path="/iso/debian.iso",
            cloud_init_iso="/ci.iso", network="my-net",
        )
        assert spec.iso_path == "/iso/debian.iso"
        assert spec.cloud_init_iso == "/ci.iso"
        assert spec.network == "my-net"


class TestVMCreateRequest:
    def test_valid(self):
        r = VMCreateRequest(name="test-vm", cpu=2, memory_mb=2048, disk_gb=20, image="/img.qcow2")
        assert r.name == "test-vm"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            VMCreateRequest(name="", cpu=1, memory_mb=512, disk_gb=10)

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            VMCreateRequest(name="a" * 65, cpu=1, memory_mb=512, disk_gb=10)

    def test_cpu_bounds(self):
        with pytest.raises(ValidationError):
            VMCreateRequest(name="vm", cpu=0, memory_mb=512, disk_gb=10)
        with pytest.raises(ValidationError):
            VMCreateRequest(name="vm", cpu=65, memory_mb=512, disk_gb=10)

    def test_memory_bounds(self):
        with pytest.raises(ValidationError):
            VMCreateRequest(name="vm", cpu=1, memory_mb=64, disk_gb=10)
        with pytest.raises(ValidationError):
            VMCreateRequest(name="vm", cpu=1, memory_mb=999999, disk_gb=10)

    def test_disk_bounds(self):
        with pytest.raises(ValidationError):
            VMCreateRequest(name="vm", cpu=1, memory_mb=512, disk_gb=0)
        with pytest.raises(ValidationError):
            VMCreateRequest(name="vm", cpu=1, memory_mb=512, disk_gb=99999)

    def test_default_values(self):
        r = VMCreateRequest(name="vm", image="/img.qcow2")
        assert r.cpu == 1
        assert r.memory_mb == 512
        assert r.disk_gb == 10
        assert r.network == "default"
        assert r.cloud_init_user == "user"

    def test_cloud_init_user_data_overrides_ssh_key(self):
        r = VMCreateRequest(name="vm", image="/img.qcow2", cloud_init_ssh_key="ssh-ed25519 AAA...", cloud_init_user_data="#cloud-config\nruncmd:\n  - echo hi")
        assert r.cloud_init_ssh_key == "ssh-ed25519 AAA..."
        assert r.cloud_init_user_data is not None


class TestSchemas:
    def test_vm_action_request(self):
        r = VMActionRequest(name="test-vm")
        assert r.name == "test-vm"

    def test_vm_iso_request(self):
        r = VMISORequest(name="vm", iso_path="/iso/debian.iso")
        assert r.iso_path == "/iso/debian.iso"

    def test_vm_resize_request(self):
        r = VMResizeRequest(name="vm", cpu=4, memory_mb=8192, disk_gb=100)
        assert r.cpu == 4

    def test_attach_disk_request(self):
        r = VMAttachDiskRequest(name="vm", size_gb=50, target_dev="vdb")
        assert r.target_dev == "vdb"

    def test_detach_disk_request(self):
        r = VMDetachDiskRequest(name="vm", target_dev="vdb")
        assert r.target_dev == "vdb"

    def test_snapshot_request(self):
        r = VMSnapshotRequest(name="vm", snap_name="snap1")
        assert r.snap_name == "snap1"

    def test_network_request(self):
        r = VMNetworkRequest(name="my-net", bridge="virbr1", subnet="10.0.0.0/24")
        assert r.subnet == "10.0.0.0/24"

    def test_import_request(self):
        r = VMImportRequest(xml="<domain><name>vm</name></domain>")
        assert r.xml is not None

    def test_clone_request(self):
        r = VMCloneRequest(name="src", new_name="dst")
        assert r.new_name == "dst"

    def test_backup_request(self):
        r = VMBackupRequest(name="vm")
        assert r.name == "vm"

    def test_restore_request(self):
        r = VMRestoreRequest(backup_dir="/backups/vm_20240101")
        assert r.backup_dir == "/backups/vm_20240101"
