import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import vm_routes, image_routes, host_routes
from app.config import settings
from app.errors import AppError

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="KVM Manager API",
    version="0.3.0",
    description=(
        "Pre-production KVM/libvirt VM management API. "
        "Create VMs with cloud-init SSH access, manage OS images, "
        "monitor host resources."
    ),
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(vm_routes.router, prefix="/vm")
app.include_router(image_routes.router, prefix="/images")
app.include_router(host_routes.router, prefix="/host")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
