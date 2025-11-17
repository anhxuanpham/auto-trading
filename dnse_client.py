"""
Core Async HTTP wrapper for DNSE Lightspeed API.
Handles authentication, token management, and API requests.
"""
import httpx
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

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure async client is initialized."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)
        return self.client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    def _is_token_expired(self) -> bool:
        """Check if JWT token is expired or about to expire."""
        if self.jwt_token is None or self.jwt_expires_at is None:
            return True
        # Consider token expired 5 minutes before actual expiration
        return datetime.now() >= (self.jwt_expires_at - timedelta(minutes=5))

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

        try:
            response = await client.post(
                login_url,
                json=payload.model_dump()
            )
            response.raise_for_status()
            data = response.json()

            if "token" not in data:
                raise HTTPException(
                    status_code=500,
                    detail="Login response missing token"
                )

            self.jwt_token = data["token"]
            # JWT expires in 8 hours
            self.jwt_expires_at = datetime.now() + timedelta(
                hours=self.settings.JWT_EXPIRATION_HOURS
            )

            return self.jwt_token

        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Login failed: {e.response.text}"
            )
        except Exception as e:
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
        self.settings = get_settings()

        # Login if token is expired
        if self._is_token_expired():
            await self._login()

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

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            # Auto-retry on 401 Unauthorized
            if e.response.status_code == 401 and retry_on_401:
                # Force re-login
                self.jwt_token = None
                await self._login()
                # Retry once (with retry_on_401=False to prevent infinite loop)
                return await self._request(
                    method, endpoint, json_data, params, retry_on_401=False
                )

            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"API request failed: {e.response.text}"
            )
        except Exception as e:
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
        response = await self._request(
            method="POST",
            endpoint="/order-service/v2/orders",
            json_data=order.model_dump()
        )
        return OrderDetail(**response)

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

        return [OrderDetail(**order) for order in orders_data]

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

        response = await self._request(
            method="GET",
            endpoint=f"/order-service/v2/orders/{order_id}",
            params={"accountNo": account_no}
        )
        return OrderDetail(**response)

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

        response = await self._request(
            method="DELETE",
            endpoint=f"/order-service/v2/orders/{order_id}",
            params={"accountNo": account_no}
        )
        return OrderDetail(**response)

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

        return [Deal(**deal) for deal in deals_data]

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
        response = await self._request(
            method="POST",
            endpoint="/conditional-order-api/v1/orders",
            json_data=order.model_dump()
        )
        return ConditionalOrderCreateResponse(**response)

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

        return await self._request(
            method="GET",
            endpoint="/conditional-order-api/v1/orders",
            params=params
        )

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
        response = await self._request(
            method="GET",
            endpoint=f"/conditional-order-api/v1/orders/{order_id}"
        )
        return ConditionalOrderDetail(**response)

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
        response = await self._request(
            method="PATCH",
            endpoint=f"/conditional-order-api/v1/orders/{order_id}/cancel"
        )
        return ConditionalOrderCreateResponse(**response)


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
        _client = DNSEClient()
    return _client


async def close_dnse_client() -> None:
    """Close the global DNSE client."""
    global _client
    if _client:
        await _client.close()
        _client = None
