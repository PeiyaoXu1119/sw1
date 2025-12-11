"""
Data preprocessing script: convert raw data to processed parquet files.
"""
import polars as pl
from pathlib import Path
from loguru import logger
from datetime import datetime


RAW_DATA_PATH = Path("/root/sw1/raw_data")
PROCESSED_DATA_PATH = Path("/root/sw1/processed_data")

# Index mapping: index_code -> (index_name, fut_code)
INDEX_MAPPING = {
    "000905.SH": ("CSI500", "IC"),
    "000852.SH": ("CSI1000", "IM"),
    "000300.SH": ("CSI300", "IF"),
}


def ensure_dirs():
    """Create processed data directories."""
    for subdir in ["futures", "index", "contracts", "margin"]:
        (PROCESSED_DATA_PATH / subdir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory structure at {PROCESSED_DATA_PATH}")


def process_futures_daily():
    """Process IC/IM futures daily bars."""
    for fut_code in ["IC", "IM"]:
        raw_path = RAW_DATA_PATH / "ICIM" / f"{fut_code}.csv"
        if not raw_path.exists():
            logger.warning(f"File not found: {raw_path}")
            continue
        
        df = pl.read_csv(raw_path)
        
        # Convert trade_date to date type
        df = df.with_columns(
            pl.col("trade_date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").alias("trade_date")
        )
        
        # Sort by ts_code and trade_date
        df = df.sort(["ts_code", "trade_date"])
        
        # Select and rename columns
        df = df.select([
            "ts_code",
            "trade_date",
            pl.col("pre_close").alias("pre_close"),
            pl.col("pre_settle").alias("pre_settle"),
            pl.col("open").alias("open"),
            pl.col("high").alias("high"),
            pl.col("low").alias("low"),
            pl.col("close").alias("close"),
            pl.col("settle").alias("settle"),
            pl.col("vol").alias("volume"),
            pl.col("amount").alias("amount"),
            pl.col("oi").alias("open_interest"),
            pl.col("oi_chg").alias("oi_change"),
        ])
        
        output_path = PROCESSED_DATA_PATH / "futures" / f"{fut_code}_daily.parquet"
        df.write_parquet(output_path)
        logger.info(f"Processed {fut_code} futures: {len(df)} rows -> {output_path}")


def process_index_daily():
    """Process index daily bars, split by index code."""
    raw_path = RAW_DATA_PATH / "index" / "all_index_daily.csv"
    
    df = pl.read_csv(raw_path)
    
    # Convert trade_date to date type
    df = df.with_columns(
        pl.col("TRADE_DT").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").alias("trade_date")
    )
    
    # Rename columns
    df = df.select([
        pl.col("S_INFO_WINDCODE").alias("index_code"),
        "trade_date",
        pl.col("S_DQ_OPEN").alias("open"),
        pl.col("S_DQ_HIGH").alias("high"),
        pl.col("S_DQ_LOW").alias("low"),
        pl.col("S_DQ_CLOSE").alias("close"),
    ])
    
    # Split by index code
    for index_code, (index_name, _) in INDEX_MAPPING.items():
        index_df = df.filter(pl.col("index_code") == index_code).sort("trade_date")
        
        output_path = PROCESSED_DATA_PATH / "index" / f"{index_name}_daily.parquet"
        index_df.write_parquet(output_path)
        logger.info(f"Processed {index_name} index: {len(index_df)} rows -> {output_path}")


def process_contract_info():
    """Process contract info, split by fut_code."""
    raw_path = RAW_DATA_PATH / "info" / "info.csv"
    
    df = pl.read_csv(raw_path)
    
    # Filter out continuous contracts (e.g., ICL, ICL1, ICL2, etc.)
    continuous_patterns = ["ICL", "IFL", "IML", "IC.CFX", "IF.CFX", "IM.CFX"]
    
    df = df.filter(
        ~pl.col("ts_code").is_in(continuous_patterns) &
        ~pl.col("ts_code").str.contains("L")  # Filter out all continuous contracts
    )
    
    # Filter only contracts with valid info
    df = df.filter(
        pl.col("multiplier").is_not_null() &
        pl.col("list_date").is_not_null() &
        pl.col("delist_date").is_not_null()
    )
    
    # Convert date columns
    df = df.with_columns([
        pl.col("list_date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").alias("list_date"),
        pl.col("delist_date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").alias("delist_date"),
        pl.col("last_ddate").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").alias("last_ddate"),
    ])
    
    # Select relevant columns
    df = df.select([
        "ts_code",
        "symbol",
        "fut_code",
        pl.col("multiplier").cast(pl.Float64),
        "list_date",
        "delist_date",
        "last_ddate",
        "name",
    ])
    
    # Split by fut_code
    for fut_code in ["IC", "IM", "IF"]:
        fut_df = df.filter(pl.col("fut_code") == fut_code).sort("list_date")
        
        output_path = PROCESSED_DATA_PATH / "contracts" / f"{fut_code}_info.parquet"
        fut_df.write_parquet(output_path)
        logger.info(f"Processed {fut_code} contracts: {len(fut_df)} rows -> {output_path}")


def process_margin_ratio():
    """Process margin ratio history."""
    raw_path = RAW_DATA_PATH / "info" / "infor_margin.csv"
    
    df = pl.read_csv(raw_path)
    
    # Convert trade_date
    df = df.with_columns(
        pl.col("TRADE_DT").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").alias("trade_date")
    )
    
    # Extract fut_code from S_INFO_WINDCODE (e.g., "IC2112.CFE" -> "IC")
    df = df.with_columns(
        pl.col("S_INFO_WINDCODE").str.extract(r"^([A-Z]+)", 1).alias("fut_code")
    )
    
    # Select and rename columns
    df = df.select([
        "fut_code",
        "trade_date",
        pl.col("LONG_MARGIN_RATIO").alias("long_margin_ratio"),
        pl.col("SHORT_MARGIN_RATIO").alias("short_margin_ratio"),
    ])
    
    # For each fut_code and date, take the first margin ratio (they should be the same)
    df = df.group_by(["fut_code", "trade_date"]).agg([
        pl.col("long_margin_ratio").first(),
        pl.col("short_margin_ratio").first(),
    ]).sort(["fut_code", "trade_date"])
    
    output_path = PROCESSED_DATA_PATH / "margin" / "margin_ratio.parquet"
    df.write_parquet(output_path)
    logger.info(f"Processed margin ratio: {len(df)} rows -> {output_path}")


def validate_data():
    """Validate processed data."""
    logger.info("Validating processed data...")
    
    # Check futures data
    for fut_code in ["IC", "IM"]:
        path = PROCESSED_DATA_PATH / "futures" / f"{fut_code}_daily.parquet"
        if path.exists():
            df = pl.read_parquet(path)
            contracts = df["ts_code"].unique().len()
            date_range = f"{df['trade_date'].min()} to {df['trade_date'].max()}"
            logger.info(f"  {fut_code} futures: {contracts} contracts, {len(df)} bars, {date_range}")
    
    # Check index data
    for index_code, (index_name, _) in INDEX_MAPPING.items():
        path = PROCESSED_DATA_PATH / "index" / f"{index_name}_daily.parquet"
        if path.exists():
            df = pl.read_parquet(path)
            date_range = f"{df['trade_date'].min()} to {df['trade_date'].max()}"
            logger.info(f"  {index_name} index: {len(df)} bars, {date_range}")
    
    # Check contract info
    for fut_code in ["IC", "IM", "IF"]:
        path = PROCESSED_DATA_PATH / "contracts" / f"{fut_code}_info.parquet"
        if path.exists():
            df = pl.read_parquet(path)
            logger.info(f"  {fut_code} contracts: {len(df)} contracts")


def main():
    logger.info("Starting data preprocessing...")
    
    ensure_dirs()
    process_futures_daily()
    process_index_daily()
    process_contract_info()
    process_margin_ratio()
    validate_data()
    
    logger.info("Data preprocessing completed!")


if __name__ == "__main__":
    main()
