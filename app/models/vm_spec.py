from pydantic import BaseModel
from typing import Optional


class VMSpec(BaseModel):
    name: str
    cpu: int
    memory_mb: int
    disk_gb: int
    image: str
    disk_path: Optional[str] = None
    network_bridge: Optional[str] = "virbr0"
