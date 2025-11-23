"""
AI/ML Engine for Trading Intelligence.

Features:
- Smart Risk Scoring: Calculate risk for each order
- Anomaly Detection: Detect unusual trading patterns
- Price Prediction: Simple ML-based price prediction
- Trading Insights: Portfolio analysis and recommendations
"""
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# RISK SCORING SYSTEM
# ============================================================================

class RiskScorer:
    """
    Calculate risk score (0-100) for trading orders.

    Factors considered:
    - Order size relative to typical volume
    - Price deviation from current market
    - Order type risk
    - Time of day
    - Market volatility estimate
    """

    # Risk weights
    WEIGHTS = {
        'size': 0.30,      # 30% - Order size impact
        'price': 0.25,     # 25% - Price deviation
        'type': 0.20,      # 20% - Order type risk
        'time': 0.15,      # 15% - Time of day
        'volatility': 0.10 # 10% - Market condition
    }

    # Order type risk levels (0-100)
    ORDER_TYPE_RISK = {
        'LO': 20,   # Limit order - Low risk
        'PLO': 25,  # Post limit - Low risk
        'MTL': 40,  # Market to limit - Medium risk
        'ATO': 50,  # At open - Medium-high risk
        'ATC': 50,  # At close - Medium-high risk
        'MP': 75,   # Market price - High risk
        'MOK': 80,  # Match or kill - High risk
        'MAK': 85,  # Make or kill - Very high risk
    }

    def __init__(self):
        # Historical data for volatility estimation
        self.price_history: Dict[str, List[float]] = defaultdict(list)
        self.volume_history: Dict[str, List[float]] = defaultdict(list)

    def calculate_risk_score(
        self,
        symbol: str,
        price: float,
        quantity: float,
        order_type: str,
        side: str,
        current_price: Optional[float] = None
    ) -> Dict[str, any]:
        """
        Calculate comprehensive risk score for an order.

        Returns:
            Dict with:
            - score: Overall risk score (0-100)
            - level: 'low', 'medium', 'high', 'very_high'
            - factors: Breakdown by factor
            - recommendation: 'approve', 'review', 'reject'
        """
        factors = {}

        # 1. Size risk (based on typical quantity)
        size_risk = self._calculate_size_risk(symbol, quantity)
        factors['size'] = {'score': size_risk, 'weight': self.WEIGHTS['size']}

        # 2. Price risk (deviation from market)
        price_risk = self._calculate_price_risk(symbol, price, current_price, side)
        factors['price'] = {'score': price_risk, 'weight': self.WEIGHTS['price']}

        # 3. Order type risk
        type_risk = self.ORDER_TYPE_RISK.get(order_type, 50)
        factors['type'] = {'score': type_risk, 'weight': self.WEIGHTS['type']}

        # 4. Time of day risk
        time_risk = self._calculate_time_risk()
        factors['time'] = {'score': time_risk, 'weight': self.WEIGHTS['time']}

        # 5. Volatility risk
        volatility_risk = self._calculate_volatility_risk(symbol)
        factors['volatility'] = {'score': volatility_risk, 'weight': self.WEIGHTS['volatility']}

        # Calculate weighted score
        total_score = sum(
            f['score'] * f['weight']
            for f in factors.values()
        )

        # Determine level and recommendation
        if total_score < 30:
            level = 'low'
            recommendation = 'approve'
        elif total_score < 50:
            level = 'medium'
            recommendation = 'approve'
        elif total_score < 70:
            level = 'high'
            recommendation = 'review'
        else:
            level = 'very_high'
            recommendation = 'reject'

        return {
            'score': round(total_score, 2),
            'level': level,
            'recommendation': recommendation,
            'factors': factors,
            'timestamp': datetime.now().isoformat()
        }

    def _calculate_size_risk(self, symbol: str, quantity: float) -> float:
        """Calculate risk based on order size."""
        # If no history, use conservative estimate
        if not self.volume_history[symbol]:
            # Assume typical order is 1000 shares
            typical_volume = 1000
        else:
            typical_volume = np.median(self.volume_history[symbol])

        # Risk increases exponentially with size
        ratio = quantity / max(typical_volume, 100)

        if ratio < 0.5:
            return 10  # Small order
        elif ratio < 1.0:
            return 20  # Normal order
        elif ratio < 2.0:
            return 40  # Large order
        elif ratio < 5.0:
            return 60  # Very large
        elif ratio < 10.0:
            return 80  # Extremely large
        else:
            return 95  # Massive order

    def _calculate_price_risk(
        self,
        symbol: str,
        price: float,
        current_price: Optional[float],
        side: str
    ) -> float:
        """Calculate risk based on price deviation."""
        if not current_price:
            # No market price available, use historical
            if not self.price_history[symbol]:
                return 30  # Unknown, moderate risk
            current_price = self.price_history[symbol][-1]

        # Calculate deviation percentage
        deviation = abs(price - current_price) / current_price * 100

        # For buy orders, high price is risky
        # For sell orders, low price is risky
        if side == 'NB':  # Buy
            if price > current_price * 1.05:  # > 5% higher
                risk = 70
            elif price > current_price * 1.02:  # > 2% higher
                risk = 40
            else:
                risk = 20
        else:  # Sell
            if price < current_price * 0.95:  # < 5% lower
                risk = 70
            elif price < current_price * 0.98:  # < 2% lower
                risk = 40
            else:
                risk = 20

        # Add deviation penalty
        risk += min(deviation * 2, 30)

        return min(risk, 100)

    def _calculate_time_risk(self) -> float:
        """Calculate risk based on time of day."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # Market hours: 9:00 - 15:00
        # High risk times:
        # - 9:00-9:15 (opening volatility)
        # - 11:30-13:00 (lunch, low liquidity)
        # - 14:45-15:00 (closing volatility)

        if hour == 9 and minute < 15:
            return 60  # Opening volatility
        elif hour == 14 and minute >= 45:
            return 60  # Closing volatility
        elif hour == 11 and minute >= 30:
            return 40  # Lunch time
        elif hour == 12:
            return 40  # Lunch time
        elif hour == 13 and minute < 30:
            return 40  # Lunch time
        elif 9 <= hour < 15:
            return 15  # Normal trading hours
        else:
            return 80  # Outside market hours

    def _calculate_volatility_risk(self, symbol: str) -> float:
        """Estimate volatility risk from price history."""
        if len(self.price_history[symbol]) < 10:
            return 30  # Unknown, moderate risk

        # Calculate simple volatility (std dev of returns)
        prices = np.array(self.price_history[symbol][-30:])  # Last 30 data points
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * 100  # As percentage

        # Map volatility to risk score
        if volatility < 1.0:
            return 15  # Low volatility
        elif volatility < 2.0:
            return 30  # Normal volatility
        elif volatility < 3.0:
            return 50  # High volatility
        elif volatility < 5.0:
            return 70  # Very high volatility
        else:
            return 90  # Extreme volatility

    def update_history(self, symbol: str, price: float, volume: float):
        """Update historical data for better risk assessment."""
        self.price_history[symbol].append(price)
        self.volume_history[symbol].append(volume)

        # Keep only last 100 data points
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol] = self.price_history[symbol][-100:]
        if len(self.volume_history[symbol]) > 100:
            self.volume_history[symbol] = self.volume_history[symbol][-100:]


# ============================================================================
# ANOMALY DETECTION SYSTEM
# ============================================================================

class AnomalyDetector:
    """
    Detect unusual trading patterns and potential errors.

    Detects:
    - Price anomalies (too high/low)
    - Volume anomalies (too large)
    - Frequency anomalies (too many orders)
    - Pattern anomalies (unusual behavior)
    """

    def __init__(self):
        self.order_history: List[Dict] = []

    def detect_anomalies(
        self,
        symbol: str,
        price: float,
        quantity: float,
        order_type: str,
        side: str
    ) -> Dict[str, any]:
        """
        Detect if order has anomalous characteristics.

        Returns:
            Dict with:
            - is_anomaly: Boolean
            - anomalies: List of detected anomalies
            - severity: 'low', 'medium', 'high'
            - should_block: Boolean
        """
        anomalies = []

        # 1. Price anomalies
        price_anomalies = self._detect_price_anomalies(symbol, price)
        anomalies.extend(price_anomalies)

        # 2. Volume anomalies
        volume_anomalies = self._detect_volume_anomalies(symbol, quantity)
        anomalies.extend(volume_anomalies)

        # 3. Frequency anomalies
        frequency_anomalies = self._detect_frequency_anomalies(symbol)
        anomalies.extend(frequency_anomalies)

        # 4. Pattern anomalies
        pattern_anomalies = self._detect_pattern_anomalies(symbol, side)
        anomalies.extend(pattern_anomalies)

        # Determine severity
        if not anomalies:
            severity = 'none'
            should_block = False
        elif len(anomalies) == 1:
            severity = 'low'
            should_block = False
        elif len(anomalies) == 2:
            severity = 'medium'
            should_block = False
        else:
            severity = 'high'
            should_block = True  # Block if 3+ anomalies detected

        # Log order for future analysis
        self._log_order(symbol, price, quantity, order_type, side)

        return {
            'is_anomaly': len(anomalies) > 0,
            'anomalies': anomalies,
            'severity': severity,
            'should_block': should_block,
            'count': len(anomalies)
        }

    def _detect_price_anomalies(self, symbol: str, price: float) -> List[str]:
        """Detect price-related anomalies."""
        anomalies = []

        # Extremely high price (> 10M VND)
        if price > 10_000_000:
            anomalies.append(f"Price extremely high: {price:,.0f} VND (> 10M VND)")

        # Suspiciously round numbers
        if price % 10000 == 0 and price > 100000:
            anomalies.append(f"Suspiciously round price: {price:,.0f} VND")

        # Historical comparison
        recent_orders = [o for o in self.order_history if o['symbol'] == symbol][-10:]
        if recent_orders:
            avg_price = np.mean([o['price'] for o in recent_orders])
            if price > avg_price * 2:
                anomalies.append(f"Price 2x higher than recent average ({avg_price:,.0f})")
            elif price < avg_price * 0.5:
                anomalies.append(f"Price 50% lower than recent average ({avg_price:,.0f})")

        return anomalies

    def _detect_volume_anomalies(self, symbol: str, quantity: float) -> List[str]:
        """Detect volume-related anomalies."""
        anomalies = []

        # Extremely large quantity
        if quantity > 100_000:
            anomalies.append(f"Quantity extremely large: {quantity:,.0f} shares (> 100k)")

        # Not multiple of 100 (should be caught by validation, but double-check)
        if quantity % 100 != 0:
            anomalies.append(f"Quantity not multiple of 100: {quantity}")

        # Historical comparison
        recent_orders = [o for o in self.order_history if o['symbol'] == symbol][-10:]
        if recent_orders:
            avg_qty = np.mean([o['quantity'] for o in recent_orders])
            if quantity > avg_qty * 10:
                anomalies.append(f"Quantity 10x larger than recent average ({avg_qty:,.0f})")

        return anomalies

    def _detect_frequency_anomalies(self, symbol: str) -> List[str]:
        """Detect frequency-related anomalies."""
        anomalies = []

        # Count orders in last minute
        one_min_ago = datetime.now() - timedelta(minutes=1)
        recent_orders = [
            o for o in self.order_history
            if o['symbol'] == symbol and o['timestamp'] > one_min_ago
        ]

        if len(recent_orders) > 5:
            anomalies.append(f"Too many orders in 1 minute: {len(recent_orders)} orders")

        # Count orders in last 5 minutes
        five_min_ago = datetime.now() - timedelta(minutes=5)
        recent_orders_5min = [
            o for o in self.order_history
            if o['symbol'] == symbol and o['timestamp'] > five_min_ago
        ]

        if len(recent_orders_5min) > 15:
            anomalies.append(f"Too many orders in 5 minutes: {len(recent_orders_5min)} orders")

        return anomalies

    def _detect_pattern_anomalies(self, symbol: str, side: str) -> List[str]:
        """Detect pattern-related anomalies."""
        anomalies = []

        # Check last 5 orders for same symbol
        recent_same_symbol = [o for o in self.order_history if o['symbol'] == symbol][-5:]

        if len(recent_same_symbol) >= 5:
            # All same side (all buy or all sell)
            if all(o['side'] == side for o in recent_same_symbol):
                anomalies.append(f"Last 5 orders all {side} for {symbol}")

        return anomalies

    def _log_order(
        self,
        symbol: str,
        price: float,
        quantity: float,
        order_type: str,
        side: str
    ):
        """Log order for historical analysis."""
        self.order_history.append({
            'symbol': symbol,
            'price': price,
            'quantity': quantity,
            'order_type': order_type,
            'side': side,
            'timestamp': datetime.now()
        })

        # Keep only last 1000 orders
        if len(self.order_history) > 1000:
            self.order_history = self.order_history[-1000:]


# ============================================================================
# SIMPLE PRICE PREDICTOR
# ============================================================================

class PricePredictor:
    """
    Simple price movement prediction using basic ML.

    Note: This is a simple implementation for demonstration.
    In production, you'd want more sophisticated models.
    """

    def __init__(self):
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)

    def predict_movement(
        self,
        symbol: str,
        horizon_minutes: int = 15
    ) -> Dict[str, any]:
        """
        Predict price movement direction.

        Args:
            symbol: Stock symbol
            horizon_minutes: Prediction horizon (5, 15, or 30 minutes)

        Returns:
            Dict with:
            - direction: 'up', 'down', 'neutral'
            - confidence: 0-100
            - predicted_change: Estimated % change
            - current_price: Latest price
        """
        if len(self.price_history[symbol]) < 10:
            return {
                'direction': 'neutral',
                'confidence': 0,
                'predicted_change': 0.0,
                'current_price': None,
                'message': 'Insufficient data for prediction'
            }

        # Get recent prices
        recent_data = self.price_history[symbol][-30:]
        prices = [p for _, p in recent_data]
        current_price = prices[-1]

        # Simple momentum-based prediction
        # Calculate short-term and long-term moving averages
        if len(prices) >= 10:
            short_ma = np.mean(prices[-5:])
            long_ma = np.mean(prices[-15:] if len(prices) >= 15 else prices)

            # Calculate trend
            momentum = (short_ma - long_ma) / long_ma * 100

            # Calculate recent volatility
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns) * 100

            # Determine direction and confidence
            if momentum > 0.5:
                direction = 'up'
                predicted_change = momentum
                confidence = min(70 + momentum * 10, 95)
            elif momentum < -0.5:
                direction = 'down'
                predicted_change = momentum
                confidence = min(70 + abs(momentum) * 10, 95)
            else:
                direction = 'neutral'
                predicted_change = 0.0
                confidence = 50

            # Reduce confidence if high volatility
            if volatility > 3.0:
                confidence *= 0.7

            return {
                'direction': direction,
                'confidence': round(confidence, 2),
                'predicted_change': round(predicted_change, 2),
                'current_price': current_price,
                'volatility': round(volatility, 2),
                'short_ma': round(short_ma, 2),
                'long_ma': round(long_ma, 2)
            }

        return {
            'direction': 'neutral',
            'confidence': 30,
            'predicted_change': 0.0,
            'current_price': current_price,
            'message': 'Limited data available'
        }

    def update_price(self, symbol: str, price: float):
        """Update price history."""
        self.price_history[symbol].append((datetime.now(), price))

        # Keep only last 100 data points
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol] = self.price_history[symbol][-100:]


# ============================================================================
# TRADING INSIGHTS GENERATOR
# ============================================================================

class InsightsGenerator:
    """
    Generate actionable trading insights from portfolio and order data.
    """

    def __init__(self):
        self.order_stats: Dict[str, List[Dict]] = defaultdict(list)

    def generate_insights(
        self,
        portfolio: List[Dict],
        recent_orders: List[Dict]
    ) -> List[Dict[str, str]]:
        """
        Generate trading insights.

        Returns:
            List of insights, each with:
            - type: 'warning', 'info', 'success'
            - category: 'risk', 'performance', 'opportunity'
            - message: Insight text
        """
        insights = []

        if portfolio:
            # Portfolio concentration analysis
            concentration_insights = self._analyze_concentration(portfolio)
            insights.extend(concentration_insights)

            # Performance analysis
            performance_insights = self._analyze_performance(portfolio)
            insights.extend(performance_insights)

        if recent_orders:
            # Trading pattern analysis
            pattern_insights = self._analyze_patterns(recent_orders)
            insights.extend(pattern_insights)

            # Win rate analysis
            winrate_insights = self._analyze_winrate(recent_orders)
            insights.extend(winrate_insights)

        return insights

    def _analyze_concentration(self, portfolio: List[Dict]) -> List[Dict]:
        """Analyze portfolio concentration risk."""
        insights = []

        total_value = sum(p.get('marketValue', 0) for p in portfolio)
        if total_value == 0:
            return insights

        # Calculate concentration per symbol
        concentrations = {}
        for position in portfolio:
            symbol = position.get('symbol')
            value = position.get('marketValue', 0)
            concentration = (value / total_value) * 100
            concentrations[symbol] = concentration

        # Warn about high concentration
        for symbol, concentration in concentrations.items():
            if concentration > 40:
                insights.append({
                    'type': 'warning',
                    'category': 'risk',
                    'message': f"High concentration in {symbol}: {concentration:.1f}% of portfolio. Consider diversifying."
                })
            elif concentration > 25:
                insights.append({
                    'type': 'info',
                    'category': 'risk',
                    'message': f"Moderate concentration in {symbol}: {concentration:.1f}% of portfolio."
                })

        # Diversification score
        num_positions = len(portfolio)
        if num_positions == 1:
            insights.append({
                'type': 'warning',
                'category': 'risk',
                'message': "Portfolio has only 1 position. Very high concentration risk."
            })
        elif num_positions <= 3:
            insights.append({
                'type': 'info',
                'category': 'risk',
                'message': f"Portfolio has {num_positions} positions. Consider adding more for diversification."
            })
        else:
            insights.append({
                'type': 'success',
                'category': 'risk',
                'message': f"Portfolio well-diversified with {num_positions} positions."
            })

        return insights

    def _analyze_performance(self, portfolio: List[Dict]) -> List[Dict]:
        """Analyze portfolio performance."""
        insights = []

        total_pl = sum(
            (p.get('realizedPL', 0) + p.get('unrealizedPL', 0))
            for p in portfolio
        )
        total_value = sum(p.get('marketValue', 0) for p in portfolio)

        if total_value > 0:
            total_pl_pct = (total_pl / total_value) * 100

            if total_pl_pct > 10:
                insights.append({
                    'type': 'success',
                    'category': 'performance',
                    'message': f"Strong portfolio performance: +{total_pl_pct:.2f}% ({total_pl:,.0f} VND)"
                })
            elif total_pl_pct > 5:
                insights.append({
                    'type': 'success',
                    'category': 'performance',
                    'message': f"Good portfolio performance: +{total_pl_pct:.2f}% ({total_pl:,.0f} VND)"
                })
            elif total_pl_pct < -10:
                insights.append({
                    'type': 'warning',
                    'category': 'performance',
                    'message': f"Portfolio significantly down: {total_pl_pct:.2f}% ({total_pl:,.0f} VND)"
                })
            elif total_pl_pct < -5:
                insights.append({
                    'type': 'info',
                    'category': 'performance',
                    'message': f"Portfolio moderately down: {total_pl_pct:.2f}% ({total_pl:,.0f} VND)"
                })

        # Individual position analysis
        for position in portfolio:
            symbol = position.get('symbol')
            pl = position.get('realizedPL', 0) + position.get('unrealizedPL', 0)
            value = position.get('marketValue', 0)

            if value > 0:
                pl_pct = (pl / value) * 100

                if pl_pct > 20:
                    insights.append({
                        'type': 'success',
                        'category': 'opportunity',
                        'message': f"{symbol}: Strong performer (+{pl_pct:.1f}%). Consider taking profit."
                    })
                elif pl_pct < -20:
                    insights.append({
                        'type': 'warning',
                        'category': 'risk',
                        'message': f"{symbol}: Significant loss ({pl_pct:.1f}%). Review position."
                    })

        return insights

    def _analyze_patterns(self, recent_orders: List[Dict]) -> List[Dict]:
        """Analyze trading patterns."""
        insights = []

        if len(recent_orders) < 5:
            return insights

        # Count by side
        buy_orders = sum(1 for o in recent_orders if o.get('side') == 'NB')
        sell_orders = sum(1 for o in recent_orders if o.get('side') == 'NS')

        if buy_orders > sell_orders * 2:
            insights.append({
                'type': 'info',
                'category': 'pattern',
                'message': f"Heavily buying: {buy_orders} buy vs {sell_orders} sell orders. Building positions."
            })
        elif sell_orders > buy_orders * 2:
            insights.append({
                'type': 'info',
                'category': 'pattern',
                'message': f"Heavily selling: {sell_orders} sell vs {buy_orders} buy orders. Reducing exposure."
            })

        return insights

    def _analyze_winrate(self, recent_orders: List[Dict]) -> List[Dict]:
        """Analyze win rate if we have enough data."""
        insights = []

        # This would require filled order data with P&L
        # For now, just placeholder
        completed_orders = [o for o in recent_orders if o.get('orderStatus') == 'filled']

        if len(completed_orders) >= 10:
            insights.append({
                'type': 'info',
                'category': 'performance',
                'message': f"Completed {len(completed_orders)} orders recently. Track P&L for win rate analysis."
            })

        return insights


# ============================================================================
# SINGLETON INSTANCES
# ============================================================================

# Global instances (initialized once per app)
_risk_scorer: Optional[RiskScorer] = None
_anomaly_detector: Optional[AnomalyDetector] = None
_price_predictor: Optional[PricePredictor] = None
_insights_generator: Optional[InsightsGenerator] = None


def get_risk_scorer() -> RiskScorer:
    """Get global RiskScorer instance."""
    global _risk_scorer
    if _risk_scorer is None:
        _risk_scorer = RiskScorer()
        logger.info("✅ RiskScorer initialized")
    return _risk_scorer


def get_anomaly_detector() -> AnomalyDetector:
    """Get global AnomalyDetector instance."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
        logger.info("✅ AnomalyDetector initialized")
    return _anomaly_detector


def get_price_predictor() -> PricePredictor:
    """Get global PricePredictor instance."""
    global _price_predictor
    if _price_predictor is None:
        _price_predictor = PricePredictor()
        logger.info("✅ PricePredictor initialized")
    return _price_predictor


def get_insights_generator() -> InsightsGenerator:
    """Get global InsightsGenerator instance."""
    global _insights_generator
    if _insights_generator is None:
        _insights_generator = InsightsGenerator()
        logger.info("✅ InsightsGenerator initialized")
    return _insights_generator
