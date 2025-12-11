# Backtest Flow Documentation

This document explains the step-by-step flow of the backtest system.

## Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Config    │───>│ DataHandler │───>│  Strategy   │───>│   Engine    │
│  (TOML)     │    │  (Data)     │    │  (Logic)    │    │ (Simulator) │
└─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                                │
                                                                v
                                                         ┌─────────────┐
                                                         │  Analyzer   │
                                                         │  (Report)   │
                                                         └─────────────┘
```

## Step-by-Step Flow

### 1. Configuration Loading

```python
config = load_config("config.toml")
```

The system reads configuration from `config.toml`:
- **data**: Which futures to trade (IC/IM/IF)
- **account**: Initial capital, margin rate, commission
- **strategy**: Strategy type and parameters
- **backtest**: Date range, benchmark name
- **output**: Where to save results

### 2. Data Loading

```python
data_handler = DataHandler.from_processed_data(data_path, fut_code)
```

DataHandler builds the object graph:

```
DataHandler
    ├── EquityIndex (e.g., CSI 500)
    │       └── daily_bars: Dict[date, IndexDailyBar]
    │
    ├── ContractChain
    │       └── contracts: Dict[ts_code, FuturesContract]
    │               └── daily_bars: Dict[date, FuturesDailyBar]
    │
    └── calendar: List[date]
```

### 3. Strategy Initialization

```python
strategy = BaselineRollStrategy(
    contract_chain=data_handler.contract_chain,
    roll_days_before_expiry=2,
    ...
)
```

Strategy receives the ContractChain and stores parameters.

### 4. Backtest Engine Initialization

```python
engine = BacktestEngine(
    data_handler=data_handler,
    strategy=strategy,
    initial_capital=10_000_000.0,
    ...
)
```

Engine creates an empty Account.

### 5. Main Backtest Loop

```python
for trade_date in calendar:
    engine._process_day(trade_date, contracts)
```

For each trading day:

#### 5.1 Get Market Snapshot

```python
snapshot = data_handler.get_snapshot(trade_date)
```

Snapshot contains:
- `index_bar`: Today's index close
- `futures_quotes`: All active contracts' bars today

#### 5.2 Mark-to-Market

```python
daily_pnl = account.mark_to_market(snapshot)
```

For each position:
```
PnL = (today_settle - yesterday_settle) * volume * multiplier
```

The PnL is added to cash (futures daily settlement).

#### 5.3 Strategy Decision

```python
target_positions = strategy.on_bar(snapshot, account)
```

Strategy logic (BaselineRollStrategy):

```
1. Get current holding contract
2. If no holding:
   - Select initial contract (nearby/volume/oi rule)
   - Calculate target volume
3. If holding:
   - Check days_to_expiry <= roll_days_before_expiry
   - If yes: Roll to new contract
   - If no: Maintain position, adjust volume
4. Return Dict[ts_code, target_volume]
```

#### 5.4 Trade Execution

```python
account.rebalance_to_target(target_positions, snapshot, contracts)
```

For each contract:
```
delta = target_volume - current_volume
if delta != 0:
    execute_trade(contract, delta, price)
    deduct_commission()
```

#### 5.5 Record NAV

```python
account.record_nav(trade_date)
```

NAV = equity / initial_capital

### 6. Build Analyzer

```python
analyzer = Analyzer(
    nav_series=account.get_nav_series(),
    benchmark_nav=index.get_nav_series(),
    trade_log=account.trade_log,
    ...
)
```

### 7. Compute Metrics

```python
metrics = analyzer.compute_metrics()
```

Metrics include:
- Annualized return: `(1 + total_return)^(1/n_years) - 1`
- Volatility: `std(daily_returns) * sqrt(242)`
- Sharpe: `(return - rf) / volatility`
- Max drawdown: `min((NAV - peak) / peak)`
- Alpha: `strategy_return - benchmark_return`
- Information ratio: `alpha / tracking_error`

### 8. Save Results

```python
analyzer.save_all(output_dir, run_name)
```

Creates:
```
output/
    run_name/
        report.png      # Comprehensive visual report
        trade_log.csv   # All trades
        nav_series.csv  # Daily NAV values
        metrics.csv     # Performance metrics
        report.txt      # Text summary
```

## Key Concepts

### Futures Contract Rolling

When a contract approaches expiry:

```
Day T-3: IC2401.CFX has 3 days to expiry
         -> No action (roll_days_before_expiry = 2)

Day T-2: IC2401.CFX has 2 days to expiry
         -> Trigger roll
         -> Select IC2402.CFX (next nearby)
         -> Close IC2401, Open IC2402
```

### Basis Calculation

```python
basis = (futures_price - spot_price) / spot_price
```

- Negative basis = discount (futures < spot) -> profitable for long
- Positive basis = premium (futures > spot) -> unprofitable for long

### Mark-to-Market Settlement

Chinese index futures use daily settlement:
- Each day, PnL is realized and added to cash
- Position is re-marked to settlement price
- No unrealized PnL accumulates

```python
# Day 1: Open 10 lots @ 5000
# Day 2: Settle @ 5050
PnL = (5050 - 5000) * 10 * 200 = 100,000
cash += 100,000
last_settle = 5050

# Day 3: Settle @ 5020
PnL = (5020 - 5050) * 10 * 200 = -60,000
cash += -60,000
last_settle = 5020
```

## Sequence Diagram

```
┌──────┐  ┌─────────┐  ┌────────┐  ┌───────┐  ┌────────┐
│Config│  │DataHandler│ │Strategy│  │Account│  │Analyzer│
└──┬───┘  └────┬─────┘  └───┬────┘  └───┬───┘  └───┬────┘
   │           │            │           │          │
   │  load()   │            │           │          │
   │──────────>│            │           │          │
   │           │            │           │          │
   │           │ get_snapshot(date)     │          │
   │           │<───────────────────────│          │
   │           │            │           │          │
   │           │            │ mark_to_market()     │
   │           │            │<──────────│          │
   │           │            │           │          │
   │           │  on_bar(snapshot, account)        │
   │           │───────────>│           │          │
   │           │            │           │          │
   │           │            │ targets   │          │
   │           │            │──────────>│          │
   │           │            │           │          │
   │           │            │ rebalance_to_target()│
   │           │            │<──────────│          │
   │           │            │           │          │
   │           │            │ record_nav()         │
   │           │            │<──────────│          │
   │           │            │           │          │
   │           │            │           │ nav_series
   │           │            │           │─────────>│
   │           │            │           │          │
   │           │            │           │ compute_metrics()
   │           │            │           │<─────────│
   │           │            │           │          │
```
