"""
Daily bar data structures for index and futures.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class IndexDailyBar:
    """Daily bar data for equity index."""
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    
    def __repr__(self) -> str:
        return f"IndexDailyBar({self.trade_date}, close={self.close:.2f})"


@dataclass(frozen=True)
class FuturesDailyBar:
    """Daily bar data for futures contract."""
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    settle: float           # Settlement price - core field for mark-to-market
    pre_settle: float       # Previous settlement price
    volume: float           # Trading volume (lots)
    amount: float           # Trading amount (10k CNY)
    open_interest: float    # Open interest (lots)
    oi_change: Optional[float] = None  # Open interest change
    
    def __repr__(self) -> str:
        return f"FuturesDailyBar({self.trade_date}, settle={self.settle:.2f}, vol={self.volume:.0f})"
