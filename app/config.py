import os


class Settings:
    def __init__(self):
        self.default_host_uri: str = os.getenv("DEFAULT_HOST_URI", "qemu:///system")
        self.host: str = os.getenv("API_HOST", "0.0.0.0")
        try:
            self.port: int = int(os.getenv("API_PORT", "8000"))
        except Exception:
            self.port = 8000


settings = Settings()
