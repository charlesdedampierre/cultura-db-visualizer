"""FastAPI application for the polity visualizer."""

import logging
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import polities, individuals, cities

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Historical Polity Visualizer API",
    description="API for visualizing historical polities on a world map",
    version="1.0.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# Include routers
app.include_router(polities.router, prefix="/api")
app.include_router(individuals.router, prefix="/api")
app.include_router(cities.router, prefix="/api")


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    from .database import get_db

    db = get_db()

    polity_response = db.table("polities").select("id", count="exact").limit(1).execute()
    polity_count = polity_response.count if polity_response.count else 0

    individual_response = db.table("individuals_light").select("wikidata_id", count="exact").limit(1).execute()
    individual_count = individual_response.count if individual_response.count else 0

    return {
        "status": "healthy",
        "polities": polity_count,
        "individuals": individual_count,
    }


# Serve the built frontend
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    # Serve static files in dist root (evolution.json, occupations.json, vite.svg)
    @app.get("/evolution.json")
    def serve_evolution():
        return FileResponse(FRONTEND_DIST / "evolution.json")

    @app.get("/occupations.json")
    def serve_occupations():
        return FileResponse(FRONTEND_DIST / "occupations.json")

    @app.get("/vite.svg")
    def serve_vite_svg():
        return FileResponse(FRONTEND_DIST / "vite.svg")

    # Catch-all: serve index.html for any non-API route (SPA routing)
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
