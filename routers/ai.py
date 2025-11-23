"""
AI-powered trading intelligence endpoints.
Provides risk scoring, anomaly detection, price prediction, and trading insights.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from ai_engine import (
    get_risk_scorer,
    get_anomaly_detector,
    get_price_predictor,
    get_insights_generator
)
from dnse_client import get_dnse_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Intelligence"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class OrderAnalysisRequest(BaseModel):
    """Request model for order analysis."""
    symbol: str = Field(..., description="Stock symbol (e.g., VNM, HPG)")
    price: float = Field(..., gt=0, description="Order price")
    quantity: float = Field(..., gt=0, description="Order quantity")
    side: str = Field(..., description="Order side: NB (buy) or NS (sell)")
    order_type: str = Field(..., description="Order type: LO, MP, ATC, ATO, etc.")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "VNM",
                "price": 85500,
                "quantity": 1000,
                "side": "NB",
                "order_type": "LO"
            }
        }


class RiskAnalysisResponse(BaseModel):
    """Response model for risk analysis."""
    risk_score: float = Field(..., description="Risk score (0-100)")
    risk_level: str = Field(..., description="Risk level: low, medium, high, extreme")
    recommendation: str = Field(..., description="Risk recommendation")
    factors: Dict[str, Any] = Field(..., description="Risk factors breakdown")
    anomaly_detection: Dict[str, Any] = Field(..., description="Anomaly detection results")
    timestamp: float = Field(..., description="Analysis timestamp")


class PricePredictionResponse(BaseModel):
    """Response model for price prediction."""
    symbol: str
    direction: str = Field(..., description="Predicted direction: bullish, bearish, neutral")
    confidence: float = Field(..., description="Confidence level (0-1)")
    predicted_change_pct: float = Field(..., description="Predicted price change percentage")
    current_price: Optional[float] = Field(None, description="Current market price")
    horizon_minutes: int = Field(..., description="Prediction time horizon")
    timestamp: float = Field(..., description="Prediction timestamp")


class TradingInsight(BaseModel):
    """Single trading insight."""
    type: str = Field(..., description="Insight type: recommendation, warning, observation")
    category: str = Field(..., description="Category: risk, opportunity, performance, diversification")
    message: str = Field(..., description="Insight message")
    priority: str = Field(..., description="Priority: high, medium, low")


class InsightsResponse(BaseModel):
    """Response model for trading insights."""
    insights: list[TradingInsight]
    portfolio_summary: Dict[str, Any]
    timestamp: float


# ============================================================================
# ORDER ANALYSIS ENDPOINT
# ============================================================================

@router.post("/analyze-order", response_model=RiskAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_order(order: OrderAnalysisRequest) -> RiskAnalysisResponse:
    """
    Analyze an order for risk and anomalies before placement.

    **Features:**
    - Multi-factor risk scoring (size, price, type, timing, volatility)
    - Anomaly detection (price, volume, frequency, patterns)
    - Actionable recommendations

    **Request Body:**
    - **symbol**: Stock symbol (e.g., "VNM", "HPG")
    - **price**: Order price in VND
    - **quantity**: Number of shares
    - **side**: "NB" (buy) or "NS" (sell)
    - **order_type**: "LO", "MP", "ATC", "ATO", etc.

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/ai/analyze-order" \\
         -H "Content-Type: application/json" \\
         -d '{
           "symbol": "VNM",
           "price": 85500,
           "quantity": 1000,
           "side": "NB",
           "order_type": "LO"
         }'
    ```

    **Returns:**
    - **risk_score**: 0-100 score (higher = riskier)
    - **risk_level**: low/medium/high/extreme
    - **recommendation**: Actionable advice
    - **factors**: Breakdown of risk components
    - **anomaly_detection**: Unusual pattern alerts
    """
    logger.info("=" * 80)
    logger.info(f"🤖 AI Endpoint: POST /ai/analyze-order")
    logger.info(f"Analyzing: {order.side} {order.symbol} | Qty: {order.quantity} | Price: {order.price}")

    try:
        # Get AI components
        risk_scorer = get_risk_scorer()
        anomaly_detector = get_anomaly_detector()

        # Get current market price for risk calculation
        # Note: In production, this should come from real-time market data
        current_price = order.price  # Simplified for now

        # Calculate risk score
        risk_analysis = risk_scorer.calculate_risk_score(
            symbol=order.symbol,
            price=order.price,
            quantity=order.quantity,
            order_type=order.order_type,
            side=order.side,
            current_price=current_price
        )

        # Detect anomalies
        anomaly_result = anomaly_detector.detect_anomalies(
            symbol=order.symbol,
            price=order.price,
            quantity=order.quantity,
            order_type=order.order_type,
            side=order.side
        )

        # Combine results
        response = RiskAnalysisResponse(
            risk_score=risk_analysis["score"],
            risk_level=risk_analysis["level"],
            recommendation=risk_analysis["recommendation"],
            factors=risk_analysis["factors"],
            anomaly_detection=anomaly_result,
            timestamp=risk_analysis["timestamp"]
        )

        logger.info(f"✅ AI Analysis: Risk={risk_analysis['level']} ({risk_analysis['score']:.1f}) | Anomalies={anomaly_result['count']}")
        logger.info("=" * 80)

        return response

    except Exception as e:
        logger.error(f"❌ AI Analysis Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze order: {str(e)}"
        )


# ============================================================================
# PRICE PREDICTION ENDPOINT
# ============================================================================

@router.get("/predict/{symbol}", response_model=PricePredictionResponse)
async def predict_price(
    symbol: str,
    horizon: int = Query(15, description="Prediction horizon in minutes", ge=5, le=240)
) -> PricePredictionResponse:
    """
    Predict price movement for a stock symbol.

    **Features:**
    - Momentum-based prediction
    - Moving average analysis
    - Confidence scoring

    **Path Parameters:**
    - **symbol**: Stock symbol (e.g., "VNM", "HPG")

    **Query Parameters:**
    - **horizon**: Prediction horizon in minutes (5-240, default: 15)

    **Example:**
    ```bash
    curl "http://localhost:8000/ai/predict/VNM?horizon=30"
    ```

    **Returns:**
    - **direction**: bullish/bearish/neutral
    - **confidence**: 0-1 confidence level
    - **predicted_change_pct**: Expected price change percentage
    - **current_price**: Current market price
    """
    logger.info(f"🤖 AI Endpoint: GET /ai/predict/{symbol} | Horizon: {horizon}min")

    try:
        predictor = get_price_predictor()

        # Get prediction
        prediction = predictor.predict_movement(
            symbol=symbol,
            horizon_minutes=horizon
        )

        response = PricePredictionResponse(
            symbol=symbol,
            direction=prediction["direction"],
            confidence=prediction["confidence"],
            predicted_change_pct=prediction["predicted_change_pct"],
            current_price=prediction.get("current_price"),
            horizon_minutes=horizon,
            timestamp=prediction["timestamp"]
        )

        logger.info(f"✅ AI Prediction: {prediction['direction']} | Confidence: {prediction['confidence']:.2%} | Change: {prediction['predicted_change_pct']:.2%}")

        return response

    except Exception as e:
        logger.error(f"❌ AI Prediction Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to predict price: {str(e)}"
        )


# ============================================================================
# TRADING INSIGHTS ENDPOINT
# ============================================================================

@router.get("/insights", response_model=InsightsResponse)
async def get_trading_insights(
    account_no: Optional[str] = None,
    limit: int = Query(10, description="Maximum number of insights", ge=1, le=50)
) -> InsightsResponse:
    """
    Generate actionable trading insights from portfolio and recent activity.

    **Features:**
    - Portfolio concentration analysis
    - Position performance evaluation
    - Diversification recommendations
    - Risk alerts

    **Query Parameters:**
    - **account_no**: (Optional) Account number. Defaults to DNSE_ACCOUNT_NO
    - **limit**: Maximum number of insights to return (1-50, default: 10)

    **Example:**
    ```bash
    curl "http://localhost:8000/ai/insights?limit=15"
    ```

    **Returns:**
    - **insights**: List of actionable insights with priorities
    - **portfolio_summary**: Key portfolio metrics
    """
    logger.info(f"🤖 AI Endpoint: GET /ai/insights | Account: {account_no or 'default'} | Limit: {limit}")

    try:
        client = get_dnse_client()
        insights_gen = get_insights_generator()

        # Get portfolio and recent orders
        portfolio = await client.get_deals(account_no)
        recent_orders = await client.get_orders(account_no)

        # Limit to recent orders (last 100)
        recent_orders = recent_orders[:100] if len(recent_orders) > 100 else recent_orders

        # Generate insights
        insights_data = insights_gen.generate_insights(
            portfolio=portfolio,
            recent_orders=recent_orders
        )

        # Limit insights
        limited_insights = insights_data[:limit]

        # Convert to response model
        insights = [
            TradingInsight(
                type=insight["type"],
                category=insight["category"],
                message=insight["message"],
                priority=insight.get("priority", "medium")
            )
            for insight in limited_insights
        ]

        # Calculate portfolio summary
        total_positions = len(portfolio)
        open_positions = sum(1 for p in portfolio if p.status == "OPEN")
        total_value = sum(p.marketPrice * p.tradeQuantity for p in portfolio if p.status == "OPEN")
        total_pnl = sum(p.unrealizedProfit for p in portfolio if p.status == "OPEN")

        response = InsightsResponse(
            insights=insights,
            portfolio_summary={
                "total_positions": total_positions,
                "open_positions": open_positions,
                "total_value": total_value,
                "total_unrealized_pnl": total_pnl,
                "recent_orders_analyzed": len(recent_orders)
            },
            timestamp=insights_data[0]["timestamp"] if insights_data else 0
        )

        logger.info(f"✅ AI Insights: Generated {len(insights)} insights | Portfolio: {open_positions} open positions")

        return response

    except Exception as e:
        logger.error(f"❌ AI Insights Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insights: {str(e)}"
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def ai_health() -> dict:
    """
    Health check for AI endpoints.

    Verifies:
    - All AI components are initialized
    - Models are loaded

    **Example:**
    ```bash
    curl "http://localhost:8000/ai/health"
    ```
    """
    try:
        risk_scorer = get_risk_scorer()
        anomaly_detector = get_anomaly_detector()
        price_predictor = get_price_predictor()
        insights_gen = get_insights_generator()

        return {
            "status": "healthy",
            "components": {
                "risk_scorer": risk_scorer is not None,
                "anomaly_detector": anomaly_detector is not None,
                "price_predictor": price_predictor is not None,
                "insights_generator": insights_gen is not None
            },
            "features": {
                "order_analysis": True,
                "price_prediction": True,
                "trading_insights": True,
                "risk_scoring": True,
                "anomaly_detection": True
            }
        }
    except Exception as e:
        logger.error(f"❌ AI Health Check Failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI components not healthy: {str(e)}"
        )
