# Frontend Integration Guide - DNSE Trading Platform

**Backend API Base URL**: `http://localhost:8000`

Tài liệu này hướng dẫn Frontend team tích hợp với DNSE Trading Backend API.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication & Configuration](#authentication--configuration)
3. [API Endpoints](#api-endpoints)
4. [WebSocket Integration (Real-time Data)](#websocket-integration)
5. [AI Features Integration](#ai-features-integration)
6. [Code Examples](#code-examples)
7. [Error Handling](#error-handling)
8. [Rate Limits](#rate-limits)
9. [Best Practices](#best-practices)

---

## Overview

### Tech Stack Requirements

```json
{
  "axios": "^1.6.0",
  "socket.io-client": "^4.6.0" // hoặc native WebSocket
}
```

### Base Configuration

```typescript
// config/api.ts
export const API_CONFIG = {
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  }
}
```

---

## Authentication & Configuration

### 1. Admin Endpoints (Token Management)

Backend sử dụng JWT authentication, token được auto-refresh khi hết hạn.

#### Update Trading Token

```typescript
// POST /admin/update-token
interface UpdateTokenRequest {
  newToken: string;
  adminSecret: string;
}

interface UpdateTokenResponse {
  message: string;
  token_preview: string;
}

// Example
const updateToken = async (newToken: string, adminSecret: string) => {
  const response = await axios.post<UpdateTokenResponse>(
    `${API_CONFIG.baseURL}/admin/update-token`,
    { newToken, adminSecret }
  );
  return response.data;
}
```

#### Health Check

```typescript
// GET /health
interface HealthResponse {
  status: string;
  account_no: string;
  api_base_url: string;
}

const checkHealth = async () => {
  const response = await axios.get<HealthResponse>(`${API_CONFIG.baseURL}/health`);
  return response.data;
}
```

---

## API Endpoints

### 2. Trading Endpoints

#### 2.1 Place Order (Đặt lệnh)

```typescript
// POST /trading/orders
interface PlaceOrderRequest {
  symbol: string;        // Mã CK: "VNM", "HPG", etc. (3 ký tự)
  side: "NB" | "NS";    // NB = Mua, NS = Bán
  orderType: "LO" | "MP" | "ATC" | "ATO" | "MTL" | "MOK" | "MAK" | "PLO";
  price: number;         // Giá đặt (VND)
  quantity: number;      // Khối lượng (phải chia hết cho 100)
  loanPackageId?: number; // Optional: Cho margin trading
}

interface OrderDetail {
  id: number;
  symbol: string;
  side: string;
  orderType: string;
  price: number;
  quantity: number;
  filledQuantity: number;
  remainingQuantity: number;
  orderStatus: string;  // "new", "filled", "partiallyFilled", "cancelled"
  createdAt: string;
  // ... more fields
}

// Example
const placeOrder = async (order: PlaceOrderRequest) => {
  const response = await axios.post<OrderDetail>(
    `${API_CONFIG.baseURL}/trading/orders`,
    order
  );
  return response.data;
}

// Usage
await placeOrder({
  symbol: "VNM",
  side: "NB",
  orderType: "LO",
  price: 85500,
  quantity: 100
});
```

**Rate Limit**: 10 orders/minute per IP

#### 2.2 Get Orders (Lấy danh sách lệnh)

```typescript
// GET /trading/orders
const getOrders = async () => {
  const response = await axios.get<OrderDetail[]>(`${API_CONFIG.baseURL}/trading/orders`);
  return response.data;
}
```

#### 2.3 Get Order by ID

```typescript
// GET /trading/orders/{orderId}
const getOrderById = async (orderId: number) => {
  const response = await axios.get<OrderDetail>(
    `${API_CONFIG.baseURL}/trading/orders/${orderId}`
  );
  return response.data;
}
```

#### 2.4 Cancel Order (Hủy lệnh)

```typescript
// DELETE /trading/orders/{orderId}
const cancelOrder = async (orderId: number) => {
  const response = await axios.delete<OrderDetail>(
    `${API_CONFIG.baseURL}/trading/orders/${orderId}`
  );
  return response.data;
}
```

**Rate Limit**: 20 cancellations/minute per IP

#### 2.5 Get Portfolio (Xem danh mục đầu tư)

```typescript
// GET /trading/portfolio
interface Deal {
  id: number;
  symbol: string;
  status: "OPEN" | "CLOSED";
  side: "NB" | "NS";
  costPrice: number;          // Giá vốn trung bình
  marketPrice: number;        // Giá thị trường hiện tại
  realizedProfit: number;     // Lãi/lỗ đã chốt
  unrealizedProfit: number;   // Lãi/lỗ chưa chốt
  breakEvenPrice: number;     // Giá hòa vốn (bao gồm phí)
  accumulateQuantity: number; // Tổng KL đã mua
  tradeQuantity: number;      // KL khả dụng để bán
  secure: number;             // Margin/ký quỹ
}

const getPortfolio = async () => {
  const response = await axios.get<Deal[]>(`${API_CONFIG.baseURL}/trading/portfolio`);
  return response.data;
}
```

#### 2.6 Conditional Orders (Lệnh điều kiện)

```typescript
// POST /trading/conditional-orders
interface ConditionalOrderRequest {
  condition: string;      // "price >= 26650" hoặc "price <= 26650"
  symbol: string;
  targetOrder: {
    quantity: number;
    side: "NB" | "NS";
    price: number;
    orderType: "LO" | "MP" | "MTL";
    loanPackageId?: number;
  };
  props: {
    stopPrice: number;
    marketId: "UNDERLYING" | "DERIVATIVES";
  };
  timeInForce: {
    expireTime: string;  // ISO 8601: "2024-10-23T07:30:00.000Z"
    kind: "GTD";
  };
  accountNo: string;
  category: "STOP";
}

interface ConditionalOrderResponse {
  orderId: string;
}

const placeConditionalOrder = async (order: ConditionalOrderRequest) => {
  const response = await axios.post<ConditionalOrderResponse>(
    `${API_CONFIG.baseURL}/trading/conditional-orders`,
    order
  );
  return response.data;
}
```

**Rate Limit**: 5 conditional orders/minute per IP

```typescript
// GET /trading/conditional-orders
interface GetConditionalOrdersParams {
  daily?: boolean;           // Chỉ lấy lệnh hôm nay
  from_date?: string;        // yyyy-MM-dd
  to_date?: string;          // yyyy-MM-dd
  page?: number;             // default: 1
  size?: number;             // default: 10000, max: 10000
  status?: string[];         // ["NEW", "ACTIVATED", "REJECTED", etc.]
  symbol?: string;
  market_id?: "UNDERLYING" | "DERIVATIVES";
}

const getConditionalOrders = async (params: GetConditionalOrdersParams) => {
  const response = await axios.get(`${API_CONFIG.baseURL}/trading/conditional-orders`, {
    params
  });
  return response.data;
}
```

---

### 3. Market Data Endpoints

#### 3.1 Subscribe to Symbols (Đăng ký nhận dữ liệu)

```typescript
// POST /market-data/subscribe
interface SubscribeRequest {
  symbols: string[];  // ["VNM", "HPG", "VCB"]
}

interface SubscribeResponse {
  message: string;
  symbols: string[];
  count: number;
}

const subscribeSymbols = async (symbols: string[]) => {
  const response = await axios.post<SubscribeResponse>(
    `${API_CONFIG.baseURL}/market-data/subscribe`,
    { symbols }
  );
  return response.data;
}
```

#### 3.2 Get Subscribed Symbols

```typescript
// GET /market-data/subscriptions
interface SubscriptionsResponse {
  symbols: string[];
  count: number;
}

const getSubscriptions = async () => {
  const response = await axios.get<SubscriptionsResponse>(
    `${API_CONFIG.baseURL}/market-data/subscriptions`
  );
  return response.data;
}
```

---

## WebSocket Integration

### Real-time Market Data Stream

Backend cung cấp WebSocket endpoint để nhận dữ liệu thị trường real-time.

#### Connection Setup

```typescript
// services/websocket.ts
class MarketDataWebSocket {
  private ws: WebSocket | null = null;
  private subscribers: Map<string, Set<Function>> = new Map();

  connect() {
    this.ws = new WebSocket('ws://localhost:8000/market-data/ws');

    this.ws.onopen = () => {
      console.log('✅ WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('🔌 WebSocket disconnected');
      // Auto-reconnect sau 5 giây
      setTimeout(() => this.connect(), 5000);
    };
  }

  private handleMessage(message: MarketDataMessage) {
    const { type, data } = message;

    // Notify subscribers
    const handlers = this.subscribers.get(type);
    if (handlers) {
      handlers.forEach(handler => handler(data));
    }
  }

  subscribe(messageType: string, handler: Function) {
    if (!this.subscribers.has(messageType)) {
      this.subscribers.set(messageType, new Set());
    }
    this.subscribers.get(messageType)!.add(handler);
  }

  unsubscribe(messageType: string, handler: Function) {
    const handlers = this.subscribers.get(messageType);
    if (handlers) {
      handlers.delete(handler);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const marketDataWS = new MarketDataWebSocket();
```

#### Message Types & Data Structures

```typescript
interface MarketDataMessage {
  type: string;         // "OD" | "MI" | "MT" | "PD" | "TS" | "TM"
  data: any;
  timestamp: number;
}

// Order Book (OD)
interface OrderBookData {
  symbol: string;
  bid: Array<[number, number]>;  // [price, volume]
  ask: Array<[number, number]>;
  _received_at: number;
}

// Market Info (MI)
interface MarketInfoData {
  symbol: string;
  ceiling: number;      // Giá trần
  floor: number;        // Giá sàn
  reference: number;    // Giá tham chiếu
  lastPrice: number;
  lastVolume: number;
  change: number;
  changePct: number;
  totalVolume: number;
  totalValue: number;
  _received_at: number;
}

// Match Data (MT)
interface MatchData {
  symbol: string;
  price: number;
  volume: number;
  side: "B" | "S";
  time: string;
  _received_at: number;
}
```

#### React Integration Example

```typescript
// hooks/useMarketData.ts
import { useEffect, useState } from 'react';
import { marketDataWS } from '@/services/websocket';

export const useMarketData = (symbol: string) => {
  const [marketInfo, setMarketInfo] = useState<MarketInfoData | null>(null);
  const [orderBook, setOrderBook] = useState<OrderBookData | null>(null);

  useEffect(() => {
    // Subscribe to market info
    const handleMarketInfo = (data: MarketInfoData) => {
      if (data.symbol === symbol) {
        setMarketInfo(data);
      }
    };

    // Subscribe to order book
    const handleOrderBook = (data: OrderBookData) => {
      if (data.symbol === symbol) {
        setOrderBook(data);
      }
    };

    marketDataWS.subscribe('MI', handleMarketInfo);
    marketDataWS.subscribe('OD', handleOrderBook);

    return () => {
      marketDataWS.unsubscribe('MI', handleMarketInfo);
      marketDataWS.unsubscribe('OD', handleOrderBook);
    };
  }, [symbol]);

  return { marketInfo, orderBook };
};
```

#### Component Usage

```tsx
// components/StockWidget.tsx
import { useMarketData } from '@/hooks/useMarketData';

export const StockWidget = ({ symbol }: { symbol: string }) => {
  const { marketInfo, orderBook } = useMarketData(symbol);

  if (!marketInfo) return <div>Loading...</div>;

  return (
    <div className="stock-widget">
      <h3>{symbol}</h3>
      <div className="price">
        <span className={marketInfo.change > 0 ? 'text-green' : 'text-red'}>
          {marketInfo.lastPrice.toLocaleString()} VND
        </span>
        <span>{marketInfo.changePct.toFixed(2)}%</span>
      </div>

      {/* Order Book */}
      <div className="order-book">
        <div className="asks">
          {orderBook?.ask.map(([price, vol], i) => (
            <div key={i}>
              <span className="text-red">{price.toLocaleString()}</span>
              <span>{vol.toLocaleString()}</span>
            </div>
          ))}
        </div>
        <div className="bids">
          {orderBook?.bid.map(([price, vol], i) => (
            <div key={i}>
              <span className="text-green">{price.toLocaleString()}</span>
              <span>{vol.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
```

---

## AI Features Integration

Backend cung cấp 4 AI features chính:

### 1. Order Risk Analysis (Phân tích rủi ro lệnh)

**Use Case**: Kiểm tra rủi ro TRƯỚC KHI đặt lệnh

```typescript
// POST /ai/analyze-order
interface AIOrderAnalysisRequest {
  symbol: string;
  price: number;
  quantity: number;
  side: "NB" | "NS";
  order_type: string;
}

interface AIRiskAnalysisResponse {
  risk_score: number;           // 0-100
  risk_level: "low" | "medium" | "high" | "extreme";
  recommendation: string;
  factors: {
    size_score: number;
    size_weight: number;
    price_score: number;
    price_weight: number;
    type_score: number;
    type_weight: number;
    time_score: number;
    time_weight: number;
    volatility_score: number;
    volatility_weight: number;
  };
  anomaly_detection: {
    is_anomaly: boolean;
    anomalies: Array<{
      type: string;
      severity: string;
      description: string;
    }>;
    severity: "none" | "low" | "medium" | "high" | "critical";
    should_block: boolean;
  };
  timestamp: number;
}

const analyzeOrder = async (order: AIOrderAnalysisRequest) => {
  const response = await axios.post<AIRiskAnalysisResponse>(
    `${API_CONFIG.baseURL}/ai/analyze-order`,
    order
  );
  return response.data;
}
```

#### UI Integration Example

```tsx
// components/OrderForm.tsx
const OrderForm = () => {
  const [orderData, setOrderData] = useState({
    symbol: 'VNM',
    price: 85500,
    quantity: 100,
    side: 'NB' as const,
    order_type: 'LO'
  });
  const [riskAnalysis, setRiskAnalysis] = useState<AIRiskAnalysisResponse | null>(null);

  const handleAnalyze = async () => {
    const analysis = await analyzeOrder(orderData);
    setRiskAnalysis(analysis);
  };

  const handleSubmit = async () => {
    // Kiểm tra risk trước
    if (!riskAnalysis) {
      alert('Vui lòng phân tích rủi ro trước!');
      return;
    }

    if (riskAnalysis.risk_level === 'extreme') {
      const confirm = window.confirm(
        `⚠️ RỦI RO CỰC CAO!\n${riskAnalysis.recommendation}\n\nBạn có chắc muốn tiếp tục?`
      );
      if (!confirm) return;
    }

    if (riskAnalysis.anomaly_detection.should_block) {
      alert('🚫 Lệnh bị chặn do phát hiện bất thường!');
      return;
    }

    // Đặt lệnh
    await placeOrder(orderData);
  };

  return (
    <div>
      {/* Form fields... */}

      <button onClick={handleAnalyze}>Phân tích rủi ro</button>

      {riskAnalysis && (
        <div className={`risk-card risk-${riskAnalysis.risk_level}`}>
          <h4>Điểm rủi ro: {riskAnalysis.risk_score.toFixed(1)}/100</h4>
          <p className="risk-level">{riskAnalysis.risk_level.toUpperCase()}</p>
          <p>{riskAnalysis.recommendation}</p>

          {riskAnalysis.anomaly_detection.is_anomaly && (
            <div className="anomalies">
              <h5>⚠️ Phát hiện bất thường:</h5>
              {riskAnalysis.anomaly_detection.anomalies.map((a, i) => (
                <div key={i} className={`anomaly-${a.severity}`}>
                  {a.description}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <button onClick={handleSubmit}>Đặt lệnh</button>
    </div>
  );
};
```

### 2. Price Prediction (Dự đoán giá)

```typescript
// GET /ai/predict/{symbol}?horizon=30
interface AIPricePredictionResponse {
  symbol: string;
  direction: "bullish" | "bearish" | "neutral";
  confidence: number;              // 0-1
  predicted_change_pct: number;    // % thay đổi dự đoán
  current_price: number | null;
  horizon_minutes: number;
  timestamp: number;
}

const predictPrice = async (symbol: string, horizonMinutes: number = 15) => {
  const response = await axios.get<AIPricePredictionResponse>(
    `${API_CONFIG.baseURL}/ai/predict/${symbol}`,
    { params: { horizon: horizonMinutes } }
  );
  return response.data;
}
```

#### UI Integration

```tsx
// components/PricePredictionWidget.tsx
const PricePredictionWidget = ({ symbol }: { symbol: string }) => {
  const [prediction, setPrediction] = useState<AIPricePredictionResponse | null>(null);

  useEffect(() => {
    const fetchPrediction = async () => {
      const pred = await predictPrice(symbol, 30);
      setPrediction(pred);
    };

    fetchPrediction();
    // Refresh mỗi 5 phút
    const interval = setInterval(fetchPrediction, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [symbol]);

  if (!prediction) return <div>Loading prediction...</div>;

  const getDirectionIcon = () => {
    if (prediction.direction === 'bullish') return '📈';
    if (prediction.direction === 'bearish') return '📉';
    return '➡️';
  };

  const getConfidenceColor = () => {
    if (prediction.confidence > 0.7) return 'text-green-600';
    if (prediction.confidence > 0.4) return 'text-yellow-600';
    return 'text-gray-600';
  };

  return (
    <div className="prediction-widget">
      <h4>Dự đoán 30 phút {getDirectionIcon()}</h4>
      <div className="direction">{prediction.direction.toUpperCase()}</div>
      <div className={getConfidenceColor()}>
        Độ tin cậy: {(prediction.confidence * 100).toFixed(0)}%
      </div>
      <div>
        Dự đoán: {prediction.predicted_change_pct > 0 ? '+' : ''}
        {prediction.predicted_change_pct.toFixed(2)}%
      </div>
    </div>
  );
};
```

### 3. Trading Insights (Gợi ý giao dịch)

```typescript
// GET /ai/insights?limit=15
interface AITradingInsight {
  type: "recommendation" | "warning" | "observation";
  category: "risk" | "opportunity" | "performance" | "diversification";
  message: string;
  priority: "high" | "medium" | "low";
}

interface AIInsightsResponse {
  insights: AITradingInsight[];
  portfolio_summary: {
    total_positions: number;
    open_positions: number;
    total_value: number;
    total_unrealized_pnl: number;
    recent_orders_analyzed: number;
  };
  timestamp: number;
}

const getTradingInsights = async (limit: number = 10) => {
  const response = await axios.get<AIInsightsResponse>(
    `${API_CONFIG.baseURL}/ai/insights`,
    { params: { limit } }
  );
  return response.data;
}
```

#### Dashboard Integration

```tsx
// components/InsightsDashboard.tsx
const InsightsDashboard = () => {
  const [insights, setInsights] = useState<AIInsightsResponse | null>(null);

  useEffect(() => {
    const fetchInsights = async () => {
      const data = await getTradingInsights(15);
      setInsights(data);
    };

    fetchInsights();
    // Refresh mỗi 10 phút
    const interval = setInterval(fetchInsights, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  if (!insights) return <div>Loading insights...</div>;

  const getInsightIcon = (type: string) => {
    if (type === 'warning') return '⚠️';
    if (type === 'recommendation') return '💡';
    return 'ℹ️';
  };

  const getPriorityClass = (priority: string) => {
    if (priority === 'high') return 'bg-red-100 border-red-500';
    if (priority === 'medium') return 'bg-yellow-100 border-yellow-500';
    return 'bg-gray-100 border-gray-500';
  };

  return (
    <div className="insights-dashboard">
      <h2>AI Trading Insights</h2>

      {/* Portfolio Summary */}
      <div className="summary-cards">
        <div className="card">
          <h4>Vị thế mở</h4>
          <p>{insights.portfolio_summary.open_positions}</p>
        </div>
        <div className="card">
          <h4>Tổng giá trị</h4>
          <p>{insights.portfolio_summary.total_value.toLocaleString()} VND</p>
        </div>
        <div className="card">
          <h4>Lãi/lỗ chưa chốt</h4>
          <p className={insights.portfolio_summary.total_unrealized_pnl > 0 ? 'text-green' : 'text-red'}>
            {insights.portfolio_summary.total_unrealized_pnl.toLocaleString()} VND
          </p>
        </div>
      </div>

      {/* Insights List */}
      <div className="insights-list">
        {insights.insights
          .sort((a, b) => {
            const priority = { high: 3, medium: 2, low: 1 };
            return priority[b.priority as keyof typeof priority] - priority[a.priority as keyof typeof priority];
          })
          .map((insight, i) => (
            <div key={i} className={`insight-card ${getPriorityClass(insight.priority)}`}>
              <div className="insight-header">
                <span>{getInsightIcon(insight.type)}</span>
                <span className="category">{insight.category}</span>
                <span className="priority">{insight.priority}</span>
              </div>
              <p>{insight.message}</p>
            </div>
          ))}
      </div>
    </div>
  );
};
```

---

## Code Examples

### Complete Trading Flow

```typescript
// services/tradingService.ts
export class TradingService {
  private api = axios.create({
    baseURL: API_CONFIG.baseURL,
    timeout: API_CONFIG.timeout,
  });

  /**
   * Place an order with AI risk check
   */
  async placeOrderSafe(orderData: PlaceOrderRequest): Promise<OrderDetail> {
    // Step 1: Analyze risk
    const riskAnalysis = await this.api.post<AIRiskAnalysisResponse>(
      '/ai/analyze-order',
      {
        symbol: orderData.symbol,
        price: orderData.price,
        quantity: orderData.quantity,
        side: orderData.side,
        order_type: orderData.orderType
      }
    );

    // Step 2: Check if should block
    if (riskAnalysis.data.anomaly_detection.should_block) {
      throw new Error('Order blocked due to anomalies');
    }

    // Step 3: Warn on high risk
    if (riskAnalysis.data.risk_level === 'extreme') {
      console.warn(`⚠️ Extreme risk: ${riskAnalysis.data.recommendation}`);
    }

    // Step 4: Place order
    const response = await this.api.post<OrderDetail>('/trading/orders', orderData);
    return response.data;
  }

  /**
   * Get portfolio with insights
   */
  async getPortfolioWithInsights() {
    const [portfolio, insights] = await Promise.all([
      this.api.get<Deal[]>('/trading/portfolio'),
      this.api.get<AIInsightsResponse>('/ai/insights', { params: { limit: 20 } })
    ]);

    return {
      portfolio: portfolio.data,
      insights: insights.data
    };
  }

  /**
   * Cancel order
   */
  async cancelOrder(orderId: number): Promise<OrderDetail> {
    const response = await this.api.delete<OrderDetail>(`/trading/orders/${orderId}`);
    return response.data;
  }
}

export const tradingService = new TradingService();
```

### React Context for Global State

```typescript
// context/TradingContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';

interface TradingContextType {
  orders: OrderDetail[];
  portfolio: Deal[];
  insights: AIInsightsResponse | null;
  refreshOrders: () => Promise<void>;
  refreshPortfolio: () => Promise<void>;
}

const TradingContext = createContext<TradingContextType | undefined>(undefined);

export const TradingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [orders, setOrders] = useState<OrderDetail[]>([]);
  const [portfolio, setPortfolio] = useState<Deal[]>([]);
  const [insights, setInsights] = useState<AIInsightsResponse | null>(null);

  const refreshOrders = async () => {
    const response = await axios.get<OrderDetail[]>(`${API_CONFIG.baseURL}/trading/orders`);
    setOrders(response.data);
  };

  const refreshPortfolio = async () => {
    const response = await axios.get<Deal[]>(`${API_CONFIG.baseURL}/trading/portfolio`);
    setPortfolio(response.data);
  };

  const refreshInsights = async () => {
    const response = await axios.get<AIInsightsResponse>(
      `${API_CONFIG.baseURL}/ai/insights`,
      { params: { limit: 15 } }
    );
    setInsights(response.data);
  };

  useEffect(() => {
    // Initial load
    refreshOrders();
    refreshPortfolio();
    refreshInsights();

    // Auto refresh every 30 seconds
    const interval = setInterval(() => {
      refreshOrders();
      refreshPortfolio();
    }, 30000);

    // Refresh insights every 5 minutes
    const insightsInterval = setInterval(refreshInsights, 5 * 60 * 1000);

    return () => {
      clearInterval(interval);
      clearInterval(insightsInterval);
    };
  }, []);

  return (
    <TradingContext.Provider value={{
      orders,
      portfolio,
      insights,
      refreshOrders,
      refreshPortfolio
    }}>
      {children}
    </TradingContext.Provider>
  );
};

export const useTrading = () => {
  const context = useContext(TradingContext);
  if (!context) {
    throw new Error('useTrading must be used within TradingProvider');
  }
  return context;
};
```

---

## Error Handling

### Error Response Format

```typescript
interface ErrorResponse {
  error: string;
  status_code?: number;
  timestamp?: number;
}

// Global error handler
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const errorData: ErrorResponse = error.response.data;

      // Handle specific error codes
      switch (error.response.status) {
        case 400:
          toast.error(`Lỗi dữ liệu: ${errorData.error}`);
          break;
        case 401:
          toast.error('Không có quyền truy cập');
          // Redirect to login or refresh token
          break;
        case 429:
          toast.error('Quá nhiều yêu cầu. Vui lòng thử lại sau.');
          break;
        case 500:
          toast.error('Lỗi server. Vui lòng thử lại sau.');
          break;
        default:
          toast.error(errorData.error || 'Đã có lỗi xảy ra');
      }
    } else if (error.request) {
      toast.error('Không thể kết nối đến server');
    } else {
      toast.error('Đã có lỗi xảy ra');
    }

    return Promise.reject(error);
  }
);
```

---

## Rate Limits

Backend có rate limiting để tránh abuse:

| Endpoint | Limit | Scope |
|----------|-------|-------|
| `POST /trading/orders` | 10/minute | Per IP |
| `DELETE /trading/orders/{id}` | 20/minute | Per IP |
| `POST /trading/conditional-orders` | 5/minute | Per IP |

**Khi bị rate limit**, server trả về HTTP 429. Frontend nên:

```typescript
const handleRateLimit = (retryAfter: number = 60) => {
  toast.warning(`Vui lòng chờ ${retryAfter} giây trước khi thử lại`);

  // Disable button với countdown
  setIsDisabled(true);
  setCountdown(retryAfter);

  const interval = setInterval(() => {
    setCountdown(prev => {
      if (prev <= 1) {
        clearInterval(interval);
        setIsDisabled(false);
        return 0;
      }
      return prev - 1;
    });
  }, 1000);
};
```

---

## Best Practices

### 1. Always Check Risk Before Placing Orders

```typescript
// ❌ BAD
const placeOrder = async (order) => {
  await axios.post('/trading/orders', order);
}

// ✅ GOOD
const placeOrderSafe = async (order) => {
  // Analyze first
  const risk = await analyzeOrder(order);

  if (risk.anomaly_detection.should_block) {
    throw new Error('Order blocked');
  }

  if (risk.risk_level === 'extreme') {
    const confirmed = await confirmHighRisk(risk.recommendation);
    if (!confirmed) return;
  }

  await axios.post('/trading/orders', order);
}
```

### 2. Use WebSocket for Real-time Data

```typescript
// ❌ BAD - Polling every second
setInterval(() => {
  fetch('/market-data/...');
}, 1000);

// ✅ GOOD - WebSocket
marketDataWS.connect();
marketDataWS.subscribe('MI', handleMarketInfo);
```

### 3. Batch API Calls

```typescript
// ❌ BAD - Multiple sequential calls
const orders = await getOrders();
const portfolio = await getPortfolio();
const insights = await getInsights();

// ✅ GOOD - Parallel calls
const [orders, portfolio, insights] = await Promise.all([
  getOrders(),
  getPortfolio(),
  getInsights()
]);
```

### 4. Cache AI Predictions

```typescript
// Cache predictions for 5 minutes
const predictionCache = new Map<string, { data: any, expiry: number }>();

const getPredictionCached = async (symbol: string) => {
  const cached = predictionCache.get(symbol);

  if (cached && cached.expiry > Date.now()) {
    return cached.data;
  }

  const prediction = await predictPrice(symbol);
  predictionCache.set(symbol, {
    data: prediction,
    expiry: Date.now() + 5 * 60 * 1000
  });

  return prediction;
};
```

### 5. Handle Connection Loss

```typescript
// WebSocket auto-reconnect
class RobustWebSocket {
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        setTimeout(() => {
          this.reconnectAttempts++;
          this.connect();
        }, delay);
      }
    };

    this.ws.onopen = () => {
      this.reconnectAttempts = 0; // Reset on successful connection
    };
  }
}
```

---

## API Documentation

Full interactive API documentation có sẵn tại:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## Support & Contact

Nếu có vấn đề:

1. Check API docs tại `/docs`
2. Xem logs trong browser console
3. Test endpoints với curl hoặc Postman
4. Liên hệ Backend team

---

## Monitoring & Metrics

Backend expose Prometheus metrics tại `/metrics` để monitoring:

```bash
curl http://localhost:8000/metrics
```

Frontend có thể dùng để hiển thị:
- Request count
- Error rate
- Response time
- Order success rate

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-11 | Initial release with trading, market data, AI features |

---

**Happy coding! 🚀**
