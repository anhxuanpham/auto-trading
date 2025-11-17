"""
Example: Connecting to DNSE Market Data Feed

This example demonstrates how to:
1. Initialize market data connection
2. Subscribe to real-time data
3. Receive and process market updates
4. Use WebSocket for streaming
"""
import asyncio
import requests
import json
from websockets import connect


# Configuration
API_BASE_URL = "http://localhost:8000"


def initialize_market_data():
    """Step 1: Initialize market data connection."""
    print("1️⃣ Initializing market data...")

    response = requests.post(f"{API_BASE_URL}/market-data/initialize")
    result = response.json()

    if result["success"]:
        print(f"✅ Connected! Client ID: {result['client_id']}")
        return True
    else:
        print(f"❌ Failed: {result}")
        return False


def subscribe_to_symbol(symbol: str):
    """Step 2: Subscribe to stock info for a symbol."""
    print(f"\n2️⃣ Subscribing to {symbol}...")

    response = requests.post(
        f"{API_BASE_URL}/market-data/subscribe",
        json={
            "messageType": "STOCK_INFO",
            "symbol": symbol
        }
    )
    result = response.json()

    if result["success"]:
        print(f"✅ Subscribed to: {result['topic']}")
        return True
    else:
        print(f"❌ Failed: {result}")
        return False


def subscribe_to_ticks(symbol: str):
    """Subscribe to real-time ticks/trades."""
    print(f"\n3️⃣ Subscribing to ticks for {symbol}...")

    response = requests.post(
        f"{API_BASE_URL}/market-data/subscribe",
        json={
            "messageType": "TICK",
            "symbol": symbol
        }
    )
    result = response.json()

    if result["success"]:
        print(f"✅ Subscribed to ticks: {result['topic']}")
        return True
    else:
        print(f"❌ Failed: {result}")
        return False


def subscribe_to_order_book(symbol: str):
    """Subscribe to best bid/ask prices."""
    print(f"\n4️⃣ Subscribing to order book for {symbol}...")

    response = requests.post(
        f"{API_BASE_URL}/market-data/subscribe",
        json={
            "messageType": "TOP_PRICE",
            "symbol": symbol
        }
    )
    result = response.json()

    if result["success"]:
        print(f"✅ Subscribed to order book: {result['topic']}")
        return True
    else:
        print(f"❌ Failed: {result}")
        return False


async def stream_market_data():
    """Step 3: Connect to WebSocket and receive streaming data."""
    print("\n5️⃣ Connecting to WebSocket stream...")

    ws_url = "ws://localhost:8000/market-data/ws"

    async with connect(ws_url) as websocket:
        print("✅ WebSocket connected! Receiving data...\n")
        print("=" * 80)

        message_count = 0

        while True:
            try:
                # Receive message
                message = await websocket.recv()
                data = json.loads(message)

                message_count += 1

                # Process based on message type
                msg_type = data.get("type")

                if msg_type == "STOCK_INFO":
                    stock_data = data["data"]
                    print(f"📊 [{stock_data['symbol']}] Stock Info:")
                    print(f"   Last Price: {stock_data.get('lastPrice', 'N/A')}")
                    print(f"   Change: {stock_data.get('change', 'N/A')} "
                          f"({stock_data.get('changePercent', 'N/A')}%)")
                    print(f"   Session ID: {stock_data.get('tradingSessionId', 'N/A')}")
                    print(f"   Status: {stock_data.get('securityStatus', 'N/A')}")

                elif msg_type == "TICK":
                    tick_data = data["data"]
                    print(f"💹 [{tick_data['symbol']}] Trade:")
                    print(f"   Price: {tick_data.get('price', 'N/A')}")
                    print(f"   Volume: {tick_data.get('volume', 'N/A')}")
                    print(f"   Time: {tick_data.get('timestamp', 'N/A')}")

                elif msg_type == "TOP_PRICE":
                    book_data = data["data"]
                    print(f"📖 [{book_data['symbol']}] Order Book:")
                    print(f"   Best Bid: {book_data.get('bestBidPrice', 'N/A')} "
                          f"x {book_data.get('bestBidQuantity', 'N/A')}")
                    print(f"   Best Ask: {book_data.get('bestAskPrice', 'N/A')} "
                          f"x {book_data.get('bestAskQuantity', 'N/A')}")

                elif msg_type == "BOARD_EVENT":
                    event_data = data["data"]
                    print(f"🔔 Market Event:")
                    print(f"   Market ID: {event_data.get('marketId', 'N/A')}")
                    print(f"   Session ID: {event_data.get('tradingSessionId', 'N/A')}")
                    print(f"   Event: {event_data.get('eventId', 'N/A')}")

                print(f"   [Total messages: {message_count}]")
                print("-" * 80)

                # Send ping every 30 seconds to keep connection alive
                if message_count % 30 == 0:
                    await websocket.send(json.dumps({"type": "ping"}))

            except KeyboardInterrupt:
                print("\n⏹️ Stopping...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                break


def check_status():
    """Check market data connection status."""
    response = requests.get(f"{API_BASE_URL}/market-data/status")
    status = response.json()

    print("\n📊 Market Data Status:")
    print(f"   Initialized: {status.get('initialized', False)}")
    print(f"   Connected: {status.get('connected', False)}")
    print(f"   Active WebSockets: {status.get('active_websockets', 0)}")
    print(f"   Subscribed Topics: {len(status.get('subscribed_topics', []))}")

    for topic in status.get('subscribed_topics', []):
        print(f"     - {topic}")


async def main():
    """Main example flow."""
    print("🚀 DNSE Market Data Example\n")

    # Step 1: Initialize
    if not initialize_market_data():
        print("Failed to initialize. Make sure the backend is running.")
        return

    # Step 2: Subscribe to symbols
    symbols = ["VNM", "HPG", "VIC"]  # Change to your preferred symbols

    for symbol in symbols:
        subscribe_to_symbol(symbol)
        subscribe_to_ticks(symbol)
        subscribe_to_order_book(symbol)

    # Check status
    check_status()

    # Step 3: Stream data
    print("\n▶️ Starting WebSocket stream (Press Ctrl+C to stop)...")
    await asyncio.sleep(2)  # Give subscriptions time to activate

    try:
        await stream_market_data()
    except KeyboardInterrupt:
        print("\n✅ Done!")


if __name__ == "__main__":
    # Note: Make sure the FastAPI backend is running first!
    # Run with: python main.py

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
