"""
Pydantic models for DNSE Market Data messages.
Based on official DNSE MDDS System specifications (from Excel documentation).

CRITICAL: All IntEnum values must match exactly as defined by DNSE.
Do not guess or modify these values.
"""
from enum import Enum, IntEnum
from typing import Optional, Any
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Market data message types."""
    MARKET_INDEX = "MARKET_INDEX"
    STOCK_INFO = "STOCK_INFO"
    TOP_PRICE = "TOP_PRICE"
    BOARD_EVENT = "BOARD_EVENT"
    OHLC = "OHLC"
    TICK = "TICK"


# ============================================================================
# CRITICAL ENUMS - Values from DNSE MDDS Specifications
# ============================================================================

class MarketID(IntEnum):
    """
    Market IDs (EXACT values from DNSE).
    These are returned as integers in API responses.
    """
    UNSPECIFIED = 0
    BDO = 1  # HOSE Bond
    BDX = 2  # HNX Government Bond
    DVX = 3  # HNX Derivative
    HCX = 4  # HNX Corporate Bond
    RPO = 5  # HOSE Repo
    STO = 6  # HOSE Stock (VN30, Stocks, CW, ETF) -> PRIMARY FOCUS
    STX = 7  # HNX Stock -> PRIMARY FOCUS
    UPX = 8  # HNX UpCom


class BoardID(IntEnum):
    """
    Board IDs (EXACT values from DNSE).
    Note: DNSE merges some boards (e.g., G1 includes G7).
    """
    UNSPECIFIED = 0
    AL = 1   # All Boards
    G1 = 2   # Main Board (Round Lot/Lô chẵn) -> MOST IMPORTANT for trading
    G3 = 4   # Post Closing (Sau giờ)
    G4 = 5   # Odd Lot (Lô lẻ)
    T1 = 9   # Negotiation (Thỏa thuận)


class SecurityGroupID(IntEnum):
    """Security/Product group IDs."""
    ST = 7   # Stock
    EW = 3   # Warrant (CW - Covered Warrant)
    EF = 2   # ETF
    FU = 4   # Futures


class TradingSessionID(IntEnum):
    """
    Trading session IDs (EXACT values from DNSE).
    This determines if we can place orders and what order types are allowed.

    CRITICAL for order placement logic!
    """
    GT_ORDER_LOAD = 1        # 01: Pre-day order load
    ATO = 2                  # 10: Opening Call Auction (Khớp lệnh mở cửa)
    ATO_EXT = 3              # 11: ATO extension
    ATC = 6                  # 30: Closing Call Auction (Khớp lệnh đóng cửa)
    CONTINUOUS = 7           # 40: Continuous Matching (Khớp lệnh liên tục) -> MAIN SESSION
    ORDER_ACCEPT_ONLY = 10   # 60: PLO (Post Limit Order - Sau giờ)
    HALT = 13                # 90: Market Halted (Tạm dừng)
    CLOSED = 14              # 99: Market Closed (Đóng cửa)


class SecurityStatus(IntEnum):
    """Security trading status."""
    HALT = 1      # Trading halted
    NO_HALT = 2   # Normal trading


class SymbolAdminStatus(IntEnum):
    """Symbol administrative status codes."""
    CONTROL = 1       # Kiểm soát/Hạn chế giao dịch
    WARNING = 2       # Cảnh báo
    NORMAL = 3        # Bình thường


class IndexName(str, Enum):
    """Index names."""
    VN30 = "VN30"
    VNINDEX = "VNINDEX"
    HNX30 = "HNX30"
    HNX = "HNX"
    UPCOM = "UPCOM"


class Resolution(str, Enum):
    """OHLC resolution."""
    ONE_MINUTE = "1"
    ONE_HOUR = "1H"
    ONE_DAY = "1D"
    ONE_WEEK = "W"


# ============================================================================
# MESSAGE SCHEMAS (Pydantic Models)
# ============================================================================

# Market Index
class MarketIndex(BaseModel):
    """Market index information."""
    indexName: str = Field(..., description="Tên chỉ số (VN30, VNINDEX, etc.)")
    indexValue: Optional[float] = Field(None, description="Giá trị chỉ số")
    change: Optional[float] = Field(None, description="Thay đổi điểm")
    changePercent: Optional[float] = Field(None, description="Thay đổi phần trăm")
    totalVolume: Optional[float] = Field(None, description="Tổng khối lượng")
    totalValue: Optional[float] = Field(None, description="Tổng giá trị")
    advanceCount: Optional[int] = Field(None, description="Số mã tăng")
    noChangeCount: Optional[int] = Field(None, description="Số mã đứng giá")
    declineCount: Optional[int] = Field(None, description="Số mã giảm")
    timestamp: Optional[str] = Field(None, description="Thời gian")


# Stock Info (Snapshot)
class StockInfo(BaseModel):
    """
    Stock price snapshot information.
    CRITICAL: Contains tradingSessionId which determines what orders can be placed.
    """
    symbol: str = Field(..., description="Mã chứng khoán")
    marketId: int = Field(..., description="Market ID (6=STO/HOSE, 7=STX/HNX, 8=UPX)")
    boardId: int = Field(..., description="Board ID (2=G1/Main, 5=G4/Odd Lot)")

    # Price levels
    referencePrice: Optional[float] = Field(None, description="Giá tham chiếu")
    ceilingPrice: Optional[float] = Field(None, description="Giá trần")
    floorPrice: Optional[float] = Field(None, description="Giá sàn")

    # Last trade
    lastPrice: Optional[float] = Field(None, description="Giá khớp lệnh gần nhất")
    lastVolume: Optional[float] = Field(None, description="Khối lượng khớp gần nhất")
    change: Optional[float] = Field(None, description="Thay đổi giá")
    changePercent: Optional[float] = Field(None, description="Thay đổi phần trăm")

    # Volume/Value
    totalVolume: Optional[float] = Field(None, description="Tổng khối lượng")
    totalValue: Optional[float] = Field(None, description="Tổng giá trị")

    # Open/High/Low
    openPrice: Optional[float] = Field(None, description="Giá mở cửa")
    highPrice: Optional[float] = Field(None, description="Giá cao nhất")
    lowPrice: Optional[float] = Field(None, description="Giá thấp nhất")
    averagePrice: Optional[float] = Field(None, description="Giá trung bình")

    # Session info (CRITICAL!)
    tradingSessionId: int = Field(..., description="Trading session ID (2=ATO, 7=CONTINUOUS, 6=ATC, 14=CLOSED)")
    securityStatus: int = Field(..., description="Security status (1=HALT, 2=NO_HALT)")
    symbolAdminStatusCode: int = Field(..., description="Admin status (3=NORMAL, 1=CONTROL, 2=WARNING)")

    # Foreign trading
    foreignBuyVolume: Optional[float] = Field(None, description="KL mua nước ngoài")
    foreignSellVolume: Optional[float] = Field(None, description="KL bán nước ngoài")
    foreignRemain: Optional[float] = Field(None, description="Room nước ngoài còn lại")

    timestamp: Optional[str] = Field(None, description="Thời gian")


# Top Price (Order Book Level 1)
class PriceLevel(BaseModel):
    """Price level for bid/ask."""
    price: Optional[float] = Field(None, description="Giá")
    volume: Optional[float] = Field(None, description="Khối lượng")


class TopPrice(BaseModel):
    """
    Best bid/ask prices (Level 1 order book).
    Use for spread analysis and order placement decisions.
    """
    symbol: str = Field(..., description="Mã chứng khoán")

    # Best bid (buy) prices
    bestBidPrice: Optional[float] = Field(None, alias="bid1Price", description="Giá mua tốt nhất")
    bestBidQuantity: Optional[float] = Field(None, alias="bid1Volume", description="KL mua tốt nhất")

    # Best ask (sell) prices
    bestAskPrice: Optional[float] = Field(None, alias="ask1Price", description="Giá bán tốt nhất")
    bestAskQuantity: Optional[float] = Field(None, alias="ask1Volume", description="KL bán tốt nhất")

    # Additional levels (if available)
    bid2: Optional[PriceLevel] = Field(None, description="Giá mua 2")
    bid3: Optional[PriceLevel] = Field(None, description="Giá mua 3")
    ask2: Optional[PriceLevel] = Field(None, description="Giá bán 2")
    ask3: Optional[PriceLevel] = Field(None, description="Giá bán 3")

    timestamp: Optional[str] = Field(None, description="Thời gian")


# Tick (Trade)
class Tick(BaseModel):
    """
    Real-time trade (tick) information.
    Derive action (B/S) by comparing with previous price.
    """
    symbol: str = Field(..., description="Mã chứng khoán")
    price: Optional[float] = Field(..., description="Giá khớp")
    volume: Optional[int] = Field(..., description="Khối lượng khớp")
    accumulatedVolume: Optional[int] = Field(None, description="Tổng khối lượng tích lũy")
    timestamp: Optional[str] = Field(None, description="Thời gian khớp")

    # Derived field (calculate based on price movement)
    action: Optional[str] = Field(None, description="'B' if buying pressure, 'S' if selling")


# Board Event (Session Change)
class BoardEvent(BaseModel):
    """
    Board/session event notification.
    Triggered when market session changes (e.g., ATO -> CONTINUOUS -> ATC).
    """
    marketId: int = Field(..., description="Market ID (6=STO, 7=STX, 8=UPX)")
    boardId: int = Field(..., description="Board ID (2=G1 main board)")
    tradingSessionId: int = Field(..., description="New trading session ID")
    eventId: Optional[str] = Field(None, description="Event code (e.g., 'AA1', 'BC1')")
    timestamp: Optional[str] = Field(None, description="Thời gian")


# OHLC (Candlestick)
class OHLC(BaseModel):
    """OHLC candlestick data."""
    symbol: str = Field(..., description="Mã CK/Index")
    resolution: str = Field(..., description="Độ phân giải (1/1H/1D/W)")
    timestamp: Optional[str] = Field(None, description="Thời gian")
    open: Optional[float] = Field(None, description="Giá mở")
    high: Optional[float] = Field(None, description="Giá cao nhất")
    low: Optional[float] = Field(None, description="Giá thấp nhất")
    close: Optional[float] = Field(None, description="Giá đóng")
    volume: Optional[float] = Field(None, description="Khối lượng")
    value: Optional[float] = Field(None, description="Giá trị")


# ============================================================================
# SUBSCRIPTION & WRAPPER SCHEMAS
# ============================================================================

class MarketDataSubscription(BaseModel):
    """Subscription request."""
    messageType: MessageType = Field(..., description="Loại message cần subscribe")
    symbol: Optional[str] = Field(None, description="Mã CK (cho STOCK_INFO, TOP_PRICE, TICK, OHLC)")
    indexName: Optional[str] = Field(None, description="Tên index (cho MARKET_INDEX)")
    resolution: Optional[str] = Field(None, description="Resolution cho OHLC")
    marketId: Optional[str] = Field(None, description="Market ID cho BOARD_EVENT")
    productGroupId: Optional[str] = Field(None, description="Product Group ID cho BOARD_EVENT")


class MarketDataMessage(BaseModel):
    """Wrapper for all market data messages."""
    type: MessageType = Field(..., description="Loại message")
    data: Any = Field(..., description="Data payload")
    timestamp: Optional[str] = Field(None, description="Thời gian nhận")


class MarketDataAuth(BaseModel):
    """Authentication info for market data connection."""
    username: str = Field(..., description="Username từ DNSE")
    password: str = Field(..., description="Password từ DNSE")
    investorId: Optional[str] = Field(None, description="Investor ID sau khi login")
    token: Optional[str] = Field(None, description="JWT token sau khi login")


# ============================================================================
# TOPIC TEMPLATES
# ============================================================================

TOPIC_TEMPLATES = {
    "STOCK_INFO": "plaintext/quotes/krx/mdds/stockinfo/v1/roundlot/symbol/{symbol}",
    "TOP_PRICE": "plaintext/quotes/krx/mdds/topprice/v1/roundlot/symbol/{symbol}",
    "BOARD_EVENT": "plaintext/quotes/krx/mdds/boardevent/v1/roundlot/market/{marketId}/product/{productGroupId}",
    "MARKET_INDEX": "plaintext/quotes/krx/mdds/index/{indexName}",
    "STOCK_OHLC": "plaintext/quotes/krx/mdds/v2/ohlc/stock/{resolution}/{symbol}",
    "DERIVATIVE_OHLC": "plaintext/quotes/krx/mdds/v2/ohlc/derivative/{resolution}/{symbol}",
    "INDEX_OHLC": "plaintext/quotes/krx/mdds/v2/ohlc/index/{resolution}/{indexName}",
    "TICK": "plaintext/quotes/krx/mdds/tick/v1/roundlot/symbol/{symbol}",
}


def get_topic(message_type: MessageType, **kwargs) -> str:
    """
    Get MQTT topic for subscription.

    Args:
        message_type: Type of market data
        **kwargs: Parameters for topic (symbol, indexName, etc.)

    Returns:
        str: MQTT topic

    Examples:
        >>> get_topic(MessageType.STOCK_INFO, symbol="VNM")
        'plaintext/quotes/krx/mdds/stockinfo/v1/roundlot/symbol/VNM'

        >>> get_topic(MessageType.MARKET_INDEX, indexName="VNINDEX")
        'plaintext/quotes/krx/mdds/index/VNINDEX'

        >>> get_topic(MessageType.STOCK_OHLC, resolution="1D", symbol="HPG")
        'plaintext/quotes/krx/mdds/v2/ohlc/stock/1D/HPG'
    """
    template_key = message_type.value

    # Handle OHLC special cases
    if message_type == MessageType.OHLC:
        symbol = kwargs.get("symbol", "")
        if kwargs.get("indexName"):
            template_key = "INDEX_OHLC"
        elif symbol:
            # Check if derivative (you might need logic to determine this)
            template_key = "STOCK_OHLC"

    template = TOPIC_TEMPLATES.get(template_key)
    if not template:
        raise ValueError(f"Unknown message type: {message_type}")

    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required parameter: {e}")
