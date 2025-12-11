"""
Futures contract class - the core domain object.
"""
from datetime import date
from typing import Dict, Optional, Literal

from .bars import FuturesDailyBar


class FuturesContract:
    """
    Represents a single futures contract (e.g., IC1505.CFX).
    This is the core domain object that encapsulates all contract-related logic.
    """
    
    def __init__(
        self,
        ts_code: str,
        fut_code: str,
        multiplier: float,
        list_date: date,
        delist_date: date,
        last_ddate: Optional[date] = None,
        name: Optional[str] = None,
        daily_bars: Optional[Dict[date, FuturesDailyBar]] = None
    ):
        self.ts_code = ts_code
        self.fut_code = fut_code
        self.multiplier = multiplier
        self.list_date = list_date
        self.delist_date = delist_date
        self.last_ddate = last_ddate or delist_date  # Delivery date = delist date for index futures
        self.name = name or ts_code
        self._daily_bars: Dict[date, FuturesDailyBar] = daily_bars or {}
    
    def __repr__(self) -> str:
        return f"FuturesContract({self.ts_code}, mult={self.multiplier}, delist={self.delist_date})"
    
    def __hash__(self) -> int:
        return hash(self.ts_code)
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, FuturesContract):
            return False
        return self.ts_code == other.ts_code
    
    @property
    def daily_bars(self) -> Dict[date, FuturesDailyBar]:
        return self._daily_bars
    
    def add_bar(self, bar: FuturesDailyBar) -> None:
        """Add a daily bar to the contract."""
        self._daily_bars[bar.trade_date] = bar
    
    def is_listed(self, trade_date: date) -> bool:
        """Check if the contract has been listed by the given date."""
        return trade_date >= self.list_date
    
    def is_expired(self, trade_date: date) -> bool:
        """Check if the contract has expired by the given date."""
        return trade_date > self.delist_date
    
    def is_tradable(self, trade_date: date) -> bool:
        """Check if the contract is tradable on the given date."""
        return self.list_date <= trade_date <= self.delist_date
    
    def get_bar(self, trade_date: date) -> Optional[FuturesDailyBar]:
        """Get daily bar for a specific date."""
        return self._daily_bars.get(trade_date)
    
    def get_price(
        self,
        trade_date: date,
        field: Literal['open', 'high', 'low', 'close', 'settle'] = 'settle'
    ) -> Optional[float]:
        """
        Get price for a specific date.
        Default to settlement price for mark-to-market.
        """
        bar = self.get_bar(trade_date)
        if bar is None:
            return None
        return getattr(bar, field)
    
    def days_to_expiry(self, trade_date: date) -> int:
        """
        Calculate trading days to expiry.
        Note: This returns calendar days. For trading days, need calendar.
        """
        return (self.delist_date - trade_date).days
    
    def get_volume(self, trade_date: date) -> float:
        """Get trading volume for a specific date."""
        bar = self.get_bar(trade_date)
        return bar.volume if bar else 0.0
    
    def get_open_interest(self, trade_date: date) -> float:
        """Get open interest for a specific date."""
        bar = self.get_bar(trade_date)
        return bar.open_interest if bar else 0.0
    
    def get_trading_dates(self) -> list:
        """Get all trading dates with data in sorted order."""
        return sorted(self._daily_bars.keys())
