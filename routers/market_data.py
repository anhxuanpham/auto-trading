"""
Market Data endpoints for real-time streaming.
Provides WebSocket connections for live market data from DNSE.
"""
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status, Depends
from pydantic import BaseModel

from market_data_schemas import MessageType, MarketDataSubscription
from market_data_client import MarketDataClient, get_market_data_client, set_market_data_client
from dnse_client import get_dnse_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market-data", tags=["Market Data"])


# ============================================================================
# CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections and broadcast messages."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.message_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ New WebSocket client connected (total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected (remaining: {len(self.active_connections)})")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)


# Global connection manager
connection_manager = ConnectionManager()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_investor_id() -> str:
    """
    Get investor ID by calling DNSE user info API.

    Returns:
        str: Investor ID

    Raises:
        HTTPException: If unable to get investor ID
    """
    logger.info("📡 Fetching investor ID from DNSE user API")
    try:
        dnse_client = get_dnse_client()

        # Ensure we have valid JWT
        headers = await dnse_client._get_auth_headers()
        jwt_token = headers["Authorization"].replace("Bearer ", "")

        # Call user info API
        logger.debug(f"Calling user-service/api/me endpoint")
        client = await dnse_client._ensure_client()
        response = await client.get(
            f"{dnse_client.base_url}/user-service/api/me",
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        response.raise_for_status()
        user_data = response.json()

        investor_id = user_data.get("investorId")
        if not investor_id:
            logger.error("❌ No investorId found in user info response")
            raise HTTPException(
                status_code=500,
                detail="No investorId in user info"
            )

        logger.info(f"✅ Investor ID retrieved: {investor_id}")
        return investor_id

    except Exception as e:
        logger.error(f"❌ Failed to get investor ID: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get investor ID: {str(e)}"
        )


def market_data_callback(message_type: str, data: Dict[str, Any]):
    """
    Callback for market data messages.
    Broadcasts to all WebSocket clients.
    """
    message = {
        "type": message_type,
        "data": data,
        "timestamp": data.get("_received_at")
    }
    # Schedule broadcast in event loop
    asyncio.create_task(connection_manager.broadcast(message))


# ============================================================================
# REST ENDPOINTS
# ============================================================================

class InitializeRequest(BaseModel):
    """Request to initialize market data connection."""
    auto_connect: bool = True


class InitializeResponse(BaseModel):
    """Response after initializing market data."""
    success: bool
    message: str
    connected: bool
    client_id: Optional[str] = None


@router.post("/initialize", response_model=InitializeResponse)
async def initialize_market_data(request: InitializeRequest = InitializeRequest()) -> InitializeResponse:
    """
    Initialize market data connection.

    This must be called before using market data features.
    It authenticates with DNSE and establishes MQTT connection.

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/market-data/initialize"
    ```

    **Returns:** Connection status and client ID.
    """
    logger.info("=" * 80)
    logger.info("🌐 API Endpoint: POST /market-data/initialize")
    logger.info(f"Auto-connect: {request.auto_connect}")

    try:
        # Check if already initialized
        existing_client = get_market_data_client()
        if existing_client and existing_client.is_connected():
            logger.info(f"✅ Market data already initialized | Client ID: {existing_client.client_id}")
            logger.info("=" * 80)
            return InitializeResponse(
                success=True,
                message="Market data already initialized",
                connected=True,
                client_id=existing_client.client_id
            )

        # Get credentials
        investor_id = await get_investor_id()
        dnse_client = get_dnse_client()
        headers = await dnse_client._get_auth_headers()
        jwt_token = headers["Authorization"].replace("Bearer ", "")

        # Create market data client
        logger.info(f"🔧 Creating MarketDataClient | Investor ID: {investor_id}")
        md_client = MarketDataClient(
            investor_id=investor_id,
            token=jwt_token,
            on_message_callback=market_data_callback
        )

        # Connect if requested
        if request.auto_connect:
            logger.info("🔌 Connecting to MQTT broker...")
            success = md_client.connect()
            if not success:
                logger.error("❌ Failed to connect to market data feed")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to connect to market data feed"
                )
            logger.info("✅ MQTT connection established")

        # Store global instance
        set_market_data_client(md_client)

        logger.info(f"✅ API Response: Market data initialized | Client ID: {md_client.client_id}")
        logger.info("=" * 80)

        return InitializeResponse(
            success=True,
            message="Market data initialized successfully",
            connected=md_client.is_connected(),
            client_id=md_client.client_id
        )

    except HTTPException as e:
        logger.error(f"❌ API Error: {e.status_code} - {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Initialization error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize market data: {str(e)}"
        )


class SubscribeResponse(BaseModel):
    """Response after subscribing."""
    success: bool
    message: str
    topic: Optional[str] = None


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe_market_data(subscription: MarketDataSubscription) -> SubscribeResponse:
    """
    Subscribe to a market data topic.

    **Examples:**

    Subscribe to stock info:
    ```json
    {
        "messageType": "STOCK_INFO",
        "symbol": "VNM"
    }
    ```

    Subscribe to market index:
    ```json
    {
        "messageType": "MARKET_INDEX",
        "indexName": "VNINDEX"
    }
    ```

    Subscribe to OHLC:
    ```json
    {
        "messageType": "OHLC",
        "symbol": "HPG",
        "resolution": "1D"
    }
    ```

    **Returns:** Subscription confirmation.
    """
    logger.info("=" * 80)
    logger.info("🌐 API Endpoint: POST /market-data/subscribe")
    logger.info(f"Subscription: {subscription.messageType} | Symbol: {subscription.symbol or 'N/A'} | Index: {subscription.indexName or 'N/A'}")

    client = get_market_data_client()
    if not client:
        logger.error("❌ Market data client not initialized")
        raise HTTPException(
            status_code=400,
            detail="Market data not initialized. Call /initialize first."
        )

    if not client.is_connected():
        logger.error("❌ Market data client not connected")
        raise HTTPException(
            status_code=503,
            detail="Market data client not connected"
        )

    try:
        # Build kwargs for topic
        kwargs = {}
        if subscription.symbol:
            kwargs["symbol"] = subscription.symbol
        if subscription.indexName:
            kwargs["indexName"] = subscription.indexName
        if subscription.resolution:
            kwargs["resolution"] = subscription.resolution
        if subscription.marketId:
            kwargs["marketId"] = subscription.marketId
        if subscription.productGroupId:
            kwargs["productGroupId"] = subscription.productGroupId

        # Subscribe
        logger.info(f"📡 Subscribing to MQTT topic...")
        success = client.subscribe(subscription.messageType, **kwargs)

        if success:
            from market_data_schemas import get_topic
            topic = get_topic(subscription.messageType, **kwargs)
            logger.info(f"✅ API Response: Subscribed successfully | Topic: {topic}")
            logger.info("=" * 80)
            return SubscribeResponse(
                success=True,
                message=f"Subscribed to {subscription.messageType}",
                topic=topic
            )
        else:
            logger.error("❌ Subscription failed")
            raise HTTPException(
                status_code=500,
                detail="Subscription failed"
            )

    except ValueError as e:
        logger.error(f"❌ Invalid subscription parameters: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Subscribe error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Subscription error: {str(e)}"
        )


@router.get("/status")
async def get_market_data_status() -> dict:
    """
    Get market data connection status.

    **Returns:**
    - connected: Whether MQTT client is connected
    - subscribed_topics: List of active subscriptions
    - active_websockets: Number of WebSocket clients
    """
    logger.debug("🌐 API Endpoint: GET /market-data/status")
    client = get_market_data_client()

    if not client:
        logger.debug("Market data client not initialized")
        return {
            "initialized": False,
            "connected": False,
            "subscribed_topics": [],
            "active_websockets": len(connection_manager.active_connections)
        }

    status = {
        "initialized": True,
        "connected": client.is_connected(),
        "client_id": client.client_id,
        "subscribed_topics": client.get_subscribed_topics(),
        "active_websockets": len(connection_manager.active_connections)
    }
    logger.debug(f"Market data status: {status}")
    return status


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time market data streaming.

    **Usage:**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/market-data/ws');

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Market data:', data);
    };

    ws.onopen = () => {
        console.log('Connected to market data stream');
    };
    ```

    **Message Format:**
    ```json
    {
        "type": "STOCK_INFO",
        "data": {
            "symbol": "VNM",
            "lastPrice": 85500,
            "change": 500,
            "changePercent": 0.59,
            ...
        },
        "timestamp": "2024-01-15T10:30:00.123456"
    }
    ```

    **Note:** You must call POST /market-data/initialize and POST /market-data/subscribe
    before messages will be streamed.
    """
    await connection_manager.connect(websocket)

    try:
        # Keep connection alive and handle client messages
        while True:
            # Wait for client messages (e.g., ping/pong, commands)
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                # Handle ping
                if message.get("type") == "ping":
                    await connection_manager.send_personal(
                        websocket,
                        {"type": "pong", "timestamp": message.get("timestamp")}
                    )

                # Handle status request
                elif message.get("type") == "status":
                    client = get_market_data_client()
                    await connection_manager.send_personal(
                        websocket,
                        {
                            "type": "status",
                            "connected": client.is_connected() if client else False,
                            "topics": client.get_subscribed_topics() if client else []
                        }
                    )

            except json.JSONDecodeError:
                await connection_manager.send_personal(
                    websocket,
                    {"type": "error", "message": "Invalid JSON"}
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)
