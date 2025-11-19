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
import logging
import sys
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings
from dnse_client import close_dnse_client
from routers import admin, trading, market_data
from market_data_client import close_market_data_client


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging():
    """Configure logging with colored output and detailed formatting."""

    # Define log format
    log_format = (
        '%(asctime)s | %(levelname)-8s | %(name)-25s | '
        '%(funcName)-20s | Line:%(lineno)-4d | %(message)s'
    )

    # Create formatter
    formatter = logging.Formatter(
        log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler - all logs
    file_handler = logging.FileHandler('dnse_backend.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # File handler - errors only
    error_handler = logging.FileHandler('dnse_errors.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Set specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    return logging.getLogger(__name__)


# Setup logging
logger = setup_logging()
logger.info("=" * 80)
logger.info("DNSE Trading Backend - Logging Initialized")
logger.info("=" * 80)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("=" * 80)
    logger.info("🚀 STARTING DNSE TRADING BACKEND")
    logger.info("=" * 80)

    try:
        settings = get_settings()
        logger.info(f"📊 Account Number: {settings.DNSE_ACCOUNT_NO}")
        logger.info(f"🔗 API Base URL: {settings.API_BASE_URL}")
        logger.info(f"⏰ JWT Expiration: {settings.JWT_EXPIRATION_HOURS} hours")
        logger.info(f"🔑 Trading Token: {'*' * 10}{settings.TRADING_TOKEN[-4:] if len(settings.TRADING_TOKEN) > 4 else '****'}")
        logger.info("✅ Configuration loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("=" * 80)
    logger.info("🛑 SHUTTING DOWN DNSE TRADING BACKEND")
    logger.info("=" * 80)

    try:
        logger.info("Closing DNSE client...")
        await close_dnse_client()
        logger.info("✅ DNSE client closed")
    except Exception as e:
        logger.error(f"❌ Error closing DNSE client: {e}", exc_info=True)

    try:
        logger.info("Closing market data client...")
        close_market_data_client()
        logger.info("✅ Market data client closed")
    except Exception as e:
        logger.error(f"❌ Error closing market data client: {e}", exc_info=True)

    logger.info("👋 Shutdown complete")


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="DNSE Lightspeed API Backend",
    description="Production-ready backend for algorithmic trading via DNSE",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================

# CORS middleware - Allow frontend to access API
settings = get_settings()
allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"🔓 CORS enabled for origins: {allowed_origins}")


# ============================================================================
# ROUTERS
# ============================================================================

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


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler - catches all unhandled exceptions.
    Logs full error details but only returns safe message to client.
    """
    # Log full error with traceback
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else "unknown"
        }
    )

    # Return safe error to client (don't expose internals)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "timestamp": time.time()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle FastAPI HTTPException - these are intentional errors.
    """
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
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
