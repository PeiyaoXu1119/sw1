"""
Position class - represents holdings of a specific futures contract.
"""
from datetime import date
from typing import Optional

from ..domain.contract import FuturesContract


class Position:
    """
    Represents a position in a specific futures contract.
    Handles mark-to-market PnL calculation.
    """
    
    def __init__(
        self,
        contract: FuturesContract,
        volume: int,
        entry_price: float,
        last_settle: Optional[float] = None
    ):
        """
        Args:
            contract: The futures contract
            volume: Number of lots (positive=long, negative=short)
            entry_price: Average entry price
            last_settle: Previous settlement price for mark-to-market
        """
        self.contract = contract
        self.volume = volume
        self.entry_price = entry_price
        self.last_settle = last_settle or entry_price
    
    def __repr__(self) -> str:
        direction = "LONG" if self.volume > 0 else "SHORT"
        return f"Position({self.contract.ts_code}, {direction} {abs(self.volume)} lots @ {self.last_settle:.2f})"
    
    @property
    def ts_code(self) -> str:
        return self.contract.ts_code
    
    @property
    def multiplier(self) -> float:
        return self.contract.multiplier
    
    def mark_to_market(self, trade_date: date) -> float:
        """
        Calculate daily mark-to-market PnL.
        PnL = (today_settle - yesterday_settle) * volume * multiplier
        
        Returns: Daily PnL in currency units
        """
        today_settle = self.contract.get_price(trade_date, 'settle')
        if today_settle is None:
            return 0.0
        
        pnl = (today_settle - self.last_settle) * self.volume * self.multiplier
        
        # Update last_settle for next day
        self.last_settle = today_settle
        
        return pnl
    
    def notional_value(self, trade_date: date) -> float:
        """
        Calculate notional value of the position.
        Notional = |price * volume * multiplier|
        """
        price = self.contract.get_price(trade_date, 'settle')
        if price is None:
            price = self.last_settle
        
        return abs(price * self.volume * self.multiplier)
    
    def days_to_expiry(self, trade_date: date) -> int:
        """Get days to expiry for this position's contract."""
        return self.contract.days_to_expiry(trade_date)
    
    def is_expired(self, trade_date: date) -> bool:
        """Check if the position's contract has expired."""
        return self.contract.is_expired(trade_date)
    
    def update_volume(self, delta: int, price: float) -> float:
        """
        Update position volume (for partial close or add).
        Returns: Realized PnL from the trade
        """
        if delta == 0:
            return 0.0
        
        realized_pnl = 0.0
        
        # Closing position (reducing)
        if (self.volume > 0 and delta < 0) or (self.volume < 0 and delta > 0):
            close_volume = min(abs(delta), abs(self.volume))
            if self.volume > 0:
                realized_pnl = (price - self.entry_price) * close_volume * self.multiplier
            else:
                realized_pnl = (self.entry_price - price) * close_volume * self.multiplier
        
        # Update volume
        new_volume = self.volume + delta
        
        # Update entry price if adding to position
        if new_volume != 0 and abs(new_volume) > abs(self.volume):
            add_volume = abs(delta)
            old_value = self.entry_price * abs(self.volume)
            new_value = price * add_volume
            self.entry_price = (old_value + new_value) / abs(new_volume)
        
        self.volume = new_volume
        self.last_settle = price
        
        return realized_pnl
