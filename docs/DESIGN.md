# 股指期货指数增强策略回测系统设计文档

## 一、数据结构分析

### 1.1 原始数据概览

| 文件 | 说明 | 关键字段 |
|------|------|----------|
| `ICIM/IC.csv` | IC期货日行情 | ts_code, trade_date, settle, vol, oi |
| `ICIM/IM.csv` | IM期货日行情 | 同上 |
| `index/all_index_daily.csv` | 指数日行情 | S_INFO_WINDCODE, TRADE_DT, S_DQ_CLOSE |
| `info/info.csv` | 合约基本信息 | ts_code, fut_code, multiplier, list_date, delist_date, last_ddate |
| `info/infor_margin.csv` | 保证金比例 | S_INFO_WINDCODE, TRADE_DT, LONG_MARGIN_RATIO |

### 1.2 指数与合约对应关系

| 指数代码 | 指数名称 | 期货代码 | 期货名称 | 乘数 |
|----------|----------|----------|----------|------|
| 000905.SH | 中证500 | IC | 中证500期货 | 200 |
| 000852.SH | 中证1000 | IM | 中证1000期货 | 200 |
| 000300.SH | 沪深300 | IF | 沪深300期货 | 300 |

### 1.3 数据处理目标

将原始数据处理为以下结构:

```
processed_data/
├── futures/
│   ├── IC_daily.parquet      # IC合约日行情
│   └── IM_daily.parquet      # IM合约日行情
├── index/
│   ├── CSI500_daily.parquet  # 中证500指数
│   └── CSI1000_daily.parquet # 中证1000指数
├── contracts/
│   ├── IC_info.parquet       # IC合约基本信息
│   └── IM_info.parquet       # IM合约基本信息
└── margin/
    └── margin_ratio.parquet  # 保证金比例历史
```

---

## 二、系统架构设计

### 2.1 五层对象体系

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 5: Backtest & Analytics                                  │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │  BacktestEngine │  │    Analyzer     │                       │
│  └────────┬────────┘  └────────┬────────┘                       │
│           │                    │                                │
├───────────┼────────────────────┼────────────────────────────────┤
│  Layer 4: Strategy             │                                │
│  ┌─────────────────┐  ┌────────┴────────┐                       │
│  │ BaselineRoll    │  │ BasisTiming     │                       │
│  │ Strategy        │  │ Strategy        │                       │
│  └────────┬────────┘  └────────┬────────┘                       │
│           │                    │                                │
│           └──────────┬─────────┘                                │
│                      ▼                                          │
│           ┌─────────────────┐                                   │
│           │ <<abstract>>    │                                   │
│           │   Strategy      │                                   │
│           └─────────────────┘                                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Account & Portfolio                                   │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │    Account      │◇─│    Position     │                       │
│  │                 │  │                 │                       │
│  │ - cash          │  │ - contract      │                       │
│  │ - positions     │  │ - volume        │                       │
│  │ - nav_history   │  │ - last_settle   │                       │
│  └─────────────────┘  └────────┬────────┘                       │
│                                │                                │
├────────────────────────────────┼────────────────────────────────┤
│  Layer 2: Data & Snapshot      │                                │
│  ┌─────────────────┐  ┌────────┴────────┐                       │
│  │   DataHandler   │──│ MarketSnapshot  │                       │
│  │                 │  │                 │                       │
│  │ - index         │  │ - trade_date    │                       │
│  │ - contract_chain│  │ - index_bar     │                       │
│  │ - calendar      │  │ - futures_quotes│                       │
│  └────────┬────────┘  └─────────────────┘                       │
│           │                                                     │
├───────────┼─────────────────────────────────────────────────────┤
│  Layer 1: Domain / Instrument                                   │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐        ┌─────────────────┐                 │
│  │  ContractChain  │◇───────│ FuturesContract │                 │
│  │                 │   *    │                 │                 │
│  │ - fut_code      │        │ - ts_code       │                 │
│  │ - contracts     │        │ - multiplier    │                 │
│  └────────┬────────┘        │ - list_date     │                 │
│           │                 │ - delist_date   │                 │
│           ▼                 │ - daily_bars    │                 │
│  ┌─────────────────┐        └────────┬────────┘                 │
│  │   EquityIndex   │                 │                          │
│  │                 │                 ▼                          │
│  │ - index_code    │        ┌─────────────────┐                 │
│  │ - daily_bars    │        │ FuturesDailyBar │                 │
│  └────────┬────────┘        │ (dataclass)     │                 │
│           │                 └─────────────────┘                 │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │  IndexDailyBar  │                                            │
│  │  (dataclass)    │                                            │
│  └─────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、类设计详细说明

### 3.1 Layer 1: Domain Layer (标的与合约层)

#### IndexDailyBar (数据类)
```python
@dataclass
class IndexDailyBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
```

#### FuturesDailyBar (数据类)
```python
@dataclass
class FuturesDailyBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    settle: float          # 结算价 - 核心字段
    pre_settle: float      # 昨结算价
    vol: float             # 成交量(手)
    amount: float          # 成交金额(万元)
    oi: float              # 持仓量(手)
    oi_chg: float          # 持仓量变化
```

#### EquityIndex (现货指数)
```python
class EquityIndex:
    index_code: str        # e.g., "000905.SH"
    name: str              # e.g., "中证500"
    daily_bars: Dict[date, IndexDailyBar]
    
    def get_bar(trade_date) -> IndexDailyBar | None
    def get_close(trade_date) -> float
    def get_return_series(start, end) -> pd.Series
```

#### FuturesContract (期货合约 - 核心)
```python
class FuturesContract:
    # 元数据
    ts_code: str           # e.g., "IC1505.CFX"
    fut_code: str          # e.g., "IC"
    multiplier: float      # e.g., 200.0
    list_date: date        # 上市日
    delist_date: date      # 最后交易日
    last_ddate: date       # 交割结算日
    
    # 行情数据
    daily_bars: Dict[date, FuturesDailyBar]
    
    def is_listed(trade_date) -> bool
    def is_expired(trade_date) -> bool
    def is_tradable(trade_date) -> bool
    def get_bar(trade_date) -> FuturesDailyBar | None
    def get_price(trade_date, field='settle') -> float
    def days_to_expiry(trade_date) -> int
```

#### ContractChain (合约链)
```python
class ContractChain:
    index: EquityIndex
    fut_code: str          # "IC" / "IM"
    contracts: Dict[str, FuturesContract]
    
    def get_contract(ts_code) -> FuturesContract
    def get_active_contracts(trade_date) -> List[FuturesContract]
    def get_nearby_contracts(trade_date, k=2) -> List[FuturesContract]
    def get_main_contract(trade_date, rule='volume') -> FuturesContract
    def get_chain_snapshot(trade_date) -> Dict[str, FuturesDailyBar]
```

### 3.2 Layer 2: Data Layer (数据与快照层)

#### MarketSnapshot (市场快照)
```python
class MarketSnapshot:
    trade_date: date
    index_bar: IndexDailyBar
    futures_quotes: Dict[str, FuturesDailyBar]
    
    def get_contract_bar(ts_code) -> FuturesDailyBar | None
    def get_basis(ts_code) -> float  # (F - S) / S
```

#### DataHandler (数据处理器)
```python
class DataHandler:
    index: EquityIndex
    contract_chain: ContractChain
    calendar: List[date]
    margin_rates: Dict[date, float]  # 历史保证金比例
    
    @classmethod
    def from_processed_data(data_path, fut_code) -> DataHandler
    
    def get_trading_calendar(start, end) -> List[date]
    def get_snapshot(trade_date) -> MarketSnapshot
    def get_contract_chain() -> ContractChain
    def get_index() -> EquityIndex
    def get_margin_rate(trade_date) -> float
```

### 3.3 Layer 3: Account Layer (账户与组合层)

#### Position (持仓)
```python
class Position:
    contract: FuturesContract
    volume: int            # 正=多头, 负=空头
    entry_price: float     # 开仓均价
    last_settle: float     # 上日结算价 (用于盯市)
    
    def mark_to_market(trade_date) -> float  # 返回盯市盈亏
    def notional(trade_date) -> float        # 名义价值
    def days_to_expiry(trade_date) -> int
```

#### Account (账户)
```python
class Account:
    initial_capital: float
    cash: float
    margin_rate: float     # 默认保证金比例
    positions: Dict[str, Position]  # ts_code -> Position
    nav_history: Dict[date, float]
    trade_log: List[TradeRecord]
    
    def mark_to_market(snapshot) -> float
    def required_margin(snapshot) -> float
    def available_margin(snapshot) -> float
    def rebalance_to_target(target_positions, snapshot)
    def record_nav(trade_date)
    def get_nav_series() -> pd.Series
```

### 3.4 Layer 4: Strategy Layer (策略层)

#### Strategy (抽象策略)
```python
class Strategy(ABC):
    contract_chain: ContractChain
    
    @abstractmethod
    def on_bar(snapshot, account) -> Dict[str, int]  # ts_code -> target_volume
```

#### BaselineRollStrategy (基线换月策略)
```python
class BaselineRollStrategy(Strategy):
    roll_days_before_expiry: int = 2  # 到期前N天换月
    contract_selection_rule: str = 'nearby'  # 'nearby' / 'volume' / 'oi'
    
    def on_bar(snapshot, account) -> Dict[str, int]
    def _should_roll(current_contract, trade_date) -> bool
    def _select_new_contract(snapshot) -> FuturesContract
    def _calculate_target_volume(account, contract, snapshot) -> int
```

#### BasisTimingStrategy (基差择时策略)
```python
class BasisTimingStrategy(BaselineRollStrategy):
    basis_entry_threshold: float    # 开仓阈值 (如 -3%)
    basis_exit_threshold: float     # 平仓阈值 (如 0%)
    lookback_window: int            # 基差分位数回看窗口
    
    def on_bar(snapshot, account) -> Dict[str, int]
    def _calculate_basis(contract, snapshot) -> float
    def _get_basis_percentile(basis, lookback) -> float
```

### 3.5 Layer 5: Backtest Layer (回测与分析层)

#### BacktestEngine (回测引擎)
```python
class BacktestEngine:
    data_handler: DataHandler
    strategy: Strategy
    account: Account
    analyzer: Analyzer
    
    def run(start_date, end_date) -> BacktestResult
    def _process_day(trade_date)
```

#### Analyzer (分析器)
```python
class Analyzer:
    nav_history: pd.Series
    benchmark_nav: pd.Series
    trade_log: List[TradeRecord]
    
    def compute_metrics() -> Dict[str, float]
    # - annualized_return
    # - annualized_volatility
    # - sharpe_ratio
    # - max_drawdown
    # - alpha (超额收益)
    # - beta
    # - win_rate
    
    def plot_nav_comparison()
    def plot_drawdown()
    def generate_report() -> str
```

---

## 四、项目目录结构

```
sw1/
├── docs/
│   └── DESIGN.md              # 设计文档
├── raw_data/                  # 原始数据 (已存在)
├── processed_data/            # 处理后数据
│   ├── futures/
│   ├── index/
│   ├── contracts/
│   └── margin/
├── src/
│   ├── __init__.py
│   ├── domain/                # Layer 1: Domain Layer
│   │   ├── __init__.py
│   │   ├── bars.py            # IndexDailyBar, FuturesDailyBar
│   │   ├── index.py           # EquityIndex
│   │   ├── contract.py        # FuturesContract
│   │   └── chain.py           # ContractChain
│   ├── data/                  # Layer 2: Data Layer
│   │   ├── __init__.py
│   │   ├── handler.py         # DataHandler
│   │   ├── snapshot.py        # MarketSnapshot
│   │   └── processor.py       # 数据预处理脚本
│   ├── account/               # Layer 3: Account Layer
│   │   ├── __init__.py
│   │   ├── position.py        # Position
│   │   └── account.py         # Account
│   ├── strategy/              # Layer 4: Strategy Layer
│   │   ├── __init__.py
│   │   ├── base.py            # Strategy ABC
│   │   ├── baseline_roll.py   # BaselineRollStrategy
│   │   └── basis_timing.py    # BasisTimingStrategy
│   └── backtest/              # Layer 5: Backtest Layer
│       ├── __init__.py
│       ├── engine.py          # BacktestEngine
│       └── analyzer.py        # Analyzer
├── tests/                     # 单元测试
│   ├── test_domain.py
│   ├── test_data.py
│   ├── test_account.py
│   ├── test_strategy.py
│   └── test_backtest.py
├── notebooks/                 # Jupyter Notebooks
│   └── analysis.ipynb         # 回测分析
├── scripts/
│   └── preprocess_data.py     # 数据预处理脚本
└── main.py                    # 主入口
```

---

## 五、关键流程说明

### 5.1 回测主流程

```
for trade_date in trading_calendar:
    1. snapshot = data_handler.get_snapshot(trade_date)
    2. daily_pnl = account.mark_to_market(snapshot)  # 盯市
    3. target_positions = strategy.on_bar(snapshot, account)
    4. account.rebalance_to_target(target_positions, snapshot)
    5. account.record_nav(trade_date)
    6. analyzer.record(trade_date, snapshot, account)
```

### 5.2 换月逻辑 (BaselineRollStrategy)

```
1. 获取当前持仓的合约
2. 检查 days_to_expiry <= roll_days_before_expiry?
   - 是: 触发换月
     a. 选择新合约 (按 nearby/volume/oi 规则)
     b. 目标仓位: 旧合约 -> 0, 新合约 -> 计算手数
   - 否: 保持当前合约, 仅调整手数
3. 返回 target_positions: Dict[ts_code, volume]
```

### 5.3 基差择时逻辑 (BasisTimingStrategy)

```
1. 计算当前合约基差: basis = (F - S) / S
2. 根据历史分位数判断:
   - basis < entry_threshold: 贴水较深, 满仓
   - basis > exit_threshold: 贴水收窄/升水, 减仓
   - 中间状态: 维持现有仓位
3. 叠加换月逻辑
```

---

## 六、性能指标定义

| 指标 | 公式 |
|------|------|
| 年化收益 | $(NAV_{end}/NAV_{start})^{252/n} - 1$ |
| 年化波动 | $std(daily\_return) \times \sqrt{252}$ |
| Sharpe | $(R - R_f) / \sigma$ |
| 最大回撤 | $max(1 - NAV_t / NAV_{peak})$ |
| Alpha | $R_{strategy} - R_{benchmark}$ (简化版) |
| 信息比率 | $\alpha / TE$ |
