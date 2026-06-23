"""Unit tests for app.config — Settings with env var overrides."""

import os


class TestSettingsDefaults:
    def test_default_values(self):
        # Save and clear env vars that could interfere
        saved = {}
        for key in ["DEFAULT_HOST_URI", "API_PORT", "LOG_LEVEL", "STORAGE_POOL",
                     "default_host_uri", "port", "log_level", "storage_pool",
                     "HOST", "host", "DEFAULT_NETWORK", "default_network"]:
            saved[key] = os.environ.pop(key, None)

        from app.config import Settings
        s = Settings()
        assert s.default_host_uri == "qemu:///system"
        assert s.host == "0.0.0.0"
        assert s.port == 8000
        assert s.log_level == "INFO"
        assert s.default_network == "default"
        assert s.storage_pool == "/var/lib/libvirt/images"

        # Restore env vars
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val

    def test_env_override(self):
        saved = {}
        for key in ["DEFAULT_HOST_URI", "API_PORT", "LOG_LEVEL", "STORAGE_POOL"]:
            saved[key] = os.environ.pop(key, None)

        os.environ["DEFAULT_HOST_URI"] = "qemu+tcp://192.168.1.1/system"
        os.environ["API_PORT"] = "8443"
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ["STORAGE_POOL"] = "/mnt/storage"

        from app.config import Settings
        s = Settings()
        assert s.default_host_uri == "qemu+tcp://192.168.1.1/system"
        assert s.port == 8443
        assert s.log_level == "DEBUG"
        assert s.storage_pool == "/mnt/storage"

        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val
            else:
                os.environ.pop(key, None)

    def test_invalid_port_falls_back(self):
        saved = os.environ.pop("API_PORT", None)

        os.environ["API_PORT"] = "not-a-number"
        from app.config import Settings
        s = Settings()
        assert s.port == 8000
        if saved is not None:
            os.environ["API_PORT"] = saved
        else:
            del os.environ["API_PORT"]
