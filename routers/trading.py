"""
Trading endpoints for order placement and portfolio management.
Includes regular orders, conditional orders, and portfolio tracking.
"""
import logging
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import get_settings
from dnse_client import get_dnse_client
from metrics import track_order_placed, track_order_cancelled, order_placement_duration_seconds
from schemas import (
    PlaceOrderRequest,
    PlaceOrderPayload,
    OrderDetail,
    Deal,
    ConditionalOrderRequest,
    ConditionalOrderDetail,
    ConditionalOrderCreateResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trading", tags=["Trading"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# REGULAR ORDERS
# ============================================================================

@router.post("/orders", response_model=OrderDetail, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # Max 10 orders per minute per IP
async def place_order(request: Request, order: PlaceOrderRequest) -> OrderDetail:
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
    logger.info("=" * 80)
    logger.info(f"🌐 API Endpoint: POST /trading/orders")
    logger.info(f"Order request: {order.side} {order.symbol} | Qty: {order.quantity} | Price: {order.price} | Type: {order.orderType}")

    client = get_dnse_client()
    settings = get_settings()

    # Add accountNo from config
    payload = PlaceOrderPayload(
        **order.model_dump(),
        accountNo=settings.DNSE_ACCOUNT_NO
    )

    # Track order placement timing
    start_time = time.time()

    try:
        result = await client.place_order(payload)

        # Track metrics
        duration = time.time() - start_time
        order_placement_duration_seconds.labels(
            symbol=order.symbol,
            side=order.side.value
        ).observe(duration)

        track_order_placed(
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.orderType.value,
            status='success'
        )

        logger.info(f"✅ API Response: Order placed successfully | Order ID: {result.id}")
        logger.info("=" * 80)
        return result
    except HTTPException as e:
        track_order_placed(
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.orderType.value,
            status='failed'
        )
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        track_order_placed(
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.orderType.value,
            status='error'
        )
        logger.error(f"❌ Unexpected error placing order: {str(e)}", exc_info=True)
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
    logger.info(f"🌐 API Endpoint: GET /trading/orders | Account: {account_no or 'default'}")

    client = get_dnse_client()

    try:
        result = await client.get_orders(account_no)
        logger.info(f"✅ API Response: Retrieved {len(result)} orders")
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting orders: {str(e)}", exc_info=True)
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
    logger.info(f"🌐 API Endpoint: GET /trading/orders/{order_id} | Account: {account_no or 'default'}")

    client = get_dnse_client()

    try:
        result = await client.get_order_by_id(order_id, account_no)
        logger.info(f"✅ API Response: Order details retrieved | Symbol: {result.symbol} | Status: {result.orderStatus}")
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order: {str(e)}"
        )


@router.delete("/orders/{order_id}", response_model=OrderDetail)
@limiter.limit("20/minute")  # Max 20 cancellations per minute per IP
async def cancel_order(
    request: Request,
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
    logger.info(f"🌐 API Endpoint: DELETE /trading/orders/{order_id} | Account: {account_no or 'default'}")

    client = get_dnse_client()

    try:
        result = await client.cancel_order(order_id, account_no)

        # Track cancellation metrics
        track_order_cancelled(symbol=result.symbol)

        logger.info(f"✅ API Response: Order cancelled | New status: {result.orderStatus}")
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error cancelling order: {str(e)}", exc_info=True)
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
    logger.info(f"🌐 API Endpoint: GET /trading/portfolio | Account: {account_no or 'default'}")

    client = get_dnse_client()

    try:
        result = await client.get_deals(account_no)
        logger.info(f"✅ API Response: Retrieved {len(result)} positions")
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting portfolio: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio: {str(e)}"
        )


# ============================================================================
# CONDITIONAL ORDERS
# ============================================================================

@router.post("/conditional-orders", response_model=ConditionalOrderCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Max 5 conditional orders per minute per IP
async def place_conditional_order(request: Request, order: ConditionalOrderRequest) -> ConditionalOrderCreateResponse:
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
    logger.info("=" * 80)
    logger.info(f"🌐 API Endpoint: POST /trading/conditional-orders")
    logger.info(f"Conditional order request: {order.symbol} | Condition: {order.condition} | Stop Price: {order.stopPrice}")

    client = get_dnse_client()

    try:
        result = await client.place_conditional_order(order)
        logger.info(f"✅ API Response: Conditional order placed | Order ID: {result.orderId}")
        logger.info("=" * 80)
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error placing conditional order: {str(e)}", exc_info=True)
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
    logger.info(f"🌐 API Endpoint: GET /trading/conditional-orders | Symbol: {symbol or 'All'} | Daily: {daily}")

    client = get_dnse_client()

    try:
        result = await client.get_conditional_orders(
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
        order_count = len(result.get("content", [])) if isinstance(result, dict) else 0
        logger.info(f"✅ API Response: Retrieved {order_count} conditional orders")
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting conditional orders: {str(e)}", exc_info=True)
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
    logger.info(f"🌐 API Endpoint: GET /trading/conditional-orders/{order_id}")

    client = get_dnse_client()

    try:
        result = await client.get_conditional_order_by_id(order_id)
        logger.info(f"✅ API Response: Conditional order retrieved | Symbol: {result.symbol} | Status: {result.status}")
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting conditional order: {str(e)}", exc_info=True)
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
    logger.info(f"🌐 API Endpoint: PATCH /trading/conditional-orders/{order_id}/cancel")

    client = get_dnse_client()

    try:
        result = await client.cancel_conditional_order(order_id)
        logger.info(f"✅ API Response: Conditional order cancelled | Order ID: {result.orderId}")
        return result
    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error cancelling conditional order: {str(e)}", exc_info=True)
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
