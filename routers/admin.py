"""
Admin endpoints for managing the application.
Includes token update functionality.
"""
import logging
from fastapi import APIRouter, Header, HTTPException, status

from config import get_settings, reload_settings
from schemas import UpdateTokenRequest, UpdateTokenResponse
from utils import update_env_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


async def verify_admin_secret(x_admin_secret: str = Header(...)) -> None:
    """
    Verify the admin secret header.

    Args:
        x_admin_secret: Admin secret from request header

    Raises:
        HTTPException: If secret is invalid
    """
    settings = get_settings()
    if x_admin_secret != settings.ADMIN_SECRET:
        logger.warning("⚠️ Admin authentication failed | Invalid admin secret provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret"
        )
    logger.debug("✅ Admin authentication successful")


@router.post("/update-token", response_model=UpdateTokenResponse)
async def update_trading_token(
    request: UpdateTokenRequest,
    x_admin_secret: str = Header(..., description="Admin secret for authentication")
) -> UpdateTokenResponse:
    """
    Update the TRADING_TOKEN without restarting the server.

    This endpoint:
    1. Verifies the admin secret
    2. Updates the .env file on disk
    3. Reloads the settings in memory
    4. Returns success confirmation

    **Security:** Requires X-Admin-Secret header matching ADMIN_SECRET in config.

    **Usage:**
    ```bash
    curl -X POST "http://localhost:8000/admin/update-token" \\
         -H "X-Admin-Secret: your_admin_secret" \\
         -H "Content-Type: application/json" \\
         -d '{"new_trading_token": "new_token_value"}'
    ```
    """
    logger.info("=" * 80)
    logger.info("🌐 API Endpoint: POST /admin/update-token")
    logger.info("⚙️ Updating TRADING_TOKEN (hot-reload without restart)")

    # Verify admin secret
    await verify_admin_secret(x_admin_secret)

    try:
        # Update .env file on disk
        logger.info("📝 Updating .env file on disk")
        token_masked = f"{'*' * 10}{request.new_trading_token[-4:] if len(request.new_trading_token) > 4 else '****'}"
        logger.info(f"New token: {token_masked}")
        update_env_file("TRADING_TOKEN", request.new_trading_token)
        logger.info("✅ .env file updated successfully")

        # Reload settings in memory
        logger.info("🔄 Reloading settings cache")
        reload_settings()
        logger.info("✅ Settings cache reloaded")

        logger.info("✅ API Response: Trading token updated successfully")
        logger.info("=" * 80)

        return UpdateTokenResponse(
            success=True,
            message="Trading token updated successfully"
        )

    except Exception as e:
        logger.error(f"❌ Failed to update token: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update token: {str(e)}"
        )


@router.get("/health")
async def admin_health() -> dict:
    """
    Simple health check endpoint.

    Returns current configuration status (without sensitive values).
    """
    logger.debug("🌐 API Endpoint: GET /admin/health")
    settings = get_settings()
    return {
        "status": "healthy",
        "api_base_url": settings.API_BASE_URL,
        "account_no": settings.DNSE_ACCOUNT_NO,
        "jwt_expiration_hours": settings.JWT_EXPIRATION_HOURS,
        "trading_token_set": bool(settings.TRADING_TOKEN)
    }
