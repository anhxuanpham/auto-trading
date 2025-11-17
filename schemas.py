"""
Pydantic models for all requests and responses.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# Enums
class OrderSide(str, Enum):
    """Order side: Buy or Sell."""
    BUY = "NB"  # New Buy
    SELL = "NS"  # New Sell


class OrderType(str, Enum):
    """Order type."""
    LIMIT = "LO"  # Limit Order
    MARKET = "MP"  # Market Price
    ATC = "ATC"  # At The Close
    ATO = "ATO"  # At The Open


class DealStatus(str, Enum):
    """Deal (position) status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


# Authentication Schemas
class LoginRequest(BaseModel):
    """DNSE login request."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """DNSE login response."""
    token: str


# Order Schemas
class PlaceOrderRequest(BaseModel):
    """Request to place a new order."""
    symbol: str = Field(..., description="Stock symbol (e.g., 'VNM', 'HPG')")
    side: OrderSide = Field(..., description="Order side: NB (buy) or NS (sell)")
    orderType: OrderType = Field(..., description="Order type: LO, MP, ATC, ATO")
    price: float = Field(..., description="Order price (required even for market orders)")
    quantity: int = Field(..., gt=0, description="Order quantity (must be positive)")
    loanPackageId: Optional[int] = Field(None, description="Loan package ID for margin trading")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "VNM",
                "side": "NB",
                "orderType": "LO",
                "price": 85.5,
                "quantity": 100,
                "loanPackageId": None
            }
        }


class PlaceOrderPayload(PlaceOrderRequest):
    """Internal payload with accountNo included."""
    accountNo: str


class OrderResponse(BaseModel):
    """Response after placing an order."""
    orderId: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None


class Order(BaseModel):
    """Order information from GET orders."""
    orderId: str
    accountNo: str
    symbol: str
    side: str
    orderType: str
    price: float
    quantity: int
    filledQuantity: int = 0
    status: str
    createdAt: Optional[str] = None


class OrdersResponse(BaseModel):
    """Response containing list of orders."""
    orders: list[Order]


# Deal (Portfolio) Schemas
class Deal(BaseModel):
    """Deal (position) information."""
    id: str
    symbol: str
    status: DealStatus
    side: str
    secure: bool = Field(..., description="True if margin position")
    costPrice: float = Field(..., description="Average cost price")
    marketPrice: float = Field(..., description="Current market price")
    realizedProfit: float = Field(..., description="Realized profit/loss")
    quantity: Optional[int] = Field(None, description="Position quantity")


class DealsResponse(BaseModel):
    """Response containing list of deals."""
    deals: list[Deal]


# Admin Schemas
class UpdateTokenRequest(BaseModel):
    """Request to update the trading token."""
    new_trading_token: str = Field(..., min_length=1, description="New trading token value")

    class Config:
        json_schema_extra = {
            "example": {
                "new_trading_token": "new_token_value_here"
            }
        }


class UpdateTokenResponse(BaseModel):
    """Response after updating token."""
    success: bool
    message: str


# Error Schema
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
