# AI Features Documentation

This document describes the AI/ML-powered features integrated into the DNSE Trading Backend.

## Overview

The AI engine provides intelligent trading assistance through:

- **Risk Scoring**: Multi-factor risk assessment for orders
- **Anomaly Detection**: Identify unusual trading patterns
- **Price Prediction**: Momentum-based price movement forecasting
- **Trading Insights**: Actionable recommendations from portfolio analysis

## Architecture

### AI Components

All AI components are implemented in `ai_engine.py`:

1. **RiskScorer** - Calculates risk scores (0-100) using weighted factors
2. **AnomalyDetector** - Detects unusual patterns in orders
3. **PricePredictor** - Predicts price movements using technical indicators
4. **InsightsGenerator** - Generates actionable trading insights

### API Endpoints

All AI endpoints are available under the `/ai` prefix:

- `POST /ai/analyze-order` - Analyze order risk before placement
- `GET /ai/predict/{symbol}` - Get price predictions
- `GET /ai/insights` - Get portfolio insights
- `GET /ai/health` - AI system health check

---

## 1. Risk Scoring System

### Overview

The Risk Scorer evaluates orders using a multi-factor weighted model:

- **Size Risk (30%)**: Order size relative to average trading volume
- **Price Risk (25%)**: Price deviation from market price
- **Order Type Risk (20%)**: Risk associated with order type
- **Time Risk (15%)**: Trading time (market hours vs. pre/post-market)
- **Volatility Risk (10%)**: Based on historical price movements

### Risk Levels

| Score Range | Level | Recommendation |
|------------|-------|----------------|
| 0-25 | Low | Safe to proceed |
| 26-50 | Medium | Proceed with caution |
| 51-75 | High | Consider reducing size or adjusting price |
| 76-100 | Extreme | High risk - review carefully |

### API Endpoint

**POST /ai/analyze-order**

Request:
```json
{
  "symbol": "VNM",
  "price": 85500,
  "quantity": 1000,
  "side": "NB",
  "order_type": "LO"
}
```

Response:
```json
{
  "risk_score": 42.5,
  "risk_level": "medium",
  "recommendation": "Moderate risk - proceed with caution",
  "factors": {
    "size_score": 35.0,
    "size_weight": 0.30,
    "price_score": 40.0,
    "price_weight": 0.25,
    "type_score": 30.0,
    "type_weight": 0.20,
    "time_score": 60.0,
    "time_weight": 0.15,
    "volatility_score": 75.0,
    "volatility_weight": 0.10
  },
  "anomaly_detection": {
    "is_anomaly": false,
    "anomalies": [],
    "severity": "none",
    "should_block": false,
    "count": 0
  },
  "timestamp": 1700000000.0
}
```

### Usage Example

```bash
curl -X POST "http://localhost:8000/ai/analyze-order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "VNM",
       "price": 85500,
       "quantity": 1000,
       "side": "NB",
       "order_type": "LO"
     }'
```

---

## 2. Anomaly Detection

### Overview

Detects unusual patterns in trading orders across multiple dimensions:

#### Detection Types

1. **Price Anomalies**
   - Extreme deviations from recent prices (>5%)
   - Severity: Critical if >10%, High if >7%, Medium if >5%

2. **Volume Anomalies**
   - Unusually large orders (>3x average)
   - Severity: Critical if >10x, High if >5x, Medium if >3x

3. **Frequency Anomalies**
   - Rapid order placement (>10 orders in 60 seconds)
   - Severity: High if >10, Medium if >5

4. **Pattern Anomalies**
   - Repeated identical orders
   - Potential fat-finger errors (orders >100x typical size)

### Severity Levels

- **none**: No anomalies detected
- **low**: Minor irregularities
- **medium**: Noteworthy patterns
- **high**: Significant anomalies
- **critical**: Extreme deviations (may block order)

### Response Structure

```json
{
  "is_anomaly": true,
  "anomalies": [
    {
      "type": "price_deviation",
      "severity": "medium",
      "description": "Price 5.2% above recent average",
      "value": 5.2,
      "threshold": 5.0
    }
  ],
  "severity": "medium",
  "should_block": false,
  "count": 1
}
```

---

## 3. Price Prediction

### Overview

Predicts short-term price movements using momentum and moving average analysis.

### Methodology

1. **Moving Averages**: 5-period and 20-period MAs
2. **Momentum**: Recent price velocity and acceleration
3. **Trend Analysis**: Direction and strength

### Prediction Horizons

- **Short-term**: 5-15 minutes
- **Medium-term**: 30-60 minutes
- **Long-term**: 120-240 minutes

### API Endpoint

**GET /ai/predict/{symbol}**

Query Parameters:
- `horizon` (optional): Prediction horizon in minutes (5-240, default: 15)

Request:
```bash
curl "http://localhost:8000/ai/predict/VNM?horizon=30"
```

Response:
```json
{
  "symbol": "VNM",
  "direction": "bullish",
  "confidence": 0.72,
  "predicted_change_pct": 1.5,
  "current_price": 85500,
  "horizon_minutes": 30,
  "timestamp": 1700000000.0
}
```

### Direction Values

- **bullish**: Expected price increase (confidence-weighted)
- **bearish**: Expected price decrease (confidence-weighted)
- **neutral**: No clear direction or low confidence (<40%)

### Confidence Levels

- **0.0-0.4**: Low confidence - neutral/uncertain
- **0.4-0.7**: Medium confidence - moderate signal
- **0.7-1.0**: High confidence - strong signal

---

## 4. Trading Insights

### Overview

Generates actionable insights from portfolio analysis and recent trading activity.

### Insight Categories

1. **Risk Management**
   - Portfolio concentration warnings
   - Position size recommendations
   - Stop-loss suggestions

2. **Opportunities**
   - Underperforming positions
   - Rebalancing recommendations
   - Profit-taking suggestions

3. **Performance**
   - Win rate analysis
   - Average profit/loss metrics
   - Trading pattern observations

4. **Diversification**
   - Sector concentration
   - Single-stock exposure
   - Correlation warnings

### API Endpoint

**GET /ai/insights**

Query Parameters:
- `account_no` (optional): Account number
- `limit` (optional): Max insights to return (1-50, default: 10)

Request:
```bash
curl "http://localhost:8000/ai/insights?limit=15"
```

Response:
```json
{
  "insights": [
    {
      "type": "warning",
      "category": "risk",
      "message": "Portfolio heavily concentrated in VNM (45.2% of total value)",
      "priority": "high"
    },
    {
      "type": "recommendation",
      "category": "opportunity",
      "message": "Consider taking profit on HPG (+12.5% unrealized gain)",
      "priority": "medium"
    }
  ],
  "portfolio_summary": {
    "total_positions": 15,
    "open_positions": 12,
    "total_value": 1250000000,
    "total_unrealized_pnl": 45000000,
    "recent_orders_analyzed": 50
  },
  "timestamp": 1700000000.0
}
```

### Insight Types

- **recommendation**: Actionable trading suggestions
- **warning**: Risk alerts requiring attention
- **observation**: Informational insights

### Priority Levels

- **high**: Immediate attention recommended
- **medium**: Important but not urgent
- **low**: Informational only

---

## Integration Examples

### Pre-Order Risk Check

Before placing an order, check risk and anomalies:

```python
import httpx

async def place_safe_order(symbol, price, quantity, side, order_type):
    # 1. Analyze order first
    analysis = await httpx.post("http://localhost:8000/ai/analyze-order", json={
        "symbol": symbol,
        "price": price,
        "quantity": quantity,
        "side": side,
        "order_type": order_type
    })

    result = analysis.json()

    # 2. Check risk level
    if result["risk_level"] == "extreme":
        print(f"⚠️ Extreme risk detected: {result['recommendation']}")
        return None

    # 3. Check for blocking anomalies
    if result["anomaly_detection"]["should_block"]:
        print(f"🚫 Order blocked due to anomalies")
        return None

    # 4. Proceed with order if safe
    order = await httpx.post("http://localhost:8000/trading/orders", json={
        "symbol": symbol,
        "price": price,
        "quantity": quantity,
        "side": side,
        "orderType": order_type
    })

    return order.json()
```

### Price-Based Trading

Use predictions to time entries:

```python
async def should_buy_now(symbol):
    # Get price prediction
    prediction = await httpx.get(f"http://localhost:8000/ai/predict/{symbol}")
    result = prediction.json()

    # Buy only on bullish prediction with high confidence
    if result["direction"] == "bullish" and result["confidence"] > 0.7:
        print(f"✅ Strong buy signal for {symbol}")
        print(f"   Predicted change: +{result['predicted_change_pct']:.2f}%")
        return True

    return False
```

### Portfolio Monitoring

Regular insight checks:

```python
async def check_portfolio_health():
    insights = await httpx.get("http://localhost:8000/ai/insights?limit=20")
    result = insights.json()

    # Filter high-priority warnings
    warnings = [
        i for i in result["insights"]
        if i["type"] == "warning" and i["priority"] == "high"
    ]

    if warnings:
        print("⚠️ High-Priority Alerts:")
        for warning in warnings:
            print(f"   • {warning['message']}")

    return result
```

---

## Technical Details

### Dependencies

Required Python packages (see `requirements.txt`):

```
numpy>=1.24.0
scikit-learn>=1.3.0
pandas>=2.0.0
```

### Performance

- **Risk Analysis**: < 50ms per order
- **Anomaly Detection**: < 30ms per order
- **Price Prediction**: < 100ms per symbol
- **Insight Generation**: < 500ms for 100 positions

### Scalability

All AI components use singleton patterns with thread-safe initialization:

```python
from ai_engine import get_risk_scorer, get_anomaly_detector

# Singleton instances - no overhead for multiple calls
scorer = get_risk_scorer()
detector = get_anomaly_detector()
```

### Data Storage

Currently, the AI engine maintains in-memory historical data:

- **Price History**: Last 100 prices per symbol
- **Volume History**: Last 50 volumes per symbol
- **Order History**: Last 100 orders per symbol

For production, consider integrating with a time-series database (InfluxDB, TimescaleDB).

---

## Configuration

### Risk Score Weights

Modify weights in `ai_engine.py`:

```python
class RiskScorer:
    WEIGHTS = {
        'size': 0.30,      # Order size impact
        'price': 0.25,     # Price deviation impact
        'type': 0.20,      # Order type risk
        'time': 0.15,      # Trading time risk
        'volatility': 0.10 # Volatility impact
    }
```

### Anomaly Thresholds

Adjust detection sensitivity:

```python
class AnomalyDetector:
    # Price deviation thresholds (%)
    PRICE_DEVIATION_THRESHOLD = 5.0  # Medium
    PRICE_DEVIATION_HIGH = 7.0       # High
    PRICE_DEVIATION_CRITICAL = 10.0  # Critical

    # Volume multipliers
    VOLUME_ANOMALY_THRESHOLD = 3.0   # 3x average
    VOLUME_ANOMALY_HIGH = 5.0        # 5x average
    VOLUME_ANOMALY_CRITICAL = 10.0   # 10x average
```

---

## Health Monitoring

Check AI system status:

```bash
curl "http://localhost:8000/ai/health"
```

Response:
```json
{
  "status": "healthy",
  "components": {
    "risk_scorer": true,
    "anomaly_detector": true,
    "price_predictor": true,
    "insights_generator": true
  },
  "features": {
    "order_analysis": true,
    "price_prediction": true,
    "trading_insights": true,
    "risk_scoring": true,
    "anomaly_detection": true
  }
}
```

---

## Future Enhancements

### Planned Features

1. **Machine Learning Models**
   - LSTM networks for price prediction
   - Random Forest for risk classification
   - Gradient Boosting for anomaly detection

2. **Advanced Analytics**
   - Sentiment analysis from news/social media
   - Order book imbalance analysis
   - Correlation-based portfolio optimization

3. **Real-time Alerts**
   - WebSocket push notifications for high-risk situations
   - Email/SMS alerts for critical anomalies
   - Slack/Discord integration

4. **Backtesting**
   - Historical strategy simulation
   - Risk metric validation
   - Performance attribution

5. **Auto-Trading**
   - Signal-based automated execution
   - Risk-aware position sizing
   - Dynamic stop-loss/take-profit

### Contributing

To add new AI features:

1. Implement the component class in `ai_engine.py`
2. Add getter function with singleton pattern
3. Create API endpoints in `routers/ai.py`
4. Add tests and documentation
5. Update this document with usage examples

---

## Troubleshooting

### Common Issues

**Issue**: "AI components not healthy"
- **Cause**: Import errors or initialization failures
- **Solution**: Check dependencies with `pip install -r requirements.txt`

**Issue**: Slow prediction response
- **Cause**: Large historical data accumulation
- **Solution**: Implement data rotation/cleanup in production

**Issue**: Inaccurate predictions
- **Cause**: Insufficient historical data
- **Solution**: Allow system to collect data over time (min 50 data points)

**Issue**: Too many anomaly alerts
- **Cause**: Thresholds too sensitive
- **Solution**: Adjust thresholds in `ai_engine.py` AnomalyDetector class

---

## Support

For issues or questions:

1. Check the API documentation at `/docs`
2. Review logs in `dnse_backend.log`
3. Enable DEBUG logging for detailed AI operation logs
4. Submit issues on GitHub

---

## Disclaimer

**Important**: AI predictions and risk scores are for informational purposes only. They do not constitute financial advice. Always perform your own analysis and risk assessment before trading.

The AI models use simplified heuristics and technical indicators. They are not trained on large datasets and should be used as supporting tools, not primary decision-makers.

**Past performance does not indicate future results.**
