import subprocess
from app.infrastructure import storage


def test_prepare_disk_fallback(tmp_path, monkeypatch):
    base = tmp_path / "base.img"
    base.write_bytes(b"hello")

    # Force qemu-img to fail so code falls back to copy
    def fake_check_call(*args, **kwargs):
        raise Exception("qemu-img not available")

    monkeypatch.setattr("subprocess.check_call", fake_check_call)

    target = storage.prepare_disk(str(base), "vmtest", 1)
    assert target.endswith("vmtest.qcow2")
    tgt = tmp_path / "vmtest.qcow2"
    assert tgt.exists()
    assert tgt.read_bytes() == b"hello"
