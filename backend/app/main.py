from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.config import get_settings
from app.routers import devices, readings


def _operation_id(route: APIRoute) -> str:
    # Clean names in the generated frontend client (e.g. `list_readings`).
    return route.name


settings = get_settings()

app = FastAPI(
    title="Brew Room Monitor API",
    generate_unique_id_function=_operation_id,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(devices.router, prefix="/api/v1")
app.include_router(readings.router, prefix="/api/v1")
