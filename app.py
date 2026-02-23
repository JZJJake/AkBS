from flask import Flask, render_template, request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from data_loader import fetch_stock_data
from backtest_engine import BacktestEngine
import pandas as pd

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
            return render_template('index.html', error_message='Missing required fields')

        df = pd.DataFrame()
        try:
            df = fetch_stock_data(symbol, start_date, end_date)
        except Exception as e:
            # If fetch fails, show error
            return render_template('index.html', error_message=f'Error fetching data: {str(e)}')

        # Run Backtest
        engine = BacktestEngine(commission_rate=0.0005)
        results = engine.run_backtest(df, symbol)

        stats = results['stats']
        equity_curve = results['equity_curve']

        plot_url = None
        if not equity_curve.empty:
            plt.figure(figsize=(10, 6))
            dates = pd.to_datetime(equity_curve['date'])
            values = equity_curve['total_value']

            plt.plot(dates, values)
            plt.title('Equity Curve')
            plt.xlabel('Date')
            plt.ylabel('Total Value')
            plt.grid(True)
            plt.gcf().autofmt_xdate()

            img = io.BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode('utf-8')
            plt.close()

        return render_template('result.html', stats=stats, plot_url=plot_url)

    except Exception as e:
        return render_template('index.html', error_message=f'System Error: {str(e)}')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
