import akshare as ak
import pandas as pd
import numpy as np

class DataFetcher:
    @staticmethod
    def fetch_data(symbol: str, start_date: str = '20230101', end_date: str = '20241231') -> pd.DataFrame:
        """
        Fetches A-share stock data using akshare.
        """
        try:
            # akshare.stock_zh_a_hist requires symbol as a string
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

            if df.empty:
                raise ValueError("No data found for the given symbol and date range.")

            rename_map = {
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume"
            }
            df = df.rename(columns=rename_map)

            # Ensure columns exist
            required = ["date", "open", "high", "low", "close", "volume"]
            df = df[[c for c in required if c in df.columns]]

            # Convert date to string YYYY-MM-DD if not already
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            return df
        except Exception as e:
            # Return empty DataFrame on failure or re-raise?
            # Raising lets the caller handle it.
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates MA20, VOL_MA5, MACD(12,26,9), KDJ(9,3,3).
        """
        if df.empty:
            return df

        df = df.copy()

        # Ensure numeric
        cols = ['open', 'high', 'low', 'close', 'volume']
        for c in cols:
            df[c] = pd.to_numeric(df[c])

        # --- MA20 ---
        df['ma20'] = df['close'].rolling(window=20).mean()

        # --- VOL_MA5 ---
        df['vol_ma5'] = df['volume'].rolling(window=5).mean()

        # --- MACD (12, 26, 9) ---
        # DIFF = EMA(12) - EMA(26)
        # DEA = EMA(DIFF, 9)
        # MACD = 2 * (DIFF - DEA)
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['diff'] = ema_12 - ema_26
        df['dea'] = df['diff'].ewm(span=9, adjust=False).mean()
        df['macd'] = (df['diff'] - df['dea']) * 2

        # --- KDJ (9, 3, 3) ---
        # RSV = (Close - Lowest_Low_9) / (Highest_High_9 - Lowest_Low_9) * 100
        low_9 = df['low'].rolling(window=9, min_periods=1).min()
        high_9 = df['high'].rolling(window=9, min_periods=1).max()

        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
        rsv = rsv.replace([np.inf, -np.inf], np.nan).fillna(50)

        # K, D calculation with alpha=1/3
        k_values = []
        d_values = []
        k_prev = 50.0
        d_prev = 50.0

        for r in rsv:
            if pd.isna(r):
                k_values.append(50.0)
                d_values.append(50.0)
                continue

            k_curr = (2/3) * k_prev + (1/3) * r
            d_curr = (2/3) * d_prev + (1/3) * k_curr

            k_values.append(k_curr)
            d_values.append(d_curr)

            k_prev = k_curr
            d_prev = d_curr

        df['k'] = k_values
        df['d'] = d_values
        df['j'] = 3 * df['k'] - 2 * df['d']

        return df
