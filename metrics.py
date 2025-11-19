"""
Prometheus metrics for monitoring application performance.
Tracks requests, orders, errors, and latencies.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time

# ============================================================================
# METRICS DEFINITIONS
# ============================================================================

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# Trading metrics
orders_placed_total = Counter(
    'orders_placed_total',
    'Total orders placed',
    ['symbol', 'side', 'order_type', 'status']
)

orders_cancelled_total = Counter(
    'orders_cancelled_total',
    'Total orders cancelled',
    ['symbol']
)

order_placement_duration_seconds = Histogram(
    'order_placement_duration_seconds',
    'Order placement latency',
    ['symbol', 'side']
)

# Market data metrics
market_data_messages_total = Counter(
    'market_data_messages_total',
    'Total market data messages received',
    ['message_type', 'symbol']
)

websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections'
)

mqtt_connection_status = Gauge(
    'mqtt_connection_status',
    'MQTT connection status (1=connected, 0=disconnected)'
)

# Error metrics
errors_total = Counter(
    'errors_total',
    'Total errors by type',
    ['error_type', 'endpoint']
)

# System metrics
jwt_token_refreshes_total = Counter(
    'jwt_token_refreshes_total',
    'Total JWT token refreshes'
)

api_calls_to_dnse_total = Counter(
    'api_calls_to_dnse_total',
    'Total API calls to DNSE',
    ['endpoint', 'status']
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def track_order_placed(symbol: str, side: str, order_type: str, status: str = 'success'):
    """Track a placed order."""
    orders_placed_total.labels(
        symbol=symbol,
        side=side,
        order_type=order_type,
        status=status
    ).inc()


def track_order_cancelled(symbol: str):
    """Track a cancelled order."""
    orders_cancelled_total.labels(symbol=symbol).inc()


def track_market_data_message(message_type: str, symbol: str):
    """Track a market data message."""
    market_data_messages_total.labels(
        message_type=message_type,
        symbol=symbol
    ).inc()


def track_error(error_type: str, endpoint: str):
    """Track an error."""
    errors_total.labels(
        error_type=error_type,
        endpoint=endpoint
    ).inc()


def track_dnse_api_call(endpoint: str, status: str):
    """Track an API call to DNSE."""
    api_calls_to_dnse_total.labels(
        endpoint=endpoint,
        status=status
    ).inc()


# ============================================================================
# METRICS ENDPOINT
# ============================================================================

def metrics_response() -> Response:
    """Generate Prometheus metrics response."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
