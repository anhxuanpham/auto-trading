"""
Trading endpoints for order placement and portfolio management.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from config import get_settings
from dnse_client import get_dnse_client
from schemas import (
    PlaceOrderRequest,
    PlaceOrderPayload,
    OrderResponse,
    Order,
    Deal
)


router = APIRouter(prefix="/trading", tags=["Trading"])


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order(order: PlaceOrderRequest) -> OrderResponse:
    """
    Place a new order on DNSE.

    **Request Body:**
    - **symbol**: Stock symbol (e.g., "VNM", "HPG")
    - **side**: Order side - "NB" (buy) or "NS" (sell)
    - **orderType**: Order type - "LO" (limit), "MP" (market), "ATC", "ATO"
    - **price**: Order price
    - **quantity**: Number of shares (must be positive)
    - **loanPackageId**: (Optional) For margin trading

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/trading/orders" \\
         -H "Content-Type: application/json" \\
         -d '{
           "symbol": "VNM",
           "side": "NB",
           "orderType": "LO",
           "price": 85.5,
           "quantity": 100
         }'
    ```

    **Returns:** Order confirmation with order ID and status.
    """
    client = get_dnse_client()
    settings = get_settings()

    # Add accountNo from config
    payload = PlaceOrderPayload(
        **order.model_dump(),
        accountNo=settings.DNSE_ACCOUNT_NO
    )

    try:
        response = await client.place_order(payload)

        # Parse response into OrderResponse
        return OrderResponse(
            orderId=response.get("orderId"),
            status=response.get("status", "submitted"),
            message=response.get("message", "Order placed successfully")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to place order: {str(e)}"
        )


@router.get("/orders", response_model=list[Order])
async def get_orders(account_no: Optional[str] = None) -> list[Order]:
    """
    Get list of orders for the configured account.

    **Query Parameters:**
    - **account_no**: (Optional) Account number. Defaults to DNSE_ACCOUNT_NO from config.

    **Example:**
    ```bash
    curl "http://localhost:8000/trading/orders"
    ```

    **Returns:** List of all orders with their current status.
    """
    client = get_dnse_client()

    try:
        orders = await client.get_orders(account_no)
        return orders

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orders: {str(e)}"
        )


@router.get("/portfolio", response_model=list[Deal])
async def get_portfolio(account_no: Optional[str] = None) -> list[Deal]:
    """
    Get current portfolio (deals/positions) for the configured account.

    **Query Parameters:**
    - **account_no**: (Optional) Account number. Defaults to DNSE_ACCOUNT_NO from config.

    **Example:**
    ```bash
    curl "http://localhost:8000/trading/portfolio"
    ```

    **Returns:** List of all open and closed positions with P&L information.

    **Response Fields:**
    - **id**: Deal ID
    - **symbol**: Stock symbol
    - **status**: "OPEN" or "CLOSED"
    - **side**: Trade side
    - **secure**: True if margin position
    - **costPrice**: Average entry price
    - **marketPrice**: Current market price
    - **realizedProfit**: Realized profit/loss
    - **quantity**: Position size
    """
    client = get_dnse_client()

    try:
        deals = await client.get_deals(account_no)
        return deals

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio: {str(e)}"
        )


@router.get("/health")
async def trading_health() -> dict:
    """
    Health check for trading endpoints.

    Verifies:
    - Client is initialized
    - Configuration is loaded
    """
    settings = get_settings()
    client = get_dnse_client()

    return {
        "status": "healthy",
        "account_no": settings.DNSE_ACCOUNT_NO,
        "client_initialized": client is not None
    }
