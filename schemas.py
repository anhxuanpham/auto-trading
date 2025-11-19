"""
Pydantic models for all requests and responses.
Based on official DNSE Lightspeed API documentation.
"""
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


# Enums
class OrderSide(str, Enum):
    """Order side: Buy or Sell."""
    BUY = "NB"  # New Buy
    SELL = "NS"  # New Sell


class OrderType(str, Enum):
    """
    Order type according to DNSE API.
    """
    LIMIT = "LO"  # Lệnh giới hạn (Limit Order)
    MARKET = "MP"  # Lệnh thị trường (Market Price)
    MARKET_TO_LIMIT = "MTL"  # Lệnh thị trường chuyển giới hạn
    ATC = "ATC"  # Lệnh khớp phiên định kỳ đóng cửa (At The Close)
    ATO = "ATO"  # Lệnh khớp phiên định kỳ mở cửa (At The Open)
    MOK = "MOK"  # Match or Kill
    MAK = "MAK"  # Make or Kill
    PLO = "PLO"  # Lệnh khớp lệnh sau giờ (Post-market Limit Order)


class OrderStatus(str, Enum):
    """
    Order status according to DNSE API.
    """
    PENDING = "pending"  # Chờ gửi
    PENDING_NEW = "pendingNew"  # Chờ gửi
    NEW = "new"  # Chờ khớp
    PARTIALLY_FILLED = "partiallyFilled"  # Khớp một phần
    FILLED = "filled"  # Khớp toàn bộ
    REJECTED = "rejected"  # Bị từ chối
    EXPIRED = "expired"  # Bị hết hạn trong phiên
    DONE_FOR_DAY = "doneForDay"  # Lệnh hết hiệu lực khi hết phiên


class DealStatus(str, Enum):
    """Deal (position) status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


# Error Codes from DNSE API
class DNSEErrorCode(str, Enum):
    """DNSE API error codes."""
    # Expired errors
    MP_NO_MATCHING_ORDER = "0"  # Lệnh MP không có lệnh đối ứng

    # Rejected errors
    QMAX_EXCEED = "QMAX_EXCEED"  # Vượt quá KL có thể mua/bán
    INVALID_QUANTITY_LOT = "INVALID_QUANTITY_LOT"  # KL đặt không hợp lệ
    PRICE_TOO_LOW = "PRICE_MUST_GREATER_THAN_OR_EQUAL_TO_FLOOR_PRICE"  # Giá đặt thấp hơn sàn
    PRICE_TOO_HIGH = "PRICE_MUST_LESS_THAN_OR_EQUAL_TO_CEILING_PRICE"  # Giá đặt cao hơn trần
    INVALID_PRICE_LOT = "INVALID_PRICE_LOT"  # Giá đặt không hợp lệ
    NOT_IN_MARGIN_BASKET = "SYMBOL_IS_NOT_IN_MARGIN_BASKET"  # Mã không nằm trong rổ margin


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
    symbol: str = Field(..., description="Stock symbol (e.g., 'VNM', 'HPG')", pattern=r"^[A-Z]{3}$")
    side: OrderSide = Field(..., description="Order side: NB (buy) or NS (sell)")
    orderType: OrderType = Field(..., description="Order type: LO, MP, MTL, ATC, ATO, MOK, MAK, PLO")
    price: float = Field(..., gt=0, lt=1_000_000_000, description="Order price in VND (must be > 0 and < 1 billion)")
    quantity: float = Field(..., gt=0, description="Order quantity (must be positive and multiple of 100)")
    loanPackageId: Optional[int] = Field(None, description="Loan package ID for margin trading")

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate stock symbol format."""
        v = v.upper().strip()
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Symbol must be exactly 3 uppercase letters (e.g., VNM, HPG)')
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        """Validate quantity is positive and multiple of 100."""
        if v <= 0:
            raise ValueError('Quantity must be positive')
        if v % 100 != 0:
            raise ValueError('Quantity must be a multiple of 100')
        if v > 10_000_000:
            raise ValueError('Quantity must not exceed 10 million shares')
        return v

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: float) -> float:
        """Validate price is within reasonable bounds."""
        if v <= 0:
            raise ValueError('Price must be positive')
        if v > 1_000_000_000:
            raise ValueError('Price must not exceed 1 billion VND')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "VNM",
                "side": "NB",
                "orderType": "LO",
                "price": 85500,
                "quantity": 100,
                "loanPackageId": None
            }
        }


class PlaceOrderPayload(PlaceOrderRequest):
    """Internal payload with accountNo included."""
    accountNo: str


class OrderDetail(BaseModel):
    """
    Complete order information according to DNSE API.
    Used for all order responses (place, get, cancel).
    """
    id: int = Field(..., description="Số hiệu lệnh")
    side: str = Field(..., description="NB (mua) hoặc NS (bán)")
    accountNo: str = Field(..., description="Số tiểu khoản")
    investorId: str = Field(..., description="Mã khách hàng")
    symbol: str = Field(..., description="Mã chứng khoán")
    price: float = Field(..., description="Giá đặt")
    quantity: float = Field(..., description="Khối lượng đặt")
    orderType: str = Field(..., description="Loại lệnh: LO/MP/MTL/ATC/ATO/PLO")
    orderStatus: str = Field(..., description="Trạng thái lệnh")

    # Execution details
    fillQuantity: Optional[float] = Field(None, description="Khối lượng đã khớp")
    lastQuantity: Optional[float] = Field(None, description="Khối lượng lần khớp gần nhất")
    lastPrice: Optional[float] = Field(None, description="Giá khớp lần gần nhất")
    averagePrice: Optional[float] = Field(None, description="Giá khớp trung bình")
    leaveQuantity: Optional[float] = Field(None, description="Khối lượng chưa khớp")
    canceledQuantity: Optional[float] = Field(None, description="Khối lượng đã hủy")

    # Dates
    transDate: Optional[str] = Field(None, description="Ngày giao dịch (ISO 8601)")
    createdDate: Optional[str] = Field(None, description="Thời điểm đặt lệnh (ISO 8601)")
    modifiedDate: Optional[str] = Field(None, description="Thời điểm thay đổi cuối (ISO 8601)")

    # Fees and rates
    taxRate: Optional[float] = Field(None, description="Tỷ lệ thuế")
    feeRate: Optional[float] = Field(None, description="Tỷ lệ phí")
    priceSecure: Optional[float] = Field(None, description="Giá cọc")

    # Additional info
    custody: Optional[str] = Field(None, description="Số lưu ký")
    channel: Optional[str] = Field(None, description="Kênh đặt lệnh")
    loanPackageId: Optional[int] = Field(None, description="Id gói vay")
    initialRate: Optional[float] = Field(None, description="Tỷ lệ ký quỹ")

    # Error information
    error: Optional[str] = Field(None, description="Mã lỗi (nếu có)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 12345678,
                "side": "NB",
                "accountNo": "0001234567",
                "investorId": "INV123456",
                "symbol": "VNM",
                "price": 85500,
                "quantity": 100,
                "orderType": "LO",
                "orderStatus": "new",
                "fillQuantity": 0,
                "lastQuantity": 0,
                "lastPrice": 0,
                "averagePrice": 0,
                "leaveQuantity": 100,
                "canceledQuantity": 0,
                "transDate": "2022-07-15",
                "createdDate": "2022-07-15T10:00:00.111+07:00",
                "modifiedDate": "2022-07-15T10:00:00.111+07:00",
                "taxRate": 0.001,
                "feeRate": 0.0015,
                "priceSecure": 8550,
                "custody": "123456",
                "channel": "API",
                "loanPackageId": None,
                "initialRate": None,
                "error": None
            }
        }


class OrdersResponse(BaseModel):
    """Response containing list of orders."""
    orders: list[OrderDetail]


class OrderResponse(BaseModel):
    """
    Simple response wrapper for operations that return a single order.
    Can be used as a type alias for OrderDetail.
    """
    success: bool = True
    data: Optional[OrderDetail] = None
    message: Optional[str] = None


# Deal (Portfolio) Schemas
class Deal(BaseModel):
    """
    Complete deal (position) information according to DNSE API.
    Represents a trading position (open or closed).
    """
    # Basic info
    id: int = Field(..., description="Id deal")
    symbol: str = Field(..., description="Mã chứng khoán")
    accountNo: str = Field(..., description="Số tiểu khoản")
    orderIds: Optional[list[str]] = Field(None, description="Danh sách Order Id thuộc deal")
    status: str = Field(..., description="OPEN (đang mở) hoặc CLOSED (đã đóng)")
    loanPackageId: Optional[str] = Field(None, description="Mã gói vay")
    side: str = Field(..., description="NB (mua) hoặc NS (bán)")

    # Secure/Margin
    secure: float = Field(..., description="Cọc hiện tại của deal")

    # Quantities
    accumulateQuantity: Optional[float] = Field(None, description="Khối lượng mở tích lũy")
    tradeQuantity: Optional[float] = Field(None, description="Khối lượng có thể giao dịch")
    closedQuantity: Optional[float] = Field(None, description="Khối lượng đã đóng")
    t0ReceivingQuantity: Optional[float] = Field(None, description="KL nhận T+0")
    t1ReceivingQuantity: Optional[float] = Field(None, description="KL nhận T+1")
    t2ReceivingQuantity: Optional[float] = Field(None, description="KL nhận T+2")
    dividendReceivingQuantity: Optional[float] = Field(None, description="KL nhận cổ tức")
    dividendQuantity: Optional[float] = Field(None, description="KL cổ tức")

    # Prices
    costPrice: float = Field(..., description="Giá vốn hiện tại")
    averageCostPrice: Optional[float] = Field(None, description="Giá mở cửa trung bình")
    marketPrice: float = Field(..., description="Giá thị trường")
    breakEvenPrice: Optional[float] = Field(None, description="Giá hòa vốn")
    averageClosePrice: Optional[float] = Field(None, description="Giá đóng trung bình")

    # Profit/Loss
    realizedProfit: float = Field(..., description="Lãi lỗ đã chốt (chưa trừ phí thuế)")
    unrealizedProfit: Optional[float] = Field(None, description="Lãi lỗ tạm tính (theo giá thị trường)")

    # Fees and Taxes
    realizedTotalTaxAndFee: Optional[float] = Field(None, description="Phí thuế phần đã chốt")
    collectedBuyingFee: Optional[float] = Field(None, description="Tổng phí mua")
    collectedBuyingTax: Optional[float] = Field(None, description="Tổng thuế mua")
    collectedSellingFee: Optional[float] = Field(None, description="Tổng phí bán")
    collectedSellingTax: Optional[float] = Field(None, description="Tổng thuế bán")
    collectedStockTransferFee: Optional[float] = Field(None, description="Phí chuyển khoản CK")
    collectedInterestFee: Optional[float] = Field(None, description="Tổng lãi vay (margin)")
    estimateRemainTaxAndFee: Optional[float] = Field(None, description="Phí thuế đóng tạm tính")
    unrealizedOpenTaxAndFee: Optional[float] = Field(None, description="Phí thuế mua phần đang mở")

    # Debt/Margin
    currentDebt: Optional[float] = Field(None, description="Nợ của phần đang mở")
    currentInterest: Optional[float] = Field(None, description="Lãi của phần đang mở")
    currentDebtExcludeToCollect: Optional[float] = Field(None, description="Nợ chưa trả")
    currentInterestExcludeToCollect: Optional[float] = Field(None, description="Lãi chưa trả")
    accumulateSecure: Optional[float] = Field(None, description="Cọc tích lũy")
    accumulateDebt: Optional[float] = Field(None, description="Nợ tích lũy")

    # Cash
    cashReceiving: Optional[float] = Field(None, description="Tiền nhận")
    rightReceivingCash: Optional[float] = Field(None, description="Tiền quyền nhận")
    t0ReceivingCash: Optional[float] = Field(None, description="Tiền nhận T+0")
    t1RecevingCash: Optional[float] = Field(None, description="Tiền nhận T+1")
    t2RecevingCash: Optional[float] = Field(None, description="Tiền nhận T+2")

    # Dates
    createdDate: Optional[str] = Field(None, description="Ngày tạo (ISO 8601)")
    modifiedDate: Optional[str] = Field(None, description="Ngày sửa (ISO 8601)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123456,
                "symbol": "VNM",
                "accountNo": "0001234567",
                "orderIds": ["12345678", "12345679"],
                "status": "OPEN",
                "loanPackageId": None,
                "side": "NB",
                "secure": 8550000,
                "accumulateQuantity": 100,
                "tradeQuantity": 100,
                "closedQuantity": 0,
                "t0ReceivingQuantity": 0,
                "t1ReceivingQuantity": 0,
                "t2ReceivingQuantity": 100,
                "costPrice": 85500,
                "averageCostPrice": 85500,
                "marketPrice": 87000,
                "breakEvenPrice": 85628,
                "realizedProfit": 0,
                "unrealizedProfit": 150000,
                "realizedTotalTaxAndFee": 0,
                "collectedBuyingFee": 128250,
                "collectedBuyingTax": 0,
                "collectedSellingFee": 0,
                "collectedSellingTax": 0,
                "collectedStockTransferFee": 0,
                "collectedInterestFee": 0,
                "estimateRemainTaxAndFee": 261150,
                "unrealizedOpenTaxAndFee": 128250,
                "currentDebt": 0,
                "currentInterest": 0,
                "currentDebtExcludeToCollect": 0,
                "currentInterestExcludeToCollect": 0,
                "accumulateSecure": 8550000,
                "accumulateDebt": 0,
                "averageClosePrice": 0,
                "cashReceiving": 0,
                "rightReceivingCash": 0,
                "t0ReceivingCash": 0,
                "t1RecevingCash": 0,
                "t2RecevingCash": 0,
                "createdDate": "2022-07-15T10:00:00.111+07:00",
                "modifiedDate": "2022-07-15T10:00:00.111+07:00"
            }
        }


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


# Conditional Order Schemas
class ConditionalTargetOrder(BaseModel):
    """Target order for conditional order."""
    quantity: float = Field(..., description="Khối lượng đặt")
    side: OrderSide = Field(..., description="NB (mua) hoặc NS (bán)")
    price: float = Field(..., description="Giá đặt (VND)")
    loanPackageId: Optional[int] = Field(None, description="Mã gói vay")
    orderType: OrderType = Field(..., description="Loại lệnh: LO, MP, MTL")


class ConditionalProps(BaseModel):
    """Properties for conditional order."""
    stopPrice: float = Field(..., description="Giá trigger")
    marketId: str = Field(..., description="UNDERLYING (cơ sở) hoặc DERIVATIVES (phái sinh)")
    trailingAmount: Optional[float] = Field(0, description="Trailing amount")
    trailingPercent: Optional[float] = Field(0, description="Trailing percent")


class TimeInForce(BaseModel):
    """Time in force for conditional order."""
    expireTime: str = Field(..., description="Thời gian hết hạn (ISO 8601)")
    kind: str = Field(..., description="Loại: GTD (Good Till Date)")


class ConditionalOrderRequest(BaseModel):
    """Request to place a conditional order."""
    condition: str = Field(..., description="Điều kiện: 'price >= stopPrice' hoặc 'price <= stopPrice'")
    targetOrder: ConditionalTargetOrder = Field(..., description="Lệnh mục tiêu")
    symbol: str = Field(..., description="Mã chứng khoán")
    props: ConditionalProps = Field(..., description="Thuộc tính lệnh điều kiện")
    accountNo: str = Field(..., description="Mã tiểu khoản")
    category: str = Field("STOP", description="Loại: STOP")
    timeInForce: TimeInForce = Field(..., description="Thời gian hiệu lực")

    class Config:
        json_schema_extra = {
            "example": {
                "condition": "price <= 26650",
                "targetOrder": {
                    "quantity": 100,
                    "side": "NB",
                    "price": 26600,
                    "loanPackageId": None,
                    "orderType": "LO"
                },
                "symbol": "HPG",
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
            }
        }


class ConditionalOrderMetadata(BaseModel):
    """Metadata for conditional order."""
    errorMessage: Optional[str] = Field("", description="Thông báo lỗi")
    externalOrderId: Optional[int] = Field(None, description="ID lệnh bên ngoài")
    status: Optional[str] = Field(None, description="Trạng thái: OK, FAILED")


class ConditionalOrderStatus(str, Enum):
    """Status of conditional order."""
    NEW = "NEW"
    ACTIVATED = "ACTIVATED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    CANCELLED_BY_RIGHTS_EVENT = "CANCELLED_BY_RIGHTS_EVENT"


class ConditionalOrderDetail(BaseModel):
    """Complete conditional order information."""
    id: str = Field(..., description="ID của lệnh điều kiện")
    accountNo: str = Field(..., description="Số tiểu khoản")
    investorId: str = Field(..., description="Mã khách hàng")
    symbol: str = Field(..., description="Mã chứng khoán")
    category: str = Field(..., description="Loại: STOP")
    condition: str = Field(..., description="Điều kiện đặt")
    status: str = Field(..., description="Trạng thái lệnh")
    targetOrder: ConditionalTargetOrder = Field(..., description="Lệnh mục tiêu")
    props: ConditionalProps = Field(..., description="Thuộc tính")
    timeInForce: TimeInForce = Field(..., description="Thời gian hiệu lực")
    metadata: Optional[ConditionalOrderMetadata] = Field(None, description="Metadata")
    productGroupId: Optional[int] = Field(None, description="Product group ID")
    createdAt: Optional[str] = Field(None, description="Thời gian tạo (ISO 8601)")
    createdBy: Optional[str] = Field(None, description="Người tạo")
    updatedAt: Optional[str] = Field(None, description="Thời gian cập nhật (ISO 8601)")
    updatedBy: Optional[str] = Field(None, description="Người cập nhật")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "csc7iqa45sbpqutqm81g",
                "accountNo": "0001000006",
                "investorId": "0001000006",
                "symbol": "HPG",
                "category": "STOP",
                "condition": "price <= 26650",
                "status": "ACTIVATED",
                "targetOrder": {
                    "quantity": 100,
                    "side": "NB",
                    "price": 26600,
                    "loanPackageId": 1531,
                    "orderType": "LO"
                },
                "props": {
                    "stopPrice": 26650,
                    "marketId": "UNDERLYING",
                    "trailingAmount": 0,
                    "trailingPercent": 0
                },
                "timeInForce": {
                    "expireTime": "2024-10-23T07:30:00Z",
                    "kind": "GTD"
                },
                "metadata": {
                    "errorMessage": "",
                    "externalOrderId": 112,
                    "status": "OK"
                },
                "productGroupId": 0,
                "createdAt": "2024-10-23T04:19:53.94801Z",
                "createdBy": "064C000006",
                "updatedAt": "2024-10-23T04:19:59.299943Z",
                "updatedBy": "064C000006"
            }
        }


class ConditionalOrdersResponse(BaseModel):
    """Paginated response for conditional orders."""
    content: list[ConditionalOrderDetail] = Field(..., description="Danh sách lệnh điều kiện")
    page: int = Field(..., description="Trang hiện tại")
    size: int = Field(..., description="Số lượng items trong trang")
    numberOfElements: int = Field(..., description="Số lượng items trong trang này")
    totalElements: int = Field(..., description="Tổng số lượng items")
    totalPages: int = Field(..., description="Tổng số trang")


class ConditionalOrderCreateResponse(BaseModel):
    """Response after creating conditional order."""
    id: str = Field(..., description="ID của lệnh điều kiện")


# Error Schema
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
