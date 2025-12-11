"""
Market snapshot - cross-sectional view of all market data on a single day.
"""
from datetime import date
from typing import Dict, Optional

from ..domain.bars import IndexDailyBar, FuturesDailyBar


class MarketSnapshot:
    """
    Cross-sectional view of all market data on a specific trading day.
    Provides a unified interface for strategy to access market data.
    """
    
    def __init__(
        self,
        trade_date: date,
        index_bar: IndexDailyBar,
        futures_quotes: Dict[str, FuturesDailyBar]
    ):
        self.trade_date = trade_date
        self.index_bar = index_bar
        self.futures_quotes = futures_quotes
    
    def __repr__(self) -> str:
        return f"MarketSnapshot({self.trade_date}, index={self.index_bar.close:.2f}, futures={len(self.futures_quotes)})"
    
    def get_contract_bar(self, ts_code: str) -> Optional[FuturesDailyBar]:
        """Get futures bar for a specific contract."""
        return self.futures_quotes.get(ts_code)
    
    def get_futures_price(
        self,
        ts_code: str,
        field: str = 'settle'
    ) -> Optional[float]:
        """Get futures price for a specific contract."""
        bar = self.get_contract_bar(ts_code)
        if bar is None:
            return None
        return getattr(bar, field, None)
    
    def get_index_close(self) -> float:
        """Get spot index closing price."""
        return self.index_bar.close
    
    def get_basis(
        self,
        ts_code: str,
        relative: bool = True,
        price_field: str = "open"
    ) -> Optional[float]:
        """
        Calculate basis for a specific contract.
        Args:
            ts_code: Contract code
            relative: If True, return (F - S) / S; else return F - S
            price_field: Price field to use (open, close, settle, pre_settle)
        Returns: Basis value or None if contract not found or price invalid.
        """
        # Use specified price field, fallback to close if not available
        futures_price = self.get_futures_price(ts_code, price_field)
        if futures_price is None or futures_price <= 0:
            futures_price = self.get_futures_price(ts_code, 'close')
        
        # Still invalid, return None
        if futures_price is None or futures_price <= 0:
            return None
        
        spot_price = self.index_bar.close
        if spot_price <= 0:
            return None
        
        if relative:
            return (futures_price - spot_price) / spot_price
        else:
            return futures_price - spot_price
    
    def get_available_contracts(self) -> list:
        """Get list of available contract codes in this snapshot."""
        return list(self.futures_quotes.keys())
