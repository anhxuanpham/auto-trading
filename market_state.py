"""
Market State Manager - Maintains current state of market and trading sessions.

This module implements the "Map Phiên" (Session Mapping) logic from DNSE specs.
It tracks which order types are allowed based on current trading session.

CRITICAL: Different markets (HOSE vs HNX) have different session flows!
"""
import logging
from typing import Dict, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field

from market_data_schemas import (
    MarketID,
    BoardID,
    TradingSessionID,
    SecurityStatus,
    SymbolAdminStatus,
    StockInfo,
    Tick,
    BoardEvent
)

logger = logging.getLogger(__name__)


@dataclass
class SymbolState:
    """State of a single symbol."""
    symbol: str
    market_id: int
    board_id: int

    # Prices
    reference_price: Optional[float] = None
    ceiling_price: Optional[float] = None
    floor_price: Optional[float] = None
    current_price: Optional[float] = None
    last_price: Optional[float] = None

    # Session
    trading_session_id: int = TradingSessionID.CLOSED
    security_status: int = SecurityStatus.NO_HALT
    admin_status: int = SymbolAdminStatus.NORMAL

    # Timestamps
    last_update: Optional[str] = None
    last_tick_time: Optional[str] = None

    # Previous price for action calculation
    previous_price: Optional[float] = None


@dataclass
class MarketState:
    """State of a market (STO, STX, UPX)."""
    market_id: int
    trading_session_id: int = TradingSessionID.CLOSED
    last_board_event: Optional[str] = None
    last_update: Optional[str] = None


class MarketStateManager:
    """
    Singleton manager for market state.

    Responsibilities:
    1. Track current trading session for each market
    2. Maintain symbol states (prices, session info)
    3. Validate order placement based on session logic
    4. Process real-time market data updates
    """

    _instance: Optional["MarketStateManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.symbols: Dict[str, SymbolState] = {}
        self.markets: Dict[int, MarketState] = {}
        self._initialized = True

        logger.info("✅ MarketStateManager initialized")

    # ========================================================================
    # UPDATE METHODS (Called by market data callbacks)
    # ========================================================================

    def update_from_stock_info(self, stock_info: StockInfo):
        """
        Update state from StockInfo message.

        CRITICAL: This contains tradingSessionId which determines order types!
        """
        symbol = stock_info.symbol

        if symbol not in self.symbols:
            self.symbols[symbol] = SymbolState(
                symbol=symbol,
                market_id=stock_info.marketId,
                board_id=stock_info.boardId
            )

        state = self.symbols[symbol]

        # Update prices
        state.reference_price = stock_info.referencePrice
        state.ceiling_price = stock_info.ceilingPrice
        state.floor_price = stock_info.floorPrice
        if stock_info.lastPrice:
            state.current_price = stock_info.lastPrice
            state.last_price = stock_info.lastPrice

        # Update session info (CRITICAL!)
        old_session = state.trading_session_id
        state.trading_session_id = stock_info.tradingSessionId
        state.security_status = stock_info.securityStatus
        state.admin_status = stock_info.symbolAdminStatusCode
        state.last_update = stock_info.timestamp

        # Log session changes
        if old_session != stock_info.tradingSessionId:
            logger.info(
                f"📊 {symbol}: Session changed {old_session} -> {stock_info.tradingSessionId} "
                f"({self._get_session_name(stock_info.tradingSessionId)})"
            )

    def update_from_tick(self, tick: Tick):
        """
        Update state from Tick (trade) message.
        Calculate action (B/S) based on price movement.
        """
        symbol = tick.symbol

        if symbol not in self.symbols:
            # Initialize if doesn't exist
            self.symbols[symbol] = SymbolState(
                symbol=symbol,
                market_id=0,  # Unknown for now
                board_id=0
            )

        state = self.symbols[symbol]

        # Store previous price for action calculation
        if state.current_price:
            state.previous_price = state.current_price

        # Update current price
        if tick.price:
            state.current_price = tick.price
            state.last_price = tick.price

        state.last_tick_time = tick.timestamp

    def update_from_board_event(self, event: BoardEvent):
        """
        Update market-wide session from BoardEvent.

        This affects all symbols in that market.
        """
        market_id = event.marketId

        if market_id not in self.markets:
            self.markets[market_id] = MarketState(market_id=market_id)

        market = self.markets[market_id]
        old_session = market.trading_session_id
        market.trading_session_id = event.tradingSessionId
        market.last_board_event = event.eventId
        market.last_update = event.timestamp

        logger.info(
            f"🔔 Market {market_id} ({self._get_market_name(market_id)}): "
            f"Session {old_session} -> {event.tradingSessionId} "
            f"({self._get_session_name(event.tradingSessionId)}) "
            f"[Event: {event.eventId}]"
        )

        # Update all symbols in this market
        for symbol, state in self.symbols.items():
            if state.market_id == market_id:
                state.trading_session_id = event.tradingSessionId

    # ========================================================================
    # QUERY METHODS
    # ========================================================================

    def get_symbol_state(self, symbol: str) -> Optional[SymbolState]:
        """Get current state of a symbol."""
        return self.symbols.get(symbol)

    def get_market_state(self, market_id: int) -> Optional[MarketState]:
        """Get current state of a market."""
        return self.markets.get(market_id)

    def get_trading_session(self, symbol: str) -> Optional[int]:
        """Get current trading session ID for a symbol."""
        state = self.get_symbol_state(symbol)
        return state.trading_session_id if state else None

    def is_market_open(self, symbol: str) -> bool:
        """Check if market is open for trading this symbol."""
        session = self.get_trading_session(symbol)
        if session is None:
            return False

        # Market is open if NOT closed and NOT halted
        return session != TradingSessionID.CLOSED and session != TradingSessionID.HALT

    def is_symbol_halted(self, symbol: str) -> bool:
        """Check if symbol is halted."""
        state = self.get_symbol_state(symbol)
        if not state:
            return True  # Unknown = assume halted

        return (
            state.security_status == SecurityStatus.HALT or
            state.trading_session_id == TradingSessionID.HALT
        )

    # ========================================================================
    # TRADING LOGIC - Based on "Map Phiên" from DNSE specs
    # ========================================================================

    def can_place_order_type(self, symbol: str, order_type: str) -> tuple[bool, str]:
        """
        Check if an order type can be placed for a symbol.

        Args:
            symbol: Stock symbol
            order_type: Order type (LO, MP, ATO, ATC, PLO, etc.)

        Returns:
            tuple: (can_place: bool, reason: str)

        Logic from DNSE specs:
        - HOSE (STO):
          * ATO session (10): Allow ATO, LO. No MP.
          * CONTINUOUS session (40): Allow MP, LO.
          * ATC session (30): Allow ATC, LO.
          * CLOSED (99): Reject all.

        - HNX (STX):
          * Starts with CONTINUOUS (40) at 09:00. No ATO.
          * ATC (30) at 14:30.
          * PLO (60) after ATC.
        """
        state = self.get_symbol_state(symbol)
        if not state:
            return False, "Symbol not found in state"

        # Check if halted
        if self.is_symbol_halted(symbol):
            return False, f"Symbol is halted (status={state.security_status})"

        # Check admin status
        if state.admin_status == SymbolAdminStatus.CONTROL:
            return False, "Symbol under trading control/restriction"

        session = state.trading_session_id
        market_id = state.market_id

        # Closed market
        if session == TradingSessionID.CLOSED:
            return False, "Market is closed"

        # HOSE Logic (MarketID=6)
        if market_id == MarketID.STO:
            if session == TradingSessionID.ATO:
                # ATO session: Allow ATO and LO only
                if order_type in ["ATO", "LO"]:
                    return True, "OK"
                elif order_type == "MP":
                    return False, "Market orders not allowed during ATO session"
                else:
                    return False, f"Order type {order_type} not allowed in ATO session"

            elif session == TradingSessionID.CONTINUOUS:
                # Continuous: Allow MP, LO
                if order_type in ["MP", "LO", "MTL"]:
                    return True, "OK"
                else:
                    return False, f"Order type {order_type} not allowed in continuous session"

            elif session == TradingSessionID.ATC:
                # ATC session: Allow ATC and LO
                if order_type in ["ATC", "LO"]:
                    return True, "OK"
                else:
                    return False, f"Order type {order_type} not allowed in ATC session"

            elif session == TradingSessionID.ORDER_ACCEPT_ONLY:
                # PLO session: Only limit orders
                if order_type == "PLO" or order_type == "LO":
                    return True, "OK"
                else:
                    return False, "Only PLO/LO allowed in post-trading session"

        # HNX Logic (MarketID=7)
        elif market_id == MarketID.STX:
            # HNX has no ATO - starts with CONTINUOUS
            if session == TradingSessionID.CONTINUOUS:
                if order_type in ["MP", "LO", "MTL"]:
                    return True, "OK"
                elif order_type == "ATO":
                    return False, "HNX does not have ATO session"
                else:
                    return False, f"Order type {order_type} not allowed"

            elif session == TradingSessionID.ATC:
                if order_type in ["ATC", "LO"]:
                    return True, "OK"
                else:
                    return False, f"Only ATC/LO allowed in ATC session"

            elif session == TradingSessionID.ORDER_ACCEPT_ONLY:
                # HNX has PLO session after ATC
                if order_type in ["PLO", "LO"]:
                    return True, "OK"
                else:
                    return False, "Only PLO/LO allowed after market close"

        # UpCom Logic (MarketID=8) - Similar to HNX
        elif market_id == MarketID.UPX:
            if session == TradingSessionID.CONTINUOUS:
                if order_type in ["MP", "LO", "MTL"]:
                    return True, "OK"
                else:
                    return False, f"Order type {order_type} not allowed"

        # Default: Unknown market or session
        return False, f"Unknown market/session combination (market={market_id}, session={session})"

    def get_allowed_order_types(self, symbol: str) -> Set[str]:
        """
        Get set of allowed order types for current session.

        Returns:
            set: Set of allowed order type strings (e.g., {"LO", "MP"})
        """
        state = self.get_symbol_state(symbol)
        if not state:
            return set()

        session = state.trading_session_id
        market_id = state.market_id

        # HOSE
        if market_id == MarketID.STO:
            if session == TradingSessionID.ATO:
                return {"ATO", "LO"}
            elif session == TradingSessionID.CONTINUOUS:
                return {"MP", "LO", "MTL"}
            elif session == TradingSessionID.ATC:
                return {"ATC", "LO"}
            elif session == TradingSessionID.ORDER_ACCEPT_ONLY:
                return {"PLO", "LO"}

        # HNX / UpCom
        elif market_id in [MarketID.STX, MarketID.UPX]:
            if session == TradingSessionID.CONTINUOUS:
                return {"MP", "LO", "MTL"}
            elif session == TradingSessionID.ATC:
                return {"ATC", "LO"}
            elif session == TradingSessionID.ORDER_ACCEPT_ONLY:
                return {"PLO", "LO"}

        return set()

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_session_name(self, session_id: int) -> str:
        """Get human-readable session name."""
        names = {
            TradingSessionID.GT_ORDER_LOAD: "Pre-day Load",
            TradingSessionID.ATO: "ATO (Opening Auction)",
            TradingSessionID.ATO_EXT: "ATO Extension",
            TradingSessionID.CONTINUOUS: "Continuous Trading",
            TradingSessionID.ATC: "ATC (Closing Auction)",
            TradingSessionID.ORDER_ACCEPT_ONLY: "PLO (Post-Limit Order)",
            TradingSessionID.HALT: "HALTED",
            TradingSessionID.CLOSED: "CLOSED"
        }
        return names.get(session_id, f"Unknown({session_id})")

    def _get_market_name(self, market_id: int) -> str:
        """Get human-readable market name."""
        names = {
            MarketID.STO: "HOSE",
            MarketID.STX: "HNX",
            MarketID.UPX: "UpCom",
            MarketID.DVX: "HNX Derivatives",
            MarketID.BDX: "HNX Bonds",
            MarketID.HCX: "HNX Corp Bonds"
        }
        return names.get(market_id, f"Market{market_id}")

    def get_statistics(self) -> dict:
        """Get current statistics."""
        return {
            "total_symbols": len(self.symbols),
            "tracked_markets": len(self.markets),
            "symbols_by_market": {
                market_id: len([s for s in self.symbols.values() if s.market_id == market_id])
                for market_id in self.markets.keys()
            },
            "symbols_by_session": {
                session: len([s for s in self.symbols.values() if s.trading_session_id == session])
                for session in set(s.trading_session_id for s in self.symbols.values())
            }
        }


# Global instance
def get_market_state_manager() -> MarketStateManager:
    """Get global MarketStateManager instance (singleton)."""
    return MarketStateManager()
