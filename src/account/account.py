"""
Account class - manages cash, positions, and NAV.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Union
import pandas as pd
from loguru import logger

from ..domain.contract import FuturesContract
from ..data.snapshot import MarketSnapshot
from ..data.signal_snapshot import SignalSnapshot
from .position import Position

# Type alias for snapshots that can be used for execution
ExecutionSnapshot = Union[MarketSnapshot, SignalSnapshot]


@dataclass
class TradeRecord:
    """Record of a single trade."""
    trade_date: date
    ts_code: str
    direction: str  # 'BUY' or 'SELL'
    volume: int
    price: float
    amount: float  # volume * price * multiplier
    commission: float = 0.0
    reason: str = ""  # e.g., 'ROLL', 'REBALANCE', 'OPEN'
    realized_pnl: float = 0.0  # PnL realized from this trade (for closing trades)


class Account:
    """
    Investment account managing cash, positions, and NAV.
    Handles mark-to-market, margin calculation, and trade execution.
    """
    
    def __init__(
        self,
        initial_capital: float,
        margin_rate: float = 0.12,
        commission_rate: float = 0.00023,  # 0.023% per trade
        execution_price_field: str = "open",  # Price field for trade execution
    ):
        self.initial_capital = initial_capital
        self.margin_rate = margin_rate
        self.commission_rate = commission_rate
        self.execution_price_field = execution_price_field
        
        self.cash = initial_capital
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        
        self._positions: Dict[str, Position] = {}
        self._nav_history: Dict[date, float] = {}
        self._trade_log: List[TradeRecord] = []
    
    def __repr__(self) -> str:
        return f"Account(capital={self.initial_capital:.0f}, equity={self.equity:.0f}, positions={len(self._positions)})"
    
    @property
    def positions(self) -> Dict[str, Position]:
        return self._positions
    
    @property
    def nav_history(self) -> Dict[date, float]:
        return self._nav_history
    
    @property
    def trade_log(self) -> List[TradeRecord]:
        return self._trade_log
    
    @property
    def equity(self) -> float:
        """Total account equity = cash + unrealized PnL."""
        return self.cash + self.unrealized_pnl
    
    @property
    def nav(self) -> float:
        """Net asset value = equity / initial_capital."""
        return self.equity / self.initial_capital
    
    def mark_to_market(self, snapshot: MarketSnapshot) -> float:
        """
        Perform daily mark-to-market for all positions.
        Updates unrealized PnL and cash (for futures daily settlement).
        
        Returns: Total daily PnL
        """
        trade_date = snapshot.trade_date
        daily_pnl = 0.0
        
        for ts_code, position in list(self._positions.items()):
            pnl = position.mark_to_market(trade_date)
            daily_pnl += pnl
        
        # For futures, daily PnL is settled to cash
        self.cash += daily_pnl
        
        # Update unrealized PnL (for futures, this should be ~0 after daily settlement)
        self._update_unrealized_pnl(snapshot)
        
        return daily_pnl
    
    def _update_unrealized_pnl(self, snapshot: MarketSnapshot) -> None:
        """Update unrealized PnL based on current prices."""
        self.unrealized_pnl = 0.0
        # For futures with daily settlement, unrealized PnL is effectively 0
        # But we keep this for completeness
    
    def required_margin(self, snapshot: MarketSnapshot) -> float:
        """
        Calculate total margin required for all positions.
        Margin = sum(|notional| * margin_rate)
        """
        total_margin = 0.0
        for position in self._positions.values():
            notional = position.notional_value(snapshot.trade_date)
            total_margin += notional * self.margin_rate
        return total_margin
    
    def available_margin(self, snapshot: MarketSnapshot) -> float:
        """Calculate available margin for new positions."""
        return self.cash - self.required_margin(snapshot)
    
    def get_position(self, ts_code: str) -> Optional[Position]:
        """Get position for a specific contract."""
        return self._positions.get(ts_code)
    
    def get_position_volume(self, ts_code: str) -> int:
        """Get position volume for a specific contract."""
        pos = self._positions.get(ts_code)
        return pos.volume if pos else 0
    
    def rebalance_to_target(
        self,
        target_positions: Dict[str, int],
        snapshot: ExecutionSnapshot,
        contracts: Dict[str, FuturesContract],
        reason: str = "REBALANCE"
    ) -> float:
        """
        Rebalance portfolio to target positions.
        
        Args:
            target_positions: Dict[ts_code, target_volume]
            snapshot: SignalSnapshot (for open execution) or MarketSnapshot
            contracts: Dict of FuturesContract objects
            reason: Trade reason for logging
            
        Returns: Total commission paid
        """
        trade_date = snapshot.trade_date
        total_commission = 0.0
        
        # Close positions not in target
        for ts_code in list(self._positions.keys()):
            if ts_code not in target_positions or target_positions[ts_code] == 0:
                commission = self._close_position(ts_code, snapshot, reason)
                total_commission += commission
        
        # Open or adjust positions
        for ts_code, target_volume in target_positions.items():
            if target_volume == 0:
                continue
            
            current_volume = self.get_position_volume(ts_code)
            delta = target_volume - current_volume
            
            if delta != 0:
                contract = contracts.get(ts_code)
                if contract is None:
                    logger.warning(f"Contract not found: {ts_code}")
                    continue
                
                price = snapshot.get_futures_price(ts_code, self.execution_price_field)
                if price is None:
                    logger.warning(f"No {self.execution_price_field} price for {ts_code} on {trade_date}")
                    continue
                
                commission = self._execute_trade(contract, delta, price, trade_date, reason)
                total_commission += commission
        
        return total_commission
    
    def _execute_trade(
        self,
        contract: FuturesContract,
        volume: int,
        price: float,
        trade_date: date,
        reason: str
    ) -> float:
        """
        Execute a trade and update positions.
        Returns: Commission paid
        """
        ts_code = contract.ts_code
        amount = abs(volume * price * contract.multiplier)
        commission = amount * self.commission_rate
        
        # Deduct commission first
        self.cash -= commission
        
        # Calculate realized PnL (for closing trades)
        realized_pnl = 0.0
        
        # Update or create position
        if ts_code in self._positions:
            position = self._positions[ts_code]
            realized_pnl = position.update_volume(volume, price)
            self.realized_pnl += realized_pnl
            
            # Remove position if closed
            if position.volume == 0:
                del self._positions[ts_code]
        else:
            # New position - no realized PnL
            position = Position(
                contract=contract,
                volume=volume,
                entry_price=price,
                last_settle=price,
            )
            self._positions[ts_code] = position
        
        # Record trade with PnL
        direction = "BUY" if volume > 0 else "SELL"
        trade = TradeRecord(
            trade_date=trade_date,
            ts_code=ts_code,
            direction=direction,
            volume=abs(volume),
            price=price,
            amount=amount,
            commission=commission,
            reason=reason,
            realized_pnl=realized_pnl,
        )
        self._trade_log.append(trade)
        
        return commission
    
    def _close_position(
        self,
        ts_code: str,
        snapshot: ExecutionSnapshot,
        reason: str
    ) -> float:
        """
        Close a position entirely.
        Returns: Commission paid
        """
        position = self._positions.get(ts_code)
        if position is None:
            return 0.0
        
        price = snapshot.get_futures_price(ts_code, self.execution_price_field)
        if price is None:
            price = position.last_settle
        
        volume = -position.volume  # Opposite direction to close
        commission = self._execute_trade(
            position.contract,
            volume,
            price,
            snapshot.trade_date,
            reason,
        )
        
        return commission
    
    def record_nav(self, trade_date: date) -> None:
        """Record NAV for the given date."""
        self._nav_history[trade_date] = self.nav
    
    def get_nav_series(self) -> pd.Series:
        """Get NAV history as pandas Series."""
        dates = sorted(self._nav_history.keys())
        values = [self._nav_history[d] for d in dates]
        return pd.Series(values, index=pd.DatetimeIndex(dates))
    
    def get_trade_summary(self) -> pd.DataFrame:
        """Get trade log as DataFrame."""
        if not self._trade_log:
            return pd.DataFrame()
        
        records = [
            {
                "date": t.trade_date,
                "contract": t.ts_code,
                "direction": t.direction,
                "volume": t.volume,
                "price": t.price,
                "amount": t.amount,
                "commission": t.commission,
                "realized_pnl": t.realized_pnl,
                "reason": t.reason,
            }
            for t in self._trade_log
        ]
        return pd.DataFrame(records)
    
    def get_holding_contracts(self) -> List[str]:
        """Get list of currently held contract codes."""
        return list(self._positions.keys())
