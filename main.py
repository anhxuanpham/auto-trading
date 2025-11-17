"""
DNSE Lightspeed API Backend - Main Entry Point

A production-ready FastAPI backend for algorithmic trading via DNSE.

Features:
- Hot-reload token updates without server restart
- Automatic JWT authentication with expiration handling
- Trading operations (regular orders, conditional orders, portfolio)
- Real-time market data streaming via WebSocket/MQTT
- Admin endpoints for token management
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from config import get_settings
from dnse_client import close_dnse_client
from routers import admin, trading, market_data
from market_data_client import close_market_data_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    print(f"🚀 Starting DNSE Trading Backend")
    print(f"📊 Account: {settings.DNSE_ACCOUNT_NO}")
    print(f"🔗 API: {settings.API_BASE_URL}")

    yield

    # Shutdown
    print("🛑 Shutting down DNSE Trading Backend")
    await close_dnse_client()
    close_market_data_client()


# Initialize FastAPI app
app = FastAPI(
    title="DNSE Lightspeed API Backend",
    description="Production-ready backend for algorithmic trading via DNSE",
    version="1.0.0",
    lifespan=lifespan
)


# Register routers
app.include_router(admin.router)
app.include_router(trading.router)
app.include_router(market_data.router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> dict:
    """
    Root endpoint - API information.

    Returns basic API information and available endpoints.
    """
    return {
        "name": "DNSE Lightspeed API Backend",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "admin": "/admin",
            "trading": "/trading",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


# Health check endpoint
@app.get("/health", tags=["Root"])
async def health_check() -> dict:
    """
    Global health check endpoint.

    Verifies the application is running and configured properly.
    """
    try:
        settings = get_settings()
        return {
            "status": "healthy",
            "account_no": settings.DNSE_ACCOUNT_NO,
            "api_base_url": settings.API_BASE_URL
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all unhandled exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info"
    )
