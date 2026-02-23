import pandas as pd
import numpy as np

class BacktestEngine:
    """
    Backtesting Engine for A-share strategies.

    Attributes:
        initial_capital (float): Starting capital for the backtest.
        commission_rate (float): Commission rate per trade (e.g., 0.0003 for 0.03%).
    """

    def __init__(self, initial_capital=100000.0, commission_rate=0.0):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates MACD and KDJ indicators based on the provided DataFrame.

        Args:
            df (pd.DataFrame): DataFrame with columns ['date', 'open', 'high', 'low', 'close', 'volume'].

        Returns:
            pd.DataFrame: DataFrame with added indicator columns.
        """
        # Ensure data is sorted by date
        if 'date' in df.columns:
            df = df.sort_values('date').reset_index(drop=True)

        # --- MACD (10, 25, 7) ---
        # DIFF = EMA(10) - EMA(25)
        # DEA = EMA(DIFF, 7)
        # Note: adjust=False corresponds to the recursive formula used in most technical analysis software
        ema_10 = df['close'].ewm(span=10, adjust=False).mean()
        ema_25 = df['close'].ewm(span=25, adjust=False).mean()
        df['diff'] = ema_10 - ema_25
        df['dea'] = df['diff'].ewm(span=7, adjust=False).mean()
        df['macd'] = (df['diff'] - df['dea']) * 2 # Standard MACD histogram formula, though not explicitly asked for, good to have

        # --- KDJ (9, 3, 3) ---
        # RSV = (Close - Lowest_Low_9) / (Highest_High_9 - Lowest_Low_9) * 100
        # Use min_periods=1 to match Tongdaxin logic for initial data
        low_9 = df['low'].rolling(window=9, min_periods=1).min()
        high_9 = df['high'].rolling(window=9, min_periods=1).max()

        # Handle division by zero if high_9 == low_9 (e.g., flat limit up/down or initial single data point)
        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100

        # Replace inf/-inf with NaN, then fill NaN with 50 (neutral value)
        rsv = rsv.replace([np.inf, -np.inf], np.nan).fillna(50)

        # Initialize K, D, J columns
        # We need to iterate to calculate K and D recursively with the specific alpha=1/3
        # K_t = 2/3 * K_{t-1} + 1/3 * RSV_t
        # D_t = 2/3 * D_{t-1} + 1/3 * K_t
        # Initial values for K and D are 50

        k_values = []
        d_values = []

        k_prev = 50.0
        d_prev = 50.0

        for r in rsv:
            if pd.isna(r):
                # Before window is full, we can either skip or use default
                # Here we keep default 50 until valid RSV appears
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

    def run_backtest(self, df: pd.DataFrame, symbol: str) -> dict:
        """
        Executes the backtest logic.

        Args:
            df (pd.DataFrame): Historical data.
            symbol (str): Stock symbol.

        Returns:
            dict: Contains 'stats' dictionary and 'equity_curve' DataFrame.
        """

        # 1. 前置过滤：如果是 68 开头（科创板），直接返回空结果
        if symbol.startswith("68"):
            equity_curve = pd.DataFrame({'date': df['date'], 'total_value': self.initial_capital})
            stats = {
                'total_return': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'max_drawdown': 0.0
            }
            return {'stats': stats, 'equity_curve': equity_curve}

        # Calculate indicators
        df = self.calculate_indicators(df)

        # Initialize state variables
        balance = self.initial_capital
        position = 0  # Number of shares held
        equity_curve = []
        trades = []

        # Iterate through the DataFrame
        # We need access to previous day's data, so we start from index 2 (need i-2 for "day before yesterday")
        # However, KDJ/MACD calculation needs some warmup, let's start after the longest window (25)
        # But user didn't specify warmup period skipping, so we start as early as possible (index 2)
        # to ensure previous indicators exist.

        start_index = 2

        for i in range(len(df)):
            current_date = df.loc[i, 'date']
            current_close = df.loc[i, 'close']
            current_total_value = balance + (position * current_close)

            # Record equity before potential trades today (using yesterday's position close value)
            # Or usually equity is recorded at the end of the day. Let's record at end of loop.

            if i < start_index:
                equity_curve.append({'date': current_date, 'total_value': current_total_value})
                continue

            # Get current and previous indicators
            # Today: i, Yesterday: i-1, Day before: i-2

            # MACD
            dea_curr = df.loc[i, 'dea']
            dea_prev = df.loc[i-1, 'dea']
            dea_prev2 = df.loc[i-2, 'dea']

            # KDJ
            j_curr = df.loc[i, 'j']
            j_prev = df.loc[i-1, 'j']
            j_prev2 = df.loc[i-2, 'j']

            # --- Trading Logic ---

            action_taken = False

            if position > 0:
                # --- Sell Logic (Stop Loss / Take Profit) ---
                # Check conditions in order: Stop Loss > Price TP > Indicator TP

                # Get buy price of current position (assuming full position bought at once or average price)
                # Since we always buy full capital, we can track the last buy price.
                # If we had multiple buys, we would need average cost.
                # Simplification: Only one active trade at a time.
                buy_price = trades[-1]['price'] if trades else 0.0

                sell_signal = False
                sell_reason = ""

                # 1. Stop Loss: Close <= Buy Price * 0.95
                if current_close <= buy_price * 0.95:
                    sell_signal = True
                    sell_reason = "Stop Loss"

                # 2. Take Profit (Price): Close >= Buy Price * 1.15
                elif current_close >= buy_price * 1.15:
                    sell_signal = True
                    sell_reason = "Take Profit (Price)"

                # 3. Take Profit (MACD Slope): (DEA_curr - DEA_prev) < (DEA_prev - DEA_prev2)
                # i.e., Slope is decreasing
                elif (dea_curr - dea_prev) < (dea_prev - dea_prev2):
                    sell_signal = True
                    sell_reason = "Take Profit (MACD Slope)"

                if sell_signal:
                    # Execute Sell
                    revenue = position * current_close
                    commission = revenue * self.commission_rate
                    balance += (revenue - commission)

                    trades[-1]['sell_date'] = current_date
                    trades[-1]['sell_price'] = current_close
                    trades[-1]['sell_reason'] = sell_reason
                    trades[-1]['profit'] = (current_close - buy_price) * position - commission - trades[-1]['commission'] # approximate profit

                    position = 0
                    action_taken = True

            elif position == 0:
                # --- Buy Logic ---
                # KDJ Turnaround: J_prev <= 80 AND J_curr > J_prev AND J_prev < J_prev2
                # Note: "J_prev < J_prev2" means J was falling, now rising (Turnaround/V-shape at bottom?)
                # Wait, "J_curr > J_prev" means rising. "J_prev < J_prev2" means yesterday was lower than day before.
                # So yes, V-shape bottom for J.

                kdj_buy = (j_prev <= 80) and (j_curr > j_prev) and (j_prev < j_prev2)

                # MACD Turnaround: DEA_curr > DEA_prev AND DEA_prev < DEA_prev2
                # V-shape bottom for DEA
                macd_buy = (dea_curr > dea_prev) and (dea_prev < dea_prev2)

                if kdj_buy or macd_buy:
                    # Execute Buy
                    # Calculate max shares we can buy
                    # Cost = Shares * Price * (1 + commission_rate) <= Balance
                    # Shares <= Balance / (Price * (1 + comm))

                    cost_per_share = current_close * (1 + self.commission_rate)
                    if balance >= cost_per_share * 100: # Assuming min 100 shares, standard A-share lot
                         # Calculate max lots of 100
                        max_shares = int(balance / cost_per_share // 100) * 100

                        if max_shares > 0:
                            cost = max_shares * current_close
                            commission = cost * self.commission_rate
                            balance -= (cost + commission)
                            position = max_shares

                            trades.append({
                                'buy_date': current_date,
                                'price': current_close, # Buy Price
                                'commission': commission,
                                'signal': 'KDJ' if kdj_buy else 'MACD'
                            })
                            action_taken = True

            # Update equity for today
            current_total_value = balance + (position * current_close)
            equity_curve.append({'date': current_date, 'total_value': current_total_value})

        # Create DataFrames
        equity_df = pd.DataFrame(equity_curve)

        # Calculate Stats
        stats = self.calculate_stats(trades, equity_df)

        return {'stats': stats, 'equity_curve': equity_df, 'trades': trades}

    def calculate_stats(self, trades: list, equity_df: pd.DataFrame) -> dict:
        """
        Calculates performance statistics.
        """
        if equity_df.empty:
             return {
                'total_return': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'max_drawdown': 0.0
            }

        initial_value = equity_df.iloc[0]['total_value']
        final_value = equity_df.iloc[-1]['total_value']

        # Total Return
        total_return = (final_value - initial_value) / initial_value

        # Total Trades
        total_trades = len([t for t in trades if 'sell_date' in t])

        # Win Rate
        winning_trades = len([t for t in trades if 'sell_date' in t and t['profit'] > 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        # Max Drawdown
        # Calculate daily peak
        equity_df['peak'] = equity_df['total_value'].cummax()
        equity_df['drawdown'] = (equity_df['total_value'] - equity_df['peak']) / equity_df['peak']
        max_drawdown = equity_df['drawdown'].min() # This will be negative

        return {
            'total_return': total_return,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown
        }

if __name__ == '__main__':
    # Simple manual test
    # Create mock data
    dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
    # Random price data with some trend
    prices = [100 + i + (i%5)*2 for i in range(50)]

    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p+5 for p in prices],
        'low': [p-5 for p in prices],
        'close': prices,
        'volume': [1000] * 50
    })

    engine = BacktestEngine()
    result = engine.run_backtest(df, '600000')
    print("Stats:", result['stats'])
    print("Equity Head:", result['equity_curve'].head())
