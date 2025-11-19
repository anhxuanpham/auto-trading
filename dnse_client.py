"""
Core Async HTTP wrapper for DNSE Lightspeed API.
Handles authentication, token management, and API requests.
"""
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException

from config import get_settings
from schemas import (
    LoginRequest,
    PlaceOrderPayload,
    OrderDetail,
    Deal,
    ConditionalOrderRequest,
    ConditionalOrderDetail,
    ConditionalOrderCreateResponse
)

logger = logging.getLogger(__name__)


class DNSEClient:
    """
    Async HTTP client for DNSE Lightspeed API.

    Features:
    - Automatic JWT authentication
    - Token expiration tracking (8 hours)
    - Auto-relogin on 401 errors
    - Thread-safe singleton pattern
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.API_BASE_URL
        self.jwt_token: Optional[str] = None
        self.jwt_expires_at: Optional[datetime] = None
        self.client: Optional[httpx.AsyncClient] = None
        logger.info(f"🔧 DNSEClient initialized | Base URL: {self.base_url}")

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure async client is initialized with optimized connection pool."""
        if self.client is None:
            logger.debug("Creating new httpx.AsyncClient with optimized settings")
            # Configure connection pool limits for better performance
            limits = httpx.Limits(
                max_keepalive_connections=20,  # Keep 20 connections alive
                max_connections=100,            # Max 100 concurrent connections
                keepalive_expiry=30.0          # Keep connections alive for 30s
            )
            self.client = httpx.AsyncClient(
                timeout=30.0,
                limits=limits,
                http2=True  # Enable HTTP/2 for better performance
            )
            logger.debug("✅ HTTP client configured: max_connections=100, keepalive=20, http2=enabled")
        return self.client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client:
            logger.info("🔒 Closing DNSE HTTP client")
            await self.client.aclose()
            self.client = None
            logger.debug("HTTP client closed successfully")

    def _is_token_expired(self) -> bool:
        """Check if JWT token is expired or about to expire."""
        if self.jwt_token is None or self.jwt_expires_at is None:
            logger.debug("JWT token not set, needs login")
            return True
        # Consider token expired 5 minutes before actual expiration
        time_until_expiry = self.jwt_expires_at - datetime.now()
        is_expired = datetime.now() >= (self.jwt_expires_at - timedelta(minutes=5))
        if is_expired:
            logger.info(f"🔑 JWT token expired or expiring soon (expires in {time_until_expiry})")
        return is_expired

    async def _login(self) -> str:
        """
        Authenticate with DNSE API and get JWT token.

        Returns:
            str: JWT token

        Raises:
            HTTPException: If login fails
        """
        client = await self._ensure_client()
        login_url = f"{self.base_url}/auth-service/login"

        payload = LoginRequest(
            username=self.settings.DNSE_USERNAME,
            password=self.settings.DNSE_PASSWORD
        )

        logger.info("=" * 80)
        logger.info(f"🔐 Attempting DNSE login | User: {self.settings.DNSE_USERNAME}")
        logger.info(f"🔗 Login URL: {login_url}")

        try:
            response = await client.post(
                login_url,
                json=payload.model_dump()
            )
            logger.debug(f"Login response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()

            if "token" not in data:
                logger.error("❌ Login response missing JWT token")
                raise HTTPException(
                    status_code=500,
                    detail="Login response missing token"
                )

            self.jwt_token = data["token"]
            # JWT expires in 8 hours
            self.jwt_expires_at = datetime.now() + timedelta(
                hours=self.settings.JWT_EXPIRATION_HOURS
            )

            logger.info(f"✅ Login successful!")
            logger.info(f"🔑 JWT Token: {'*' * 20}{self.jwt_token[-6:] if len(self.jwt_token) > 6 else '***'}")
            logger.info(f"⏰ Token expires at: {self.jwt_expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 80)

            return self.jwt_token

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Login failed | Status: {e.response.status_code}", exc_info=True)
            logger.error(f"Response body: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Login failed: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"❌ Login error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Login error: {str(e)}"
            )

    async def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers with valid JWT.
        Auto-login if token is expired.

        Returns:
            Dict[str, str]: Headers with Authorization and Trading-Token
        """
        # Refresh settings to get latest TRADING_TOKEN
        logger.debug("Refreshing settings to get latest TRADING_TOKEN")
        self.settings = get_settings()

        # Login if token is expired
        if self._is_token_expired():
            logger.info("🔄 JWT token needs refresh, logging in...")
            await self._login()

        logger.debug(f"Using Trading-Token: {'*' * 10}{self.settings.TRADING_TOKEN[-4:] if len(self.settings.TRADING_TOKEN) > 4 else '****'}")
        return {
            "Authorization": f"Bearer {self.jwt_token}",
            "Trading-Token": self.settings.TRADING_TOKEN
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True
    ) -> Dict[str, Any]:
        """
        Make authenticated HTTP request to DNSE API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json_data: JSON payload for POST requests
            params: Query parameters for GET requests
            retry_on_401: If True, retry once on 401 error after re-login

        Returns:
            Dict[str, Any]: Response JSON

        Raises:
            HTTPException: If request fails
        """
        client = await self._ensure_client()
        url = f"{self.base_url}{endpoint}"
        headers = await self._get_auth_headers()

        logger.info("-" * 80)
        logger.info(f"📤 HTTP Request | {method} {endpoint}")
        if params:
            logger.debug(f"Query params: {params}")
        if json_data:
            logger.debug(f"Request payload: {json_data}")

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params
            )
            logger.info(f"📥 Response | Status: {response.status_code}")
            response.raise_for_status()
            response_data = response.json()
            logger.debug(f"Response data: {str(response_data)[:500]}...")  # First 500 chars
            return response_data

        except httpx.HTTPStatusError as e:
            # Auto-retry on 401 Unauthorized
            if e.response.status_code == 401 and retry_on_401:
                logger.warning(f"⚠️ 401 Unauthorized - Token invalid, forcing re-login...")
                # Force re-login
                self.jwt_token = None
                await self._login()
                logger.info(f"🔄 Retrying request: {method} {endpoint}")
                # Retry once (with retry_on_401=False to prevent infinite loop)
                return await self._request(
                    method, endpoint, json_data, params, retry_on_401=False
                )

            logger.error(f"❌ HTTP Error | Status: {e.response.status_code}", exc_info=True)
            logger.error(f"Response body: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"API request failed: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"❌ Request error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Request error: {str(e)}"
            )

    # Trading Operations - Regular Orders

    async def place_order(self, order: PlaceOrderPayload) -> OrderDetail:
        """
        Place a new order.

        Args:
            order: Order details including accountNo

        Returns:
            OrderDetail: Complete order information from API
        """
        logger.info("=" * 80)
        logger.info(f"📝 Placing Order | {order.side} {order.symbol} | Qty: {order.quantity} | Price: {order.price} | Type: {order.orderType}")
        logger.info(f"Account: {order.accountNo}")

        response = await self._request(
            method="POST",
            endpoint="/order-service/v2/orders",
            json_data=order.model_dump()
        )

        order_detail = OrderDetail(**response)
        logger.info(f"✅ Order placed successfully | Order ID: {order_detail.id} | Status: {order_detail.orderStatus}")
        logger.info("=" * 80)
        return order_detail

    async def get_orders(self, account_no: Optional[str] = None) -> list[OrderDetail]:
        """
        Get list of orders for an account.

        Args:
            account_no: Account number (defaults to config value)

        Returns:
            list[OrderDetail]: List of orders
        """
        if account_no is None:
            account_no = self.settings.DNSE_ACCOUNT_NO

        logger.info(f"📋 Fetching orders | Account: {account_no}")

        response = await self._request(
            method="GET",
            endpoint="/order-service/v2/orders",
            params={"accountNo": account_no}
        )

        # Parse response - API might return list directly or wrapped in object
        if isinstance(response, list):
            orders_data = response
        elif isinstance(response, dict) and "orders" in response:
            orders_data = response["orders"]
        else:
            orders_data = []

        orders = [OrderDetail(**order) for order in orders_data]
        logger.info(f"✅ Retrieved {len(orders)} orders")
        return orders

    async def get_order_by_id(
        self,
        order_id: int,
        account_no: Optional[str] = None
    ) -> OrderDetail:
        """
        Get details of a specific order.

        Args:
            order_id: Order ID
            account_no: Account number (defaults to config value)

        Returns:
            OrderDetail: Complete order information
        """
        if account_no is None:
            account_no = self.settings.DNSE_ACCOUNT_NO

        logger.info(f"🔍 Fetching order details | Order ID: {order_id} | Account: {account_no}")

        response = await self._request(
            method="GET",
            endpoint=f"/order-service/v2/orders/{order_id}",
            params={"accountNo": account_no}
        )

        order_detail = OrderDetail(**response)
        logger.info(f"✅ Order details retrieved | Symbol: {order_detail.symbol} | Status: {order_detail.orderStatus}")
        return order_detail

    async def cancel_order(
        self,
        order_id: int,
        account_no: Optional[str] = None
    ) -> OrderDetail:
        """
        Cancel an existing order.

        Args:
            order_id: Order ID
            account_no: Account number (defaults to config value)

        Returns:
            OrderDetail: Updated order information after cancellation
        """
        if account_no is None:
            account_no = self.settings.DNSE_ACCOUNT_NO

        logger.info(f"🚫 Cancelling order | Order ID: {order_id} | Account: {account_no}")

        response = await self._request(
            method="DELETE",
            endpoint=f"/order-service/v2/orders/{order_id}",
            params={"accountNo": account_no}
        )

        order_detail = OrderDetail(**response)
        logger.info(f"✅ Order cancelled successfully | New status: {order_detail.orderStatus}")
        return order_detail

    # Portfolio/Deals Operations

    async def get_deals(self, account_no: Optional[str] = None) -> list[Deal]:
        """
        Get portfolio (deals) for an account.

        Args:
            account_no: Account number (defaults to config value)

        Returns:
            list[Deal]: List of deals/positions
        """
        if account_no is None:
            account_no = self.settings.DNSE_ACCOUNT_NO

        logger.info(f"💼 Fetching portfolio (deals) | Account: {account_no}")

        response = await self._request(
            method="GET",
            endpoint="/deal-service/deals",
            params={"accountNo": account_no}
        )

        # Parse response - API might return list directly or wrapped in object
        if isinstance(response, list):
            deals_data = response
        elif isinstance(response, dict) and "deals" in response:
            deals_data = response["deals"]
        else:
            deals_data = []

        deals = [Deal(**deal) for deal in deals_data]
        logger.info(f"✅ Retrieved {len(deals)} positions")
        if deals:
            symbols = [deal.symbol for deal in deals[:5]]
            logger.debug(f"Top symbols: {', '.join(symbols)}{' ...' if len(deals) > 5 else ''}")
        return deals

    # Conditional Orders Operations

    async def place_conditional_order(
        self,
        order: ConditionalOrderRequest
    ) -> ConditionalOrderCreateResponse:
        """
        Place a conditional order.

        Args:
            order: Conditional order details

        Returns:
            ConditionalOrderCreateResponse: Response with conditional order ID
        """
        logger.info("=" * 80)
        logger.info(f"⚡ Placing Conditional Order | {order.side} {order.symbol}")
        logger.info(f"Stop Price: {order.stopPrice} | Limit Price: {order.limitPrice} | Qty: {order.quantity}")

        response = await self._request(
            method="POST",
            endpoint="/conditional-order-api/v1/orders",
            json_data=order.model_dump()
        )

        result = ConditionalOrderCreateResponse(**response)
        logger.info(f"✅ Conditional order placed | Order ID: {result.orderId}")
        logger.info("=" * 80)
        return result

    async def get_conditional_orders(
        self,
        account_no: Optional[str] = None,
        daily: bool = False,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        size: int = 10000,
        status: Optional[list[str]] = None,
        symbol: Optional[str] = None,
        market_id: str = "UNDERLYING"
    ) -> Dict[str, Any]:
        """
        Get list of conditional orders.

        Args:
            account_no: Account number (defaults to config value)
            daily: Get today's orders only (default: False)
            from_date: Start date (yyyy-MM-dd)
            to_date: End date (yyyy-MM-dd)
            page: Page number
            size: Items per page
            status: List of statuses to filter (NEW/ACTIVATED/REJECTED/etc.)
            symbol: Filter by symbol
            market_id: UNDERLYING (stocks) or DERIVATIVES

        Returns:
            Dict with 'content' (list of orders) and pagination info
        """
        if account_no is None:
            account_no = self.settings.DNSE_ACCOUNT_NO

        logger.info(f"📋 Fetching conditional orders | Account: {account_no} | Daily: {daily} | Symbol: {symbol or 'All'}")

        params: Dict[str, Any] = {
            "accountNo": account_no,
            "daily": daily,
            "page": page,
            "size": size,
            "marketId": market_id
        }

        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol

        response = await self._request(
            method="GET",
            endpoint="/conditional-order-api/v1/orders",
            params=params
        )

        order_count = len(response.get("content", [])) if isinstance(response, dict) else 0
        logger.info(f"✅ Retrieved {order_count} conditional orders")
        return response

    async def get_conditional_order_by_id(
        self,
        order_id: str
    ) -> ConditionalOrderDetail:
        """
        Get details of a specific conditional order.

        Args:
            order_id: Conditional order ID

        Returns:
            ConditionalOrderDetail: Complete conditional order information
        """
        logger.info(f"🔍 Fetching conditional order | Order ID: {order_id}")

        response = await self._request(
            method="GET",
            endpoint=f"/conditional-order-api/v1/orders/{order_id}"
        )

        order_detail = ConditionalOrderDetail(**response)
        logger.info(f"✅ Conditional order retrieved | Symbol: {order_detail.symbol} | Status: {order_detail.status}")
        return order_detail

    async def cancel_conditional_order(
        self,
        order_id: str
    ) -> ConditionalOrderCreateResponse:
        """
        Cancel a conditional order.

        Args:
            order_id: Conditional order ID

        Returns:
            ConditionalOrderCreateResponse: Response with order ID
        """
        logger.info(f"🚫 Cancelling conditional order | Order ID: {order_id}")

        response = await self._request(
            method="PATCH",
            endpoint=f"/conditional-order-api/v1/orders/{order_id}/cancel"
        )

        result = ConditionalOrderCreateResponse(**response)
        logger.info(f"✅ Conditional order cancelled | Order ID: {result.orderId}")
        return result


# Global client instance
_client: Optional[DNSEClient] = None


def get_dnse_client() -> DNSEClient:
    """
    Get or create the global DNSE client instance.

    Returns:
        DNSEClient: Singleton client instance
    """
    global _client
    if _client is None:
        logger.info("Creating new DNSEClient singleton instance")
        _client = DNSEClient()
    return _client


async def close_dnse_client() -> None:
    """Close the global DNSE client."""
    global _client
    if _client:
        logger.info("Closing global DNSE client instance")
        await _client.close()
        _client = None
        logger.debug("Global DNSE client instance cleared")
