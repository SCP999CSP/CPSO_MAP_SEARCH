from fastapi import FastAPI

from .routers import locations

app = FastAPI(title="SP DOC Map API")

app.include_router(locations.router, prefix="/api")
