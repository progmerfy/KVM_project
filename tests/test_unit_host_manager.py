"""Unit tests for app.services.host_manager — /proc parsing and subprocess stubs."""

import os
import pytest
from unittest.mock import patch, mock_open

os.environ["COLUMNS"] = "80"  # prevent subprocess issues

from app.services.host_manager import (
    get_host_info, get_host_stats,
    _get_uptime, _get_hostname, _get_cpu_info, _get_memory_info,
    _get_storage_info, _get_cpu_usage, _get_memory_usage, _get_storage_usage,
)


MOCK_CPUINFO = """processor\t: 0
vendor_id\t: GenuineIntel
cpu family\t: 6
model\t\t: 158
model name\t: Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz
stepping\t: 10
"""

MOCK_MEMINFO = """MemTotal:       16384000 kB
MemFree:         8192000 kB
MemAvailable:   10000000 kB
Buffers:         1024000 kB
Cached:          2048000 kB
"""

MOCK_STAT = "cpu  12345 678 9012 345678 0 0 0 0 0 0\n"


class TestHostManager:
    def test_get_hostname(self):
        with patch("os.uname") as mock_uname:
            mock_uname.return_value.nodename = "test-host"
            assert _get_hostname() == "test-host"

    def test_get_hostname_fallback(self):
        with patch("os.uname", side_effect=Exception):
            assert _get_hostname() == "unknown"

    def test_get_uptime(self):
        with patch("builtins.open", mock_open(read_data="123456.78 98765.43\n")):
            up = _get_uptime()
            assert up == "1d 10h 17m"

    def test_get_uptime_hours_only(self):
        with patch("builtins.open", mock_open(read_data="3600.0 1800.0\n")):
            assert _get_uptime() == "1h 0m"

    def test_get_uptime_failure(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert _get_uptime() is None

    def test_get_cpu_info_with_nproc(self):
        with patch("subprocess.check_output") as mock_nproc, \
             patch("builtins.open", mock_open(read_data=MOCK_CPUINFO)):
            mock_nproc.return_value = "8\n"
            info = _get_cpu_info()
            assert info["cores"] == 8
            assert "i7-8700K" in info["model"]

    def test_get_cpu_info_nproc_fails(self):
        with patch("subprocess.check_output", side_effect=Exception), \
             patch("builtins.open", mock_open(read_data=MOCK_CPUINFO)):
            info = _get_cpu_info()
            assert info["cores"] == 0
            assert "i7-8700K" in info["model"]

    def test_get_cpu_info_no_cpuinfo(self):
        with patch("subprocess.check_output") as mock_nproc, \
             patch("builtins.open", side_effect=[FileNotFoundError]):
            mock_nproc.return_value = "4\n"
            info = _get_cpu_info()
            assert info["cores"] == 4
            assert info["model"] == "unknown"

    def test_get_memory_info(self):
        with patch("builtins.open", mock_open(read_data=MOCK_MEMINFO)):
            info = _get_memory_info()
            assert info["total_mb"] == 16000
            assert info["total_gb"] == 15.6

    def test_get_memory_info_failure(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            info = _get_memory_info()
            assert info["total_mb"] == 0

    def test_get_storage_info(self):
        fake_df = """Source FSType Size Used Avail Target
/dev/sda1 ext4 107374182400 53687091200 53687091200 /
/dev/sdb1 xfs 214748364800 107374182400 107374182400 /data
"""
        with patch("subprocess.check_output") as mock_df:
            mock_df.return_value = fake_df
            info = _get_storage_info()
            assert len(info) >= 2
            assert info[0]["filesystem"] == "/dev/sda1"
            assert info[0]["size_gb"] == 100.0

    def test_get_storage_info_filters_tmpfs(self):
        fake_df = """Source FSType Size Used Avail Target
tmpfs tmpfs 1048576 0 1048576 /run
/dev/sda1 ext4 107374182400 0 107374182400 /
"""
        with patch("subprocess.check_output") as mock_df:
            mock_df.return_value = fake_df
            info = _get_storage_info()
            assert len(info) == 1
            assert info[0]["filesystem"] == "/dev/sda1"

    def test_get_storage_info_failure(self):
        with patch("subprocess.check_output", side_effect=FileNotFoundError):
            assert _get_storage_info() == []

    def test_get_cpu_usage(self):
        with patch("builtins.open", mock_open(read_data=MOCK_STAT)):
            info = _get_cpu_usage()
            assert info["used_percent"] > 0
            assert info["idle_percent"] > 0
            assert round(info["used_percent"] + info["idle_percent"], 1) == 100.0

    def test_get_cpu_usage_failure(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert _get_cpu_usage() == {"used_percent": 0, "idle_percent": 0}

    def test_get_memory_usage(self):
        with patch("builtins.open", mock_open(read_data=MOCK_MEMINFO)):
            mem = _get_memory_usage()
            assert mem["total_mb"] == 16000
            assert mem["available_mb"] > 0
            assert mem["used_mb"] > 0
            assert 0 < mem["used_percent"] < 100

    def test_get_memory_usage_failure(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert _get_memory_usage() == {"total_mb": 0, "available_mb": 0, "used_mb": 0, "used_percent": 0}

    def test_get_storage_usage(self):
        fake_df = """Source FSType Size Used Avail Target
/dev/sda1 ext4 107374182400 53687091200 53687091200 /
"""
        with patch("subprocess.check_output") as mock_df:
            mock_df.return_value = fake_df
            info = _get_storage_usage()
            assert len(info) >= 1
            assert info[0]["used_percent"] == 50.0

    def test_get_storage_usage_failure(self):
        with patch("subprocess.check_output", side_effect=Exception):
            assert _get_storage_usage() == []

    def test_get_host_info_integrates(self):
        with patch("app.services.host_manager._get_hostname", return_value="host"), \
             patch("app.services.host_manager._get_uptime", return_value="1d"), \
             patch("app.services.host_manager._get_cpu_info", return_value={"cores": 4, "model": "test"}), \
             patch("app.services.host_manager._get_memory_info", return_value={"total_mb": 8192}), \
             patch("app.services.host_manager._get_storage_info", return_value=[{"size_gb": 100}]):
            info = get_host_info()
            assert info["hostname"] == "host"
            assert info["uptime"] == "1d"
            assert info["cpu"]["cores"] == 4
            assert info["memory"]["total_mb"] == 8192
            assert len(info["storage"]) == 1

    def test_get_host_stats_integrates(self):
        with patch("app.services.host_manager._get_cpu_usage", return_value={"used_percent": 50}), \
             patch("app.services.host_manager._get_memory_usage", return_value={"used_percent": 60}), \
             patch("app.services.host_manager._get_storage_usage", return_value=[{"used_percent": 70}]):
            stats = get_host_stats()
            assert stats["cpu"]["used_percent"] == 50
            assert stats["memory"]["used_percent"] == 60
            assert stats["storage"][0]["used_percent"] == 70
