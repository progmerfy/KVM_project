import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def get_host_info() -> dict:
    return {
        "hostname": _get_hostname(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "storage": _get_storage_info(),
        "uptime": _get_uptime(),
    }


def _get_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
        days = int(up // 86400)
        hours = int((up % 86400) // 3600)
        mins = int((up % 3600) // 60)
        if days:
            return f"{days}d {hours}h {mins}m"
        return f"{hours}h {mins}m"
    except Exception:
        return None


def get_host_stats() -> dict:
    return {
        "cpu": _get_cpu_usage(),
        "memory": _get_memory_usage(),
        "storage": _get_storage_usage(),
    }


def _get_hostname() -> str:
    try:
        return os.uname().nodename
    except Exception:
        return "unknown"


def _get_cpu_info() -> dict:
    try:
        output = subprocess.check_output(
            ["nproc"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        cores = int(output)
    except Exception:
        cores = 0

    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    return {"cores": cores, "model": model}
    except Exception:
        pass
    return {"cores": cores, "model": "unknown"}


def _get_memory_info() -> dict:
    total = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) // 1024
                    break
    except Exception:
        pass
    return {"total_mb": total, "total_gb": round(total / 1024, 1)}


def _get_storage_info() -> list:
    result = []
    try:
        output = subprocess.check_output(
            ["df", "-B1", "--output=source,fstype,size,used,avail,target"],
            stderr=subprocess.DEVNULL, text=True,
        )
        lines = output.strip().split("\n")[1:]
        for line in lines:
            parts = line.split(None, 5)
            if len(parts) >= 6:
                source, fstype, size_b, used_b, avail_b, mount = parts
                if fstype in ("tmpfs", "devtmpfs", "overlay"):
                    continue
                result.append({
                    "filesystem": source,
                    "type": fstype,
                    "size_gb": round(int(size_b) / (1024**3), 1),
                    "used_gb": round(int(used_b) / (1024**3), 1),
                    "avail_gb": round(int(avail_b) / (1024**3), 1),
                    "mount": mount,
                })
    except Exception:
        pass
    return result


def _get_cpu_usage() -> dict:
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.strip().split()
        if len(parts) >= 5:
            user = int(parts[1])
            nice = int(parts[2])
            system = int(parts[3])
            idle = int(parts[4])
            total = user + nice + system + idle
            used = user + nice + system
            return {
                "used_percent": round(used / total * 100, 1) if total else 0,
                "idle_percent": round(idle / total * 100, 1) if total else 0,
            }
    except Exception:
        pass
    return {"used_percent": 0, "idle_percent": 0}


def _get_memory_usage() -> dict:
    try:
        with open("/proc/meminfo") as f:
            data = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    data[key] = int(val)

        total = data.get("MemTotal", 0)
        free = data.get("MemFree", 0)
        buffers = data.get("Buffers", 0)
        cached = data.get("Cached", 0)
        available = data.get("MemAvailable", free + buffers + cached)

        return {
            "total_mb": total // 1024,
            "available_mb": available // 1024,
            "used_mb": (total - available) // 1024,
            "used_percent": round((total - available) / total * 100, 1) if total else 0,
        }
    except Exception:
        return {"total_mb": 0, "available_mb": 0, "used_mb": 0, "used_percent": 0}


def _get_storage_usage() -> list:
    result = []
    try:
        output = subprocess.check_output(
            ["df", "-B1", "--output=source,fstype,size,used,avail,target"],
            stderr=subprocess.DEVNULL, text=True,
        )
        lines = output.strip().split("\n")[1:]
        for line in lines:
            parts = line.split(None, 5)
            if len(parts) >= 6:
                source, fstype, size_b, used_b, avail_b, mount = parts
                if fstype in ("tmpfs", "devtmpfs", "overlay"):
                    continue
                total = int(size_b)
                used = int(used_b)
                result.append({
                    "filesystem": source,
                    "mount": mount,
                    "size_gb": round(total / (1024**3), 1),
                    "used_gb": round(used / (1024**3), 1),
                    "avail_gb": round(int(avail_b) / (1024**3), 1),
                    "used_percent": round(used / total * 100, 1) if total else 0,
                })
    except Exception:
        pass
    return result
