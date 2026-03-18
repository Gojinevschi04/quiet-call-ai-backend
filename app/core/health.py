from fastapi import APIRouter
from sqlmodel import text

from app.core.database import async_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    db_ok = False
    try:
        async with async_session() as session:
            await session.exec(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "database": "connected" if db_ok else "disconnected",
        "version": "1.0.0",
    }
