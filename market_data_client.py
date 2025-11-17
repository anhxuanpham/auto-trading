"""
MQTT client for DNSE Market Data streaming.
Connects to datafeed-lts-krx.dnse.com.vn via WebSocket/MQTT.
"""
import json
import asyncio
import logging
from typing import Optional, Callable, Dict, Any, Set
from datetime import datetime
import random
import string

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None  # Will be handled in __init__

from market_data_schemas import MessageType, get_topic
from config import get_settings


logger = logging.getLogger(__name__)


class MarketDataClient:
    """
    Async MQTT client for DNSE Market Data.

    Features:
    - Auto-reconnection with exponential backoff
    - Multiple topic subscriptions
    - Callback-based message handling
    - Clean disconnect/cleanup
    """

    def __init__(
        self,
        investor_id: str,
        token: str,
        on_message_callback: Optional[Callable[[MessageType, Dict[str, Any]], None]] = None
    ):
        """
        Initialize market data client.

        Args:
            investor_id: Investor ID from user-service/api/me
            token: JWT token from authentication
            on_message_callback: Callback function(message_type, data)

        Raises:
            ImportError: If paho-mqtt is not installed
        """
        if mqtt is None:
            raise ImportError(
                "paho-mqtt is required for market data. "
                "Install with: pip install paho-mqtt"
            )

        self.investor_id = investor_id
        self.token = token
        self.on_message_callback = on_message_callback

        # MQTT configuration
        self.host = "datafeed-lts-krx.dnse.com.vn"
        self.port = 443
        self.path = "/wss"

        # Generate client ID
        random_seq = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.client_id = f"dnse-price-json-mqtt-ws-sub-{self.investor_id}-{random_seq}"

        # MQTT client
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.subscribed_topics: Set[str] = set()

        # Reconnection
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2  # seconds

    def _create_client(self) -> mqtt.Client:
        """Create and configure MQTT client."""
        # Use MQTTv311 for WebSocket
        client = mqtt.Client(
            client_id=self.client_id,
            transport="websockets",
            protocol=mqtt.MQTTv311
        )

        # Set authentication
        client.username_pw_set(self.investor_id, self.token)

        # Configure WebSocket path
        client.ws_set_options(path=self.path)

        # Set TLS/SSL
        client.tls_set()

        # Set callbacks
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message

        return client

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            logger.info(f"✅ Connected to DNSE Market Data (client_id: {self.client_id})")
            self.connected = True
            self.reconnect_attempts = 0

            # Re-subscribe to all topics
            if self.subscribed_topics:
                logger.info(f"Re-subscribing to {len(self.subscribed_topics)} topics...")
                for topic in self.subscribed_topics:
                    client.subscribe(topic, qos=0)
        else:
            logger.error(f"❌ Connection failed with code {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️ Unexpected disconnect (code: {rc}). Will attempt to reconnect...")
            self._attempt_reconnect()
        else:
            logger.info("Disconnected from DNSE Market Data")

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            # Parse JSON message
            payload = json.loads(msg.payload.decode('utf-8'))

            # Determine message type from topic
            message_type = self._get_message_type_from_topic(msg.topic)

            # Add timestamp
            payload['_received_at'] = datetime.now().isoformat()

            logger.debug(f"Received {message_type}: {payload}")

            # Call user callback
            if self.on_message_callback:
                self.on_message_callback(message_type, payload)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _get_message_type_from_topic(self, topic: str) -> str:
        """Extract message type from MQTT topic."""
        if "stockinfo" in topic:
            return MessageType.STOCK_INFO
        elif "topprice" in topic:
            return MessageType.TOP_PRICE
        elif "boardevent" in topic:
            return MessageType.BOARD_EVENT
        elif "index" in topic and "ohlc" not in topic:
            return MessageType.MARKET_INDEX
        elif "ohlc" in topic:
            return MessageType.OHLC
        elif "tick" in topic:
            return MessageType.TICK
        else:
            return "UNKNOWN"

    def _attempt_reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Giving up.")
            return

        self.reconnect_attempts += 1
        delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))

        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})...")
        asyncio.get_event_loop().call_later(delay, self._reconnect)

    def _reconnect(self):
        """Perform reconnection."""
        try:
            if self.client:
                self.client.reconnect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            self._attempt_reconnect()

    def connect(self) -> bool:
        """
        Connect to DNSE Market Data feed.

        Returns:
            bool: True if connected successfully
        """
        try:
            self.client = self._create_client()
            logger.info(f"Connecting to {self.host}:{self.port}{self.path}...")
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from market data feed."""
        if self.client:
            logger.info("Disconnecting from market data...")
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    def subscribe(self, message_type: MessageType, **kwargs) -> bool:
        """
        Subscribe to a market data topic.

        Args:
            message_type: Type of market data
            **kwargs: Parameters for topic (symbol, indexName, etc.)

        Returns:
            bool: True if subscribed successfully

        Examples:
            >>> client.subscribe(MessageType.STOCK_INFO, symbol="VNM")
            >>> client.subscribe(MessageType.MARKET_INDEX, indexName="VNINDEX")
            >>> client.subscribe(MessageType.OHLC, resolution="1D", symbol="HPG")
        """
        if not self.client:
            logger.error("Client not initialized")
            return False

        try:
            topic = get_topic(message_type, **kwargs)
            result, mid = self.client.subscribe(topic, qos=0)

            if result == mqtt.MQTT_ERR_SUCCESS:
                self.subscribed_topics.add(topic)
                logger.info(f"✅ Subscribed to: {topic}")
                return True
            else:
                logger.error(f"❌ Subscription failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return False

    def unsubscribe(self, message_type: MessageType, **kwargs) -> bool:
        """
        Unsubscribe from a market data topic.

        Args:
            message_type: Type of market data
            **kwargs: Parameters for topic

        Returns:
            bool: True if unsubscribed successfully
        """
        if not self.client:
            return False

        try:
            topic = get_topic(message_type, **kwargs)
            result, mid = self.client.unsubscribe(topic)

            if result == mqtt.MQTT_ERR_SUCCESS:
                self.subscribed_topics.discard(topic)
                logger.info(f"Unsubscribed from: {topic}")
                return True
            else:
                logger.error(f"Unsubscribe failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if connected to market data feed."""
        return self.connected

    def get_subscribed_topics(self) -> list:
        """Get list of currently subscribed topics."""
        return list(self.subscribed_topics)


# Global client instance
_market_data_client: Optional[MarketDataClient] = None


def get_market_data_client() -> Optional[MarketDataClient]:
    """Get global market data client instance."""
    return _market_data_client


def set_market_data_client(client: MarketDataClient):
    """Set global market data client instance."""
    global _market_data_client
    _market_data_client = client


def close_market_data_client():
    """Close and cleanup global market data client."""
    global _market_data_client
    if _market_data_client:
        _market_data_client.disconnect()
        _market_data_client = None
