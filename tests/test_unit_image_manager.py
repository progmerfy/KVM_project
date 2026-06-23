"""Unit tests for app.services.image_manager — list/get/delete/download operations."""

import os
import tempfile
import json
import pytest
from unittest.mock import patch, MagicMock

IMAGE_DIR = tempfile.mkdtemp()

# Patch _get_image_dir before importing
import app.services.image_manager
app.services.image_manager._get_image_dir = lambda: IMAGE_DIR

from app.services.image_manager import (
    list_images, get_image, delete_image,
    download_cloud_image, download_repo_iso,
    list_cloud_images, list_repo_images,
)
from app.errors import ServiceError


class TestListImages:
    def test_list_empty(self):
        images = list_images()
        assert images == []

    def test_list_with_files(self):
        fpath = os.path.join(IMAGE_DIR, "test.qcow2")
        open(fpath, "w").close()

        with patch("app.services.image_manager.subprocess.check_output") as mock_qemu:
            mock_qemu.return_value = json.dumps({
                "format": "qcow2",
                "virtual-size": 2147483648,
            })
            images = list_images()
            assert len(images) >= 1
            assert images[0].name == "test.qcow2"
            assert images[0].format == "qcow2"

        os.remove(fpath)

    def test_unsupported_extension_skipped(self):
        fpath = os.path.join(IMAGE_DIR, "test.txt")
        open(fpath, "w").close()

        images = list_images()
        names = [i.name for i in images]
        assert "test.txt" not in names

        os.remove(fpath)


class TestGetImage:
    def test_get_existing(self):
        fpath = os.path.join(IMAGE_DIR, "ubuntu.img")
        open(fpath, "w").close()

        with patch("app.services.image_manager.subprocess.check_output") as mock_qemu:
            mock_qemu.return_value = json.dumps({
                "format": "raw",
                "virtual-size": 1073741824,
            })
            img = get_image("ubuntu.img")
            assert img is not None
            assert img.name == "ubuntu.img"
            assert img.format == "raw"

        os.remove(fpath)

    def test_get_nonexistent(self):
        img = get_image("nonexistent.qcow2")
        assert img is None


class TestDeleteImage:
    def test_delete_existing(self):
        fpath = os.path.join(IMAGE_DIR, "delete-me.qcow2")
        open(fpath, "w").close()
        assert os.path.isfile(fpath)

        delete_image("delete-me.qcow2")
        assert not os.path.isfile(fpath)

    def test_delete_nonexistent(self):
        with pytest.raises(ServiceError) as exc:
            delete_image("ghost.qcow2")
        assert exc.value.http_status == 404

    def test_delete_service_error_code(self):
        with pytest.raises(ServiceError) as exc:
            delete_image("ghost.qcow2")
        assert exc.value.code == "IMAGE_NOT_FOUND"


class TestDownloadCloudImage:
    def test_download_success(self):
        with patch("app.services.image_manager.subprocess.check_call") as mock_curl, \
             patch("app.services.image_manager.subprocess.check_output") as mock_qemu:
            mock_qemu.return_value = json.dumps({
                "format": "qcow2",
                "virtual-size": 2147483648,
            })

            def curl_side_effect(args, **kw):
                for i, a in enumerate(args):
                    if a == "-o" and i + 1 < len(args):
                        open(args[i + 1], "w").close()
                return MagicMock()

            mock_curl.side_effect = curl_side_effect
            img = download_cloud_image("ubuntu-24.04")
            assert img.format == "qcow2"

    def test_download_unknown(self):
        with pytest.raises(ServiceError) as exc:
            download_cloud_image("nonexistent-os")
        assert exc.value.http_status == 404
        assert exc.value.code == "CLOUD_IMAGE_NOT_FOUND"

    def test_download_already_exists(self):
        dest = os.path.join(IMAGE_DIR, "noble-server-cloudimg-amd64.img")
        open(dest, "w").close()

        with patch("app.services.image_manager.subprocess.check_output") as mock_qemu:
            mock_qemu.return_value = json.dumps({
                "format": "qcow2",
                "virtual-size": 2147483648,
            })
            img = download_cloud_image("ubuntu-24.04")
            assert img.format == "qcow2"

        os.remove(dest)

    def test_download_failure(self):
        # Remove any existing dest that would skip the download
        dest = os.path.join(IMAGE_DIR, "noble-server-cloudimg-amd64.img")
        if os.path.isfile(dest):
            os.remove(dest)

        with patch("app.services.image_manager.subprocess.check_call", side_effect=Exception("network err")):
            with pytest.raises(ServiceError) as exc:
                download_cloud_image("ubuntu-24.04")
            assert exc.value.code == "DOWNLOAD_FAILED"

    def test_download_invalid_file(self):
        dest = os.path.join(IMAGE_DIR, "noble-server-cloudimg-amd64.img")
        if os.path.isfile(dest):
            os.remove(dest)

        with patch("app.services.image_manager.subprocess.check_call") as mock_curl, \
             patch("app.services.image_manager.subprocess.check_output", side_effect=Exception("bad file")):

            def curl_side_effect(args, **kw):
                for i, a in enumerate(args):
                    if a == "-o" and i + 1 < len(args):
                        open(args[i + 1], "w").close()
                return MagicMock()

            mock_curl.side_effect = curl_side_effect
            with pytest.raises(ServiceError) as exc:
                download_cloud_image("ubuntu-24.04")
            assert exc.value.code == "INVALID_IMAGE"


class TestDownloadRepoISO:
    def test_download_iso(self):
        dest = os.path.join(IMAGE_DIR, "ubuntu-24.04.4-live-server-amd64.iso")
        if os.path.isfile(dest):
            os.remove(dest)

        with patch("app.services.image_manager.subprocess.check_call") as mock_curl, \
             patch("app.services.image_manager.subprocess.check_output") as mock_qemu:
            mock_qemu.return_value = json.dumps({
                "format": "iso",
                "virtual-size": 4700000000,
            })

            def curl_side_effect(args, **kw):
                for i, a in enumerate(args):
                    if a == "-o" and i + 1 < len(args):
                        open(args[i + 1], "w").close()
                return MagicMock()

            mock_curl.side_effect = curl_side_effect
            img = download_repo_iso("ubuntu-24.04-server")
            assert img.format == "iso"

    def test_download_iso_unknown(self):
        with pytest.raises(ServiceError) as exc:
            download_repo_iso("nonexistent-iso")
        assert exc.value.http_status == 404
        assert exc.value.code == "REPO_ISO_NOT_FOUND"


class TestListRepoImages:
    def test_list_cloud_images(self):
        result = list_cloud_images()
        assert "ubuntu-24.04" in result
        assert "url" in result["ubuntu-24.04"]
        assert "description" in result["ubuntu-24.04"]

    def test_list_repo_images_structure(self):
        result = list_repo_images()
        assert isinstance(result, dict)
        families = list(result.keys())
        assert len(families) > 0
        for fam, items in result.items():
            for item in items:
                assert "name" in item
                assert "type" in item
                assert "is_iso" in item
                assert item["type"] in ("cloud", "iso")
                assert isinstance(item["is_iso"], bool)
