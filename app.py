from flask import Flask, render_template, request, jsonify
from data_loader import fetch_stock_data
import pandas as pd

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch', methods=['POST'])
def fetch():
    try:
        symbol = request.form.get('symbol')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        if not symbol or not start_date or not end_date:
            return jsonify({'error': 'Missing required fields'}), 400

        # Fetch data
        df = fetch_stock_data(symbol, start_date, end_date)

        # Take first 5 rows
        head_df = df.head(5)

        # Convert to JSON records
        result = head_df.to_dict(orient='records')

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
