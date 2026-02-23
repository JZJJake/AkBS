import akshare as ak
import pandas as pd

def fetch_stock_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetches A-share stock data using akshare.

    Args:
        symbol (str): Stock code (e.g., '600519').
        start_date (str): Start date in 'YYYYMMDD' format.
        end_date (str): End date in 'YYYYMMDD' format.

    Returns:
        pd.DataFrame: DataFrame with columns ['date', 'open', 'high', 'low', 'close', 'volume'].

    Raises:
        Exception: If data fetching fails or input is invalid.
    """
    try:
        # akshare.stock_zh_a_hist requires symbol as a string, e.g., "000001"
        # adjust='qfq' for forward rehabilitation
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

        if df.empty:
            raise ValueError("No data found for the given symbol and date range.")

        # Rename columns
        # Typical columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        rename_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume"
        }

        df = df.rename(columns=rename_map)

        # Select only required columns
        required_columns = ["date", "open", "high", "low", "close", "volume"]
        # Ensure all required columns exist
        if not all(col in df.columns for col in required_columns):
             missing = [col for col in required_columns if col not in df.columns]
             raise ValueError(f"Missing columns in fetched data: {missing}")

        df = df[required_columns]

        return df

    except Exception as e:
        raise e
