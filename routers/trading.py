"""
Trading endpoints for order placement and portfolio management.
Includes regular orders, conditional orders, and portfolio tracking.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query

from config import get_settings
from dnse_client import get_dnse_client
from schemas import (
    PlaceOrderRequest,
    PlaceOrderPayload,
    OrderDetail,
    Deal,
    ConditionalOrderRequest,
    ConditionalOrderDetail,
    ConditionalOrderCreateResponse
)


router = APIRouter(prefix="/trading", tags=["Trading"])


# ============================================================================
# REGULAR ORDERS
# ============================================================================

@router.post("/orders", response_model=OrderDetail, status_code=status.HTTP_201_CREATED)
async def place_order(order: PlaceOrderRequest) -> OrderDetail:
    """
    Place a new order on DNSE.

    **Request Body:**
    - **symbol**: Stock symbol (e.g., "VNM", "HPG")
    - **side**: Order side - "NB" (buy) or "NS" (sell)
    - **orderType**: Order type - "LO", "MP", "MTL", "ATC", "ATO", "MOK", "MAK", "PLO"
    - **price**: Order price in VND
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
           "price": 85500,
           "quantity": 100
         }'
    ```

    **Returns:** Complete order details with order ID, status, execution info.
    """
    client = get_dnse_client()
    settings = get_settings()

    # Add accountNo from config
    payload = PlaceOrderPayload(
        **order.model_dump(),
        accountNo=settings.DNSE_ACCOUNT_NO
    )

    try:
        return await client.place_order(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to place order: {str(e)}"
        )


@router.get("/orders", response_model=list[OrderDetail])
async def get_orders(account_no: Optional[str] = None) -> list[OrderDetail]:
    """
    Get list of orders for the configured account.

    **Query Parameters:**
    - **account_no**: (Optional) Account number. Defaults to DNSE_ACCOUNT_NO from config.

    **Example:**
    ```bash
    curl "http://localhost:8000/trading/orders"
    ```

    **Returns:** List of all orders with complete details including fill information.
    """
    client = get_dnse_client()

    try:
        return await client.get_orders(account_no)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orders: {str(e)}"
        )


@router.get("/orders/{order_id}", response_model=OrderDetail)
async def get_order_by_id(
    order_id: int,
    account_no: Optional[str] = None
) -> OrderDetail:
    """
    Get details of a specific order.

    **Path Parameters:**
    - **order_id**: Order ID

    **Query Parameters:**
    - **account_no**: (Optional) Account number. Defaults to DNSE_ACCOUNT_NO from config.

    **Example:**
    ```bash
    curl "http://localhost:8000/trading/orders/12345678"
    ```

    **Returns:** Complete order information including execution details.
    """
    client = get_dnse_client()

    try:
        return await client.get_order_by_id(order_id, account_no)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order: {str(e)}"
        )


@router.delete("/orders/{order_id}", response_model=OrderDetail)
async def cancel_order(
    order_id: int,
    account_no: Optional[str] = None
) -> OrderDetail:
    """
    Cancel an existing order.

    **Path Parameters:**
    - **order_id**: Order ID to cancel

    **Query Parameters:**
    - **account_no**: (Optional) Account number. Defaults to DNSE_ACCOUNT_NO from config.

    **Example:**
    ```bash
    curl -X DELETE "http://localhost:8000/trading/orders/12345678"
    ```

    **Returns:** Updated order information after cancellation.
    **Note:** Only orders with status 'new' or 'partiallyFilled' can be cancelled.
    """
    client = get_dnse_client()

    try:
        return await client.cancel_order(order_id, account_no)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )


# ============================================================================
# PORTFOLIO / DEALS
# ============================================================================

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

    **Returns:** List of all open and closed positions with complete P&L information.

    **Key Response Fields:**
    - **id**: Deal ID
    - **symbol**: Stock symbol
    - **status**: "OPEN" or "CLOSED"
    - **side**: "NB" (buy) or "NS" (sell)
    - **secure**: Margin/collateral amount
    - **costPrice**: Average entry price
    - **marketPrice**: Current market price
    - **realizedProfit**: Realized profit/loss (closed portion)
    - **unrealizedProfit**: Unrealized profit/loss (open portion)
    - **breakEvenPrice**: Break-even price including fees
    - **accumulateQuantity**: Total quantity accumulated
    - **tradeQuantity**: Quantity available for trading
    """
    client = get_dnse_client()

    try:
        return await client.get_deals(account_no)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio: {str(e)}"
        )


# ============================================================================
# CONDITIONAL ORDERS
# ============================================================================

@router.post("/conditional-orders", response_model=ConditionalOrderCreateResponse, status_code=status.HTTP_201_CREATED)
async def place_conditional_order(order: ConditionalOrderRequest) -> ConditionalOrderCreateResponse:
    """
    Place a conditional order (stop order).

    **Request Body:**
    - **condition**: Condition string (e.g., "price >= 26650" or "price <= 26650")
    - **symbol**: Stock symbol
    - **targetOrder**: Order to place when condition is met
      - **quantity**: Order quantity
      - **side**: "NB" (buy) or "NS" (sell)
      - **price**: Order price
      - **orderType**: "LO", "MP", "MTL"
      - **loanPackageId**: (Optional) For margin
    - **props**:
      - **stopPrice**: Trigger price
      - **marketId**: "UNDERLYING" (stocks) or "DERIVATIVES"
    - **timeInForce**:
      - **expireTime**: Expiration time (ISO 8601 format)
      - **kind**: "GTD" (Good Till Date)
    - **accountNo**: Account number
    - **category**: "STOP"

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/trading/conditional-orders" \\
         -H "Content-Type: application/json" \\
         -d '{
           "condition": "price <= 26650",
           "symbol": "HPG",
           "targetOrder": {
             "quantity": 100,
             "side": "NB",
             "price": 26600,
             "orderType": "LO"
           },
           "props": {
             "stopPrice": 26650,
             "marketId": "UNDERLYING"
           },
           "accountNo": "0001234567",
           "category": "STOP",
           "timeInForce": {
             "expireTime": "2024-10-23T07:30:00.000Z",
             "kind": "GTD"
           }
         }'
    ```

    **Returns:** Conditional order ID.
    """
    client = get_dnse_client()

    try:
        return await client.place_conditional_order(order)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to place conditional order: {str(e)}"
        )


@router.get("/conditional-orders")
async def get_conditional_orders(
    account_no: Optional[str] = None,
    daily: bool = Query(False, description="Get today's orders only"),
    from_date: Optional[str] = Query(None, description="Start date (yyyy-MM-dd)"),
    to_date: Optional[str] = Query(None, description="End date (yyyy-MM-dd)"),
    page: int = Query(1, description="Page number", ge=1),
    size: int = Query(10000, description="Items per page", le=10000),
    status: Optional[list[str]] = Query(None, description="Filter by status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    market_id: str = Query("UNDERLYING", description="UNDERLYING or DERIVATIVES")
):
    """
    Get list of conditional orders with pagination.

    **Query Parameters:**
    - **account_no**: (Optional) Account number
    - **daily**: Get today's orders only (default: false)
    - **from_date**: Start date (yyyy-MM-dd)
    - **to_date**: End date (yyyy-MM-dd)
    - **page**: Page number (default: 1)
    - **size**: Items per page (default: 10000, max: 10000)
    - **status**: Filter by status (NEW/ACTIVATED/REJECTED/CANCELLED/EXPIRED/FAILED)
    - **symbol**: Filter by symbol
    - **market_id**: UNDERLYING or DERIVATIVES (default: UNDERLYING)

    **Example:**
    ```bash
    curl "http://localhost:8000/trading/conditional-orders?daily=true&status=ACTIVATED"
    ```

    **Returns:** Paginated list of conditional orders with metadata.
    """
    client = get_dnse_client()

    try:
        return await client.get_conditional_orders(
            account_no=account_no,
            daily=daily,
            from_date=from_date,
            to_date=to_date,
            page=page,
            size=size,
            status=status,
            symbol=symbol,
            market_id=market_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conditional orders: {str(e)}"
        )


@router.get("/conditional-orders/{order_id}", response_model=ConditionalOrderDetail)
async def get_conditional_order_by_id(order_id: str) -> ConditionalOrderDetail:
    """
    Get details of a specific conditional order.

    **Path Parameters:**
    - **order_id**: Conditional order ID

    **Example:**
    ```bash
    curl "http://localhost:8000/trading/conditional-orders/csc7iqa45sbpqutqm81g"
    ```

    **Returns:** Complete conditional order information.
    """
    client = get_dnse_client()

    try:
        return await client.get_conditional_order_by_id(order_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conditional order: {str(e)}"
        )


@router.patch("/conditional-orders/{order_id}/cancel", response_model=ConditionalOrderCreateResponse)
async def cancel_conditional_order(order_id: str) -> ConditionalOrderCreateResponse:
    """
    Cancel a conditional order.

    **Path Parameters:**
    - **order_id**: Conditional order ID to cancel

    **Example:**
    ```bash
    curl -X PATCH "http://localhost:8000/trading/conditional-orders/csc7iqa45sbpqutqm81g/cancel"
    ```

    **Returns:** Confirmation with order ID.
    **Note:** Only orders with status 'NEW' or 'ACTIVATED' can be cancelled.
    """
    client = get_dnse_client()

    try:
        return await client.cancel_conditional_order(order_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel conditional order: {str(e)}"
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================

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
        "client_initialized": client is not None,
        "features": {
            "regular_orders": True,
            "conditional_orders": True,
            "portfolio_tracking": True
        }
    }
