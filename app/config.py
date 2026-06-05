import os


class Settings:
    def __init__(self):
        self.default_host_uri: str = os.getenv("DEFAULT_HOST_URI", "qemu:///system")
        self.host: str = os.getenv("API_HOST", "0.0.0.0")
        try:
            self.port: int = int(os.getenv("API_PORT", "8000"))
        except (ValueError, TypeError):
            self.port = 8000
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.default_network: str = os.getenv("DEFAULT_NETWORK", "default")
        self.storage_pool: str = os.getenv("STORAGE_POOL", "/var/lib/libvirt/images")


settings = Settings()
