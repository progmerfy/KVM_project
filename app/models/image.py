from pydantic import BaseModel
from typing import Optional


class ImageInfo(BaseModel):
    name: str
    path: str
    format: str
    virtual_size_gb: float
    actual_size_bytes: int
    backing_file: Optional[str] = None
    mtime: Optional[float] = None
    ctime: Optional[float] = None


class CloudImageInfo(BaseModel):
    name: str
    url: str
    description: str
