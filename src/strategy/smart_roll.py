"""
Smart roll strategy - liquidity driven rolling.
"""
from datetime import date
from typing import Optional, Literal
from loguru import logger

from ..domain.contract import FuturesContract
from ..domain.chain import ContractChain
from ..data.signal_snapshot import SignalSnapshot
from .baseline_roll import BaselineRollStrategy


class SmartRollStrategy(BaselineRollStrategy):
    """
    Smart rolling strategy based on liquidity crossover.
    
    Logic:
    1. Monitor the next dominant contract (usually next month or next quarter).
    2. Roll when the next contract's Volume or Open Interest exceeds the current holding.
    3. Safety: Force roll if days to expiry is too small (e.g., 1 day), regardless of liquidity.
    """
    
    def __init__(
        self,
        contract_chain: ContractChain,
        roll_days_before_expiry: int = 1,  # Force roll if <= 1 day left
        contract_selection: str = 'nearby', # Initial selection
        target_leverage: float = 1.0,
        min_roll_days: int = 5,
        signal_price_field: str = "open",
        roll_criteria: Literal['volume', 'oi'] = 'volume', # Trigger criteria
    ):
        super().__init__(
            contract_chain=contract_chain,
            roll_days_before_expiry=roll_days_before_expiry,
            contract_selection=contract_selection,
            target_leverage=target_leverage,
            min_roll_days=min_roll_days,
            signal_price_field=signal_price_field
        )
        self.roll_criteria = roll_criteria
        self._check_next_contract: Optional[FuturesContract] = None

    def _should_roll(self, contract: FuturesContract, snapshot: SignalSnapshot) -> bool:
        """
        Check if we should roll based on liquidity crossover or forced expiry.
        """
        trade_date = snapshot.trade_date
        
        # 1. Safety Check: Force roll if very close to expiry
        days_to_expiry = contract.days_to_expiry(trade_date)
        if days_to_expiry <= self.roll_days_before_expiry:
            logger.info(f"Force rolling {contract.ts_code}: days_to_expiry={days_to_expiry}")
            return True
            
        # 2. Identify the candidate for liquidity comparison
        candidates = self.contract_chain.get_contracts_expiring_after(
            trade_date, 
            min_days=self.min_roll_days
        )
        # Filter out current contract
        candidates = [c for c in candidates if c.ts_code != contract.ts_code]
        
        if not candidates:
            return False
            
        # The most likely roll target is the first one (next expiry)
        candidate = candidates[0]
        
        # 3. Liquidity Comparison (using T-1 data from snapshot)
        current_val = 0.0
        candidate_val = 0.0
        
        if self.roll_criteria == 'volume':
            current_val = snapshot.get_prev_volume(contract.ts_code) or 0.0
            candidate_val = snapshot.get_prev_volume(candidate.ts_code) or 0.0
        elif self.roll_criteria == 'oi':
            current_val = snapshot.get_prev_oi(contract.ts_code) or 0.0
            candidate_val = snapshot.get_prev_oi(candidate.ts_code) or 0.0
            
        # Trigger roll if candidate has more liquidity
        if candidate_val > current_val and candidate_val > 0:
            logger.info(f"Liquidity roll triggered: {candidate.ts_code} ({candidate_val}) > {contract.ts_code} ({current_val})")
            return True
            
        return False

    # No need to override on_bar anymore since base class handles passing snapshot
