from fastapi import FastAPI
from app.api import vm_routes
from app.config import settings

app = FastAPI(title="KVM Manager MVP")

app.include_router(vm_routes.router, prefix="/vm")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
