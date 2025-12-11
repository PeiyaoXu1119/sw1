"""
Equity index class.
"""
from datetime import date
from typing import Dict, Optional, List
import pandas as pd

from .bars import IndexDailyBar


class EquityIndex:
    """Represents an equity index (e.g., CSI 500)."""
    
    def __init__(
        self,
        index_code: str,
        name: str,
        daily_bars: Optional[Dict[date, IndexDailyBar]] = None
    ):
        self.index_code = index_code
        self.name = name
        self._daily_bars: Dict[date, IndexDailyBar] = daily_bars or {}
    
    def __repr__(self) -> str:
        return f"EquityIndex({self.index_code}, {self.name}, bars={len(self._daily_bars)})"
    
    @property
    def daily_bars(self) -> Dict[date, IndexDailyBar]:
        return self._daily_bars
    
    def add_bar(self, bar: IndexDailyBar) -> None:
        """Add a daily bar to the index."""
        self._daily_bars[bar.trade_date] = bar
    
    def get_bar(self, trade_date: date) -> Optional[IndexDailyBar]:
        """Get daily bar for a specific date."""
        return self._daily_bars.get(trade_date)
    
    def get_close(self, trade_date: date) -> Optional[float]:
        """Get closing price for a specific date."""
        bar = self.get_bar(trade_date)
        return bar.close if bar else None
    
    def get_trading_dates(self) -> List[date]:
        """Get all trading dates in sorted order."""
        return sorted(self._daily_bars.keys())
    
    def get_return_series(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.Series:
        """
        Get daily return series for benchmark NAV calculation.
        Returns: Series indexed by date with daily returns.
        """
        dates = self.get_trading_dates()
        
        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]
        
        closes = [self._daily_bars[d].close for d in dates]
        series = pd.Series(closes, index=pd.DatetimeIndex(dates))
        return series.pct_change().fillna(0)
    
    def get_nav_series(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.Series:
        """
        Get normalized NAV series starting from 1.0.
        """
        dates = self.get_trading_dates()
        
        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]
        
        if not dates:
            return pd.Series(dtype=float)
        
        closes = [self._daily_bars[d].close for d in dates]
        nav = pd.Series(closes, index=pd.DatetimeIndex(dates))
        return nav / nav.iloc[0]
