from pydantic import BaseModel
from typing import Optional


class VMSpec(BaseModel):
    name: str
    cpu: int
    memory_mb: int
    disk_gb: int
    image: Optional[str] = None
    disk_path: Optional[str] = None
    iso_path: Optional[str] = None
    cloud_init_iso: Optional[str] = None
    network: Optional[str] = "default"
