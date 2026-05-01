from pydantic import BaseModel, Field
from typing import Optional


class VMCreateRequest(BaseModel):
    name: str = Field(..., description="Имя виртуальной машины")
    cpu: int = Field(1, ge=1)
    memory_mb: int = Field(512, ge=128)
    disk_gb: int = Field(10, ge=1)
    image: str = Field(..., description="Путь до образа или шаблона")
    host_uri: Optional[str] = Field(
        None,
        description="URI libvirt хоста; использует DEFAULT_HOST_URI если не задано",
    )
    network_bridge: Optional[str] = Field("virbr0")


class VMActionRequest(BaseModel):
    name: str = Field(..., description="Имя виртуальной машины (domain name)")
    host_uri: Optional[str] = Field(None)
