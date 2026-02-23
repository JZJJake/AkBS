from flask import Flask, render_template, request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
import io
import base64
import numpy as np
import pandas as pd
from data_loader import fetch_stock_data
from backtest_engine import BacktestEngine

# Set Chinese font for Windows compatibility
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run_backtest', methods=['POST'])
def run_backtest():
    try:
        symbol = request.form.get('symbol')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        if not symbol or not start_date or not end_date:
            return render_template('index.html', error_message='缺少必填字段')

        df = pd.DataFrame()
        try:
            df = fetch_stock_data(symbol, start_date, end_date)
        except Exception as e:
            return render_template('index.html', error_message=f'获取数据失败: {str(e)}')

        # Run Backtest
        engine = BacktestEngine(commission_rate=0.0005)
        results = engine.run_backtest(df, symbol)

        stats = results['stats']
        equity_curve = results['equity_curve']
        trades = results.get('trades', [])

        plot_url = None
        if not equity_curve.empty:
            # 1. Merge df and equity_curve to align dates
            # df has 'date' column (string or timestamp), equity_curve has 'date' column
            # Convert both to datetime to be safe
            df['date'] = pd.to_datetime(df['date'])
            equity_curve['date'] = pd.to_datetime(equity_curve['date'])

            # Merge: left join on date
            plot_df = pd.merge(df, equity_curve[['date', 'total_value']], on='date', how='left')

            # Fill initial NaN values in total_value with initial_capital
            # (BacktestEngine starts with initial_capital)
            plot_df['total_value'] = plot_df['total_value'].ffill().fillna(engine.initial_capital)

            # Set index for mplfinance
            plot_df.set_index('date', inplace=True)

            # 2. Prepare Signals
            # Create list of NaNs
            buy_signals = [np.nan] * len(plot_df)
            sell_signals = [np.nan] * len(plot_df)

            for trade in trades:
                if 'buy_date' in trade:
                    buy_date = pd.to_datetime(trade['buy_date'])
                    # Check if date exists in plot_df index
                    if buy_date in plot_df.index:
                        # Get integer location
                        idx = plot_df.index.get_loc(buy_date)
                        # Handle potential duplicate index (unlikely for daily data but safe to check)
                        if isinstance(idx, int):
                            low_val = plot_df.iloc[idx]['low']
                            buy_signals[idx] = low_val * 0.98
                        else:
                            # If slice/array, take first
                            low_val = plot_df.iloc[idx[0]]['low']
                            buy_signals[idx[0]] = low_val * 0.98

                if 'sell_date' in trade:
                    sell_date = pd.to_datetime(trade['sell_date'])
                    if sell_date in plot_df.index:
                        idx = plot_df.index.get_loc(sell_date)
                        if isinstance(idx, int):
                            high_val = plot_df.iloc[idx]['high']
                            sell_signals[idx] = high_val * 1.02
                        else:
                            high_val = plot_df.iloc[idx[0]]['high']
                            sell_signals[idx[0]] = high_val * 1.02

            # 3. Create AddPlots
            ap = []

            # Buy Signals (Panel 0)
            # Check if any non-nan
            has_buys = not np.isnan(buy_signals).all()
            if has_buys:
                ap.append(mpf.make_addplot(buy_signals, type='scatter', markersize=100, marker='^', color='r', panel=0))

            # Sell Signals (Panel 0)
            has_sells = not np.isnan(sell_signals).all()
            if has_sells:
                ap.append(mpf.make_addplot(sell_signals, type='scatter', markersize=100, marker='v', color='g', panel=0))

            # Equity Curve (Panel 1)
            # Use 'total_value' column
            # Note: panel=1 puts it below main chart (panel=0)
            ap.append(mpf.make_addplot(plot_df['total_value'], panel=1, color='b', ylabel='资金权益'))

            # 4. Create Style
            # A-share: Up=Red, Down=Green
            mc = mpf.make_marketcolors(up='r', down='g', edge='inherit', wick='inherit', volume='in')
            s = mpf.make_mpf_style(marketcolors=mc)

            # 5. Plot
            # Use returnfig=True to get figure object
            # figratio controls aspect ratio, panel_ratios controls relative height
            fig, axlist = mpf.plot(plot_df,
                     type='candle',
                     addplot=ap,
                     figratio=(10, 8),
                     panel_ratios=(2, 1),
                     style=s,
                     title='股票K线及买卖点标注',
                     ylabel='价格',
                     datetime_format='%Y-%m-%d',
                     returnfig=True)

            # Save to BytesIO
            img = io.BytesIO()
            fig.savefig(img, format='png', bbox_inches='tight')
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode('utf-8')
            plt.close(fig)

        return render_template('result.html', stats=stats, plot_url=plot_url)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template('index.html', error_message=f'系统错误: {str(e)}')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
