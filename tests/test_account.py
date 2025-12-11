"""
Tests for account layer (Layer 3).
"""
import pytest
from datetime import date

from src.domain.bars import IndexDailyBar, FuturesDailyBar
from src.domain.contract import FuturesContract
from src.data.snapshot import MarketSnapshot
from src.account.position import Position
from src.account.account import Account


class TestPosition:
    """Tests for Position."""
    
    @pytest.fixture
    def sample_contract(self):
        contract = FuturesContract(
            ts_code="IC2401.CFX",
            fut_code="IC",
            multiplier=200.0,
            list_date=date(2023, 10, 1),
            delist_date=date(2024, 1, 19),
        )
        # Add bars for two days
        for i, (d, settle) in enumerate([
            (date(2024, 1, 5), 5000.0),
            (date(2024, 1, 8), 5050.0),
        ]):
            bar = FuturesDailyBar(
                trade_date=d,
                open=settle - 20,
                high=settle + 50,
                low=settle - 50,
                close=settle - 10,
                settle=settle,
                pre_settle=settle - 50 if i > 0 else settle,
                volume=10000.0,
                amount=500000.0,
                open_interest=50000.0,
            )
            contract.add_bar(bar)
        return contract
    
    def test_create_position(self, sample_contract):
        pos = Position(
            contract=sample_contract,
            volume=10,
            entry_price=5000.0,
        )
        assert pos.volume == 10
        assert pos.ts_code == "IC2401.CFX"
    
    def test_mark_to_market(self, sample_contract):
        pos = Position(
            contract=sample_contract,
            volume=10,
            entry_price=5000.0,
            last_settle=5000.0,
        )
        
        # Price goes from 5000 to 5050
        pnl = pos.mark_to_market(date(2024, 1, 8))
        expected_pnl = (5050.0 - 5000.0) * 10 * 200.0  # 100,000
        assert pnl == expected_pnl
        assert pos.last_settle == 5050.0
    
    def test_notional_value(self, sample_contract):
        pos = Position(
            contract=sample_contract,
            volume=10,
            entry_price=5000.0,
        )
        
        notional = pos.notional_value(date(2024, 1, 5))
        expected = 5000.0 * 10 * 200.0  # 10,000,000
        assert notional == expected


class TestAccount:
    """Tests for Account."""
    
    @pytest.fixture
    def sample_account(self):
        return Account(
            initial_capital=10_000_000.0,
            margin_rate=0.12,
            commission_rate=0.00023,
        )
    
    @pytest.fixture
    def sample_contract(self):
        contract = FuturesContract(
            ts_code="IC2401.CFX",
            fut_code="IC",
            multiplier=200.0,
            list_date=date(2023, 10, 1),
            delist_date=date(2024, 1, 19),
        )
        for d, settle in [(date(2024, 1, 5), 5000.0), (date(2024, 1, 8), 5050.0)]:
            bar = FuturesDailyBar(
                trade_date=d,
                open=settle - 20,
                high=settle + 50,
                low=settle - 50,
                close=settle - 10,
                settle=settle,
                pre_settle=settle - 50,
                volume=10000.0,
                amount=500000.0,
                open_interest=50000.0,
            )
            contract.add_bar(bar)
        return contract
    
    @pytest.fixture
    def sample_snapshot(self, sample_contract):
        index_bar = IndexDailyBar(
            trade_date=date(2024, 1, 5),
            open=5000.0,
            high=5100.0,
            low=4900.0,
            close=5050.0,
        )
        futures_quotes = {
            "IC2401.CFX": sample_contract.get_bar(date(2024, 1, 5)),
        }
        return MarketSnapshot(date(2024, 1, 5), index_bar, futures_quotes)
    
    def test_initial_state(self, sample_account):
        assert sample_account.cash == 10_000_000.0
        assert sample_account.equity == 10_000_000.0
        assert sample_account.nav == 1.0
        assert len(sample_account.positions) == 0
    
    def test_rebalance_to_target(self, sample_account, sample_snapshot, sample_contract):
        contracts = {sample_contract.ts_code: sample_contract}
        
        # Open position: buy 10 lots
        target = {"IC2401.CFX": 10}
        commission = sample_account.rebalance_to_target(target, sample_snapshot, contracts)
        
        assert "IC2401.CFX" in sample_account.positions
        assert sample_account.positions["IC2401.CFX"].volume == 10
        assert commission > 0
    
    def test_required_margin(self, sample_account, sample_snapshot, sample_contract):
        contracts = {sample_contract.ts_code: sample_contract}
        
        # Open position
        sample_account.rebalance_to_target({"IC2401.CFX": 10}, sample_snapshot, contracts)
        
        # Calculate margin
        margin = sample_account.required_margin(sample_snapshot)
        expected = 5000.0 * 10 * 200.0 * 0.12  # 1,200,000
        assert abs(margin - expected) < 1000  # Allow small difference due to price
    
    def test_record_nav(self, sample_account):
        sample_account.record_nav(date(2024, 1, 5))
        assert date(2024, 1, 5) in sample_account.nav_history
        assert sample_account.nav_history[date(2024, 1, 5)] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
