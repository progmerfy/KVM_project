from pydantic import BaseModel, Field
from typing import Optional


class VMCreateRequest(BaseModel):
    name: str = Field(..., description="VM name", min_length=1, max_length=64)
    cpu: int = Field(1, ge=1, le=64)
    memory_mb: int = Field(512, ge=128, le=524288)
    disk_gb: int = Field(10, ge=1, le=10240)
    image: str = Field(
        ..., description="Path to base qcow2 image or template"
    )
    iso_path: Optional[str] = Field(
        None, description="Path to ISO for OS installation"
    )
    host_uri: Optional[str] = Field(
        None, description="libvirt host URI; uses DEFAULT_HOST_URI if not set"
    )
    network: Optional[str] = Field(
        "default", description="libvirt network name (default NAT network)"
    )
    cloud_init_ssh_key: Optional[str] = Field(
        None, description="SSH public key for cloud-init (passwordless access)"
    )
    cloud_init_user: str = Field(
        "user", description="Username for cloud-init"
    )
    cloud_init_user_data: Optional[str] = Field(
        None, description="Raw cloud-init user-data (overrides ssh_key)"
    )
    root_password: Optional[str] = Field(
        None, description="Root password (8+ chars). Auto-generated if not set"
    )


class VMISORequest(BaseModel):
    name: str = Field(..., description="VM name")
    iso_path: str = Field(..., description="Path to ISO image")
    host_uri: Optional[str] = Field(None)


class VMActionRequest(BaseModel):
    name: str = Field(..., description="VM name (domain name)")
    host_uri: Optional[str] = Field(None)
