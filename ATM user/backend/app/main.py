import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.app.config import FRONTEND_DIR, ATM_MACHINE_DIR
from backend.app.database import db, init_db
from backend.app.seed import seed_initial_data
from backend.app.routers import auth_router, bank_router, dashboard_router, atm_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB Atlas indexes and connectivity
    init_db()
    # Seed initial demo user (Arun Kumar) and demo banks into MongoDB Atlas UniCash
    seed_initial_data(db)
    yield

app = FastAPI(
    title="Multi-Bank Cardless ATM API",
    description="Secure backend for Multi-Bank Cardless ATM application prototype backed by MongoDB Atlas (UniCash)",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router.router)
app.include_router(bank_router.router)
app.include_router(dashboard_router.router)
app.include_router(atm_router.router)

@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "Multi-Bank Cardless ATM",
        "database": "MongoDB Atlas",
        "database_name": "UniCash"
    }

@app.get("/api/users/{user_id}/linked-banks", tags=["Banks"])
def get_user_linked_banks_by_id(user_id: str):
    """Retrieve verified demo linked banks for a user ID directly from MongoDB Atlas."""
    from backend.app.routers.bank_router import format_bank_doc
    banks_cursor = db.linked_banks.find({"user_id": str(user_id)})
    return [format_bank_doc(b) for b in banks_cursor]

# Mount ATM Machine static files & routes
if ATM_MACHINE_DIR.exists():
    app.mount("/atm-static", StaticFiles(directory=str(ATM_MACHINE_DIR)), name="atm-static")

    @app.get("/atm")
    @app.get("/atm/")
    def serve_atm_root():
        index_file = ATM_MACHINE_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "ATM Machine interface not found in 'atm machine' directory."}

# Mount frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_frontend_root():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Frontend not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)

