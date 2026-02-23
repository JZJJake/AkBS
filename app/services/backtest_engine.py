import pandas as pd
import numpy as np
from app.services.data_fetcher import DataFetcher

class BacktestEngine:
    """
    Backtesting Engine for A-share strategies.
    Uses DataFetcher for indicator calculation.
    """

    def __init__(self, initial_capital=100000.0, commission_rate=0.0003): # Updated default commission to typical A-share
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate

    def run_backtest(self, df: pd.DataFrame, symbol: str) -> dict:
        """
        Executes the backtest logic.

        Args:
            df (pd.DataFrame): Historical data.
            symbol (str): Stock symbol.

        Returns:
            dict: Contains 'stats' dictionary and 'equity_curve' DataFrame.
        """
        # 1. Filter: specific logic for 68xxxx stocks
        if symbol.startswith("68"):
            equity_curve = pd.DataFrame({'date': df['date'], 'total_value': self.initial_capital})
            stats = {
                'total_return': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'max_drawdown': 0.0
            }
            return {'stats': stats, 'equity_curve': equity_curve, 'trades': []}

        # Calculate indicators using Shared Service
        # Assuming df already has basic columns.
        # Check if indicators are already there, if not calculate them.
        if 'macd' not in df.columns:
            df = DataFetcher.calculate_indicators(df)

        # Initialize state variables
        balance = self.initial_capital
        position = 0  # Number of shares held
        equity_curve = []
        trades = []

        # We need access to previous day's data
        # Start index: Need i-2 for "day before yesterday" logic in strategy
        start_index = 2

        # Ensure df index is RangeIndex for integer access
        df = df.reset_index(drop=True)

        for i in range(len(df)):
            current_date = df.loc[i, 'date']
            current_close = df.loc[i, 'close']

            # Logic uses indicators, so need to skip if indicators are NaN at start
            # But the loop logic handles i < start_index.
            # Note: MACD/KDJ might be NaN for first few rows.
            # We should check for NaN indicators before trading.

            current_total_value = balance + (position * current_close)

            if i < start_index:
                equity_curve.append({'date': current_date, 'total_value': current_total_value})
                continue

            # Get indicators
            try:
                dea_curr = df.loc[i, 'dea']
                dea_prev = df.loc[i-1, 'dea']
                dea_prev2 = df.loc[i-2, 'dea']

                j_curr = df.loc[i, 'j']
                j_prev = df.loc[i-1, 'j']
                j_prev2 = df.loc[i-2, 'j']

                # If any indicator is NaN, skip trading
                if pd.isna(dea_curr) or pd.isna(dea_prev) or pd.isna(dea_prev2) or \
                   pd.isna(j_curr) or pd.isna(j_prev) or pd.isna(j_prev2):
                    equity_curve.append({'date': current_date, 'total_value': current_total_value})
                    continue

            except KeyError:
                 # Should not happen if calculate_indicators worked
                equity_curve.append({'date': current_date, 'total_value': current_total_value})
                continue

            # --- Trading Logic ---
            action_taken = False

            if position > 0:
                # --- Sell Logic ---
                # Retrieve last buy price
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
                    revenue = position * current_close
                    commission = revenue * self.commission_rate
                    balance += (revenue - commission)

                    trades[-1]['sell_date'] = current_date
                    trades[-1]['sell_price'] = current_close
                    trades[-1]['sell_reason'] = sell_reason
                    trades[-1]['profit'] = (current_close - buy_price) * position - commission - trades[-1]['commission']

                    position = 0
                    action_taken = True

            elif position == 0:
                # --- Buy Logic ---
                # KDJ Turnaround: J_prev <= 80 AND J_curr > J_prev AND J_prev < J_prev2
                # V-shape bottom for J
                kdj_buy = (j_prev <= 80) and (j_curr > j_prev) and (j_prev < j_prev2)

                # MACD Turnaround: DEA_curr > DEA_prev AND DEA_prev < DEA_prev2
                # V-shape bottom for DEA
                macd_buy = (dea_curr > dea_prev) and (dea_prev < dea_prev2)

                if kdj_buy or macd_buy:
                    # Calculate max shares
                    cost_per_share = current_close * (1 + self.commission_rate)
                    if balance >= cost_per_share * 100:
                        max_shares = int(balance / cost_per_share // 100) * 100

                        if max_shares > 0:
                            cost = max_shares * current_close
                            commission = cost * self.commission_rate
                            balance -= (cost + commission)
                            position = max_shares

                            trades.append({
                                'buy_date': current_date,
                                'price': current_close,
                                'commission': commission,
                                'signal': 'KDJ' if kdj_buy else 'MACD'
                            })
                            action_taken = True

            # Update equity
            current_total_value = balance + (position * current_close)
            equity_curve.append({'date': current_date, 'total_value': current_total_value})

        equity_df = pd.DataFrame(equity_curve)
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

        total_return = (final_value - initial_value) / initial_value
        total_trades = len([t for t in trades if 'sell_date' in t])

        winning_trades = len([t for t in trades if 'sell_date' in t and t['profit'] > 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        equity_df['peak'] = equity_df['total_value'].cummax()
        equity_df['drawdown'] = (equity_df['total_value'] - equity_df['peak']) / equity_df['peak']
        max_drawdown = equity_df['drawdown'].min()

        return {
            'total_return': total_return,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown
        }
