"""
Abstract strategy base class.
"""
from abc import ABC, abstractmethod
from typing import Dict

from ..domain.chain import ContractChain
from ..data.snapshot import MarketSnapshot
from ..account.account import Account


class Strategy(ABC):
    """
    Abstract base class for trading strategies.
    
    A strategy takes market snapshot and account state as input,
    and outputs target positions (contract -> volume).
    """
    
    def __init__(self, contract_chain: ContractChain):
        """
        Args:
            contract_chain: The contract chain to trade
        """
        self.contract_chain = contract_chain
    
    @abstractmethod
    def on_bar(
        self,
        snapshot: MarketSnapshot,
        account: Account
    ) -> Dict[str, int]:
        """
        Generate target positions based on current market and account state.
        
        Args:
            snapshot: Current market snapshot
            account: Current account state
            
        Returns:
            Dict mapping ts_code to target volume (positive=long, negative=short)
        """
        pass
    
    @property
    def fut_code(self) -> str:
        """Get the futures code this strategy trades."""
        return self.contract_chain.fut_code
    
    @property
    def index(self):
        """Get the underlying index."""
        return self.contract_chain.index
