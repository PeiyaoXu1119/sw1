# Index Enhancement Strategy Backtest System

## Project Overview

This is an OOP-based backtest system for equity index futures enhancement strategies. It captures excess returns over the benchmark by leveraging the tendency of a discounted futures price to converge to the spot index level as the contract approaches expiration.

## System Architecture

The system follows a 5-layer architecture:

```
+------------------------------------------------------------+
| Layer 5: Backtest & Analytics                              |
|   BacktestEngine, Analyzer                                 |
+------------------------------------------------------------+
| Layer 4: Strategy                                          |
|   Strategy (ABC), BaselineRollStrategy, BasisTimingStrategy|
+------------------------------------------------------------+
| Layer 3: Account & Portfolio                               |
|   Account, Position, TradeRecord                           |
+------------------------------------------------------------+
| Layer 2: Data & Snapshot                                   |
|   DataHandler, MarketSnapshot                              |
+------------------------------------------------------------+
| Layer 1: Domain / Instrument                               |
|   EquityIndex, FuturesContract, ContractChain, DailyBars   |
+------------------------------------------------------------+
```

## Project Structure

```
sw1/
├── config.toml                # Configuration file (editable)
├── main.py                    # Main entry point
├── docs/
│   ├── DESIGN.md              # Detailed design document
│   ├── BACKTEST_FLOW.md       # Step-by-step backtest flow
│   └── uml_class_diagram.puml # UML class diagram (PlantUML)
├── examples/                  # Interactive Jupyter notebooks
│   ├── 01_quick_start.ipynb   # Basic usage demo
│   ├── 02_explore_contracts.ipynb  # Explore domain objects
│   └── 03_compare_strategies.ipynb # Compare strategies
├── src/
│   ├── config.py              # Configuration management
│   ├── domain/                # Layer 1: Domain objects
│   ├── data/                  # Layer 2: Data handling
│   ├── account/               # Layer 3: Portfolio management
│   ├── strategy/              # Layer 4: Trading strategies
│   └── backtest/              # Layer 5: Backtest engine
├── tests/                     # Unit tests (42 tests)
├── scripts/
│   └── preprocess_data.py     # Data preprocessing script
├── output/                    # Backtest output
│   └── {strategy}_{fut}/      # Per-run outputs
│       ├── report.png         # Comprehensive visual report
│       ├── trade_log.csv      # Trade records
│       ├── nav_series.csv     # Daily NAV values
│       └── metrics.csv        # Performance metrics
├── processed_data/            # Processed parquet files
└── raw_data/                  # Original data files
```

## Quick Start

### 1. Preprocess Data

```bash
python scripts/preprocess_data.py
```

### 2. Configure Strategy

Edit `config.toml` to choose:
- **fut_code**: `IC` (CSI500), `IM` (CSI1000), or `IF` (CSI300)
- **strategy_type**: `baseline` or `basis_timing`
- **parameters**: roll days, leverage, thresholds, etc.

### 3. Run Backtest

```bash
python main.py                    # Use default config.toml
python main.py path/to/config.toml  # Use custom config
```

### 4. View Results

Results are saved to `output/{strategy}_{fut}/`:
- `report.png` - Visual dashboard with NAV, drawdown, metrics
- `trade_log.csv` - All trades with timestamps and prices
- `nav_series.csv` - Daily NAV for further analysis

### 5. Run Tests

```bash
pytest tests/ -v  # 42 tests
```

## Key Classes

### FuturesContract (Core Domain Object)

Each futures contract is represented as an object with:
- Metadata: `ts_code`, `fut_code`, `multiplier`, `list_date`, `delist_date`
- Daily bars: `Dict[date, FuturesDailyBar]`
- Methods: `is_tradable()`, `days_to_expiry()`, `get_price()`, etc.

### BaselineRollStrategy

Fixed-rule rolling strategy:
- Roll trigger: N days before expiry (default: 2 days)
- Contract selection: nearby, volume, or open interest based
- Target leverage: configurable (default: 1.0x)

### BasisTimingStrategy

Enhanced strategy with basis timing signals:
- Entry when basis < threshold (e.g., -2% discount)
- Exit when basis > threshold (e.g., +0.5%)
- Optional position scaling by basis depth

## Backtest Results (IC Futures, 2015-2025)

| Metric | Value |
|--------|-------|
| Total Return | 181.63% |
| Annualized Return | 10.23% |
| Annualized Volatility | 25.28% |
| Sharpe Ratio | 0.33 |
| Max Drawdown | -46.95% |
| Benchmark Return | -1.78% |
| **Alpha (Excess Return)** | **12.01%** |
| Information Ratio | 1.36 |

*Note: Uses 242 trading days/year (China market)*

## Configuration

All parameters are managed via `config.toml`:

```toml
[data]
fut_code = "IC"  # IC, IM, or IF

[strategy]
strategy_type = "baseline"  # or "basis_timing"
roll_days_before_expiry = 2
target_leverage = 1.0

[backtest]
start_date = "2015-05-01"
trading_days_per_year = 242  # China market
```

## Dependencies

- Python 3.11+
- polars, pandas, numpy
- matplotlib
- loguru
- pytest (for testing)

## Documentation

- [Design Document](docs/DESIGN.md) - System architecture and class design
- [Backtest Flow](docs/BACKTEST_FLOW.md) - Step-by-step simulation process
- [Examples](examples/) - Interactive Jupyter notebooks

## License

Academic use only.
