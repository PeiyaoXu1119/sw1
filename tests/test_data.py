"""
Tests for data layer (Layer 2).
"""
import pytest
from datetime import date
from pathlib import Path

from src.domain.bars import IndexDailyBar, FuturesDailyBar
from src.domain.index import EquityIndex
from src.domain.contract import FuturesContract
from src.domain.chain import ContractChain
from src.data.snapshot import MarketSnapshot
from src.data.handler import DataHandler


class TestMarketSnapshot:
    """Tests for MarketSnapshot."""
    
    @pytest.fixture
    def sample_snapshot(self):
        index_bar = IndexDailyBar(
            trade_date=date(2024, 1, 5),
            open=5000.0,
            high=5100.0,
            low=4900.0,
            close=5050.0,
        )
        
        futures_quotes = {
            "IC2401.CFX": FuturesDailyBar(
                trade_date=date(2024, 1, 5),
                open=4980.0,
                high=5080.0,
                low=4880.0,
                close=5030.0,
                settle=5020.0,
                pre_settle=4980.0,
                volume=10000.0,
                amount=500000.0,
                open_interest=50000.0,
            ),
            "IC2402.CFX": FuturesDailyBar(
                trade_date=date(2024, 1, 5),
                open=4960.0,
                high=5060.0,
                low=4860.0,
                close=5010.0,
                settle=5000.0,
                pre_settle=4960.0,
                volume=5000.0,
                amount=250000.0,
                open_interest=30000.0,
            ),
        }
        
        return MarketSnapshot(date(2024, 1, 5), index_bar, futures_quotes)
    
    def test_get_index_close(self, sample_snapshot):
        assert sample_snapshot.get_index_close() == 5050.0
    
    def test_get_futures_price(self, sample_snapshot):
        settle = sample_snapshot.get_futures_price("IC2401.CFX", 'settle')
        assert settle == 5020.0
    
    def test_get_basis(self, sample_snapshot):
        # Basis = (F - S) / S = (5020 - 5050) / 5050
        basis = sample_snapshot.get_basis("IC2401.CFX", relative=True)
        expected = (5020.0 - 5050.0) / 5050.0
        assert abs(basis - expected) < 1e-6
    
    def test_get_basis_absolute(self, sample_snapshot):
        basis = sample_snapshot.get_basis("IC2401.CFX", relative=False)
        assert basis == 5020.0 - 5050.0
    
    def test_get_available_contracts(self, sample_snapshot):
        contracts = sample_snapshot.get_available_contracts()
        assert len(contracts) == 2
        assert "IC2401.CFX" in contracts


class TestDataHandler:
    """Tests for DataHandler loading from processed data."""
    
    @pytest.fixture
    def data_handler(self):
        data_path = Path("/root/sw1/processed_data")
        if not data_path.exists():
            pytest.skip("Processed data not available")
        return DataHandler.from_processed_data(str(data_path), "IC")
    
    def test_load_index(self, data_handler):
        index = data_handler.get_index()
        assert index.index_code == "000905.SH"
        assert len(index.daily_bars) > 0
    
    def test_load_contract_chain(self, data_handler):
        chain = data_handler.get_contract_chain()
        assert chain.fut_code == "IC"
        assert len(chain.contracts) > 0
    
    def test_trading_calendar(self, data_handler):
        calendar = data_handler.get_trading_calendar()
        assert len(calendar) > 0
        assert all(isinstance(d, date) for d in calendar)
    
    def test_get_snapshot(self, data_handler):
        calendar = data_handler.get_trading_calendar()
        trade_date = calendar[100]  # Get a date in the middle
        
        snapshot = data_handler.get_snapshot(trade_date)
        assert snapshot is not None
        assert snapshot.trade_date == trade_date
        assert snapshot.index_bar is not None
    
    def test_snapshot_caching(self, data_handler):
        calendar = data_handler.get_trading_calendar()
        trade_date = calendar[100]
        
        # First call
        snapshot1 = data_handler.get_snapshot(trade_date)
        # Second call should return cached
        snapshot2 = data_handler.get_snapshot(trade_date)
        
        assert snapshot1 is snapshot2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
