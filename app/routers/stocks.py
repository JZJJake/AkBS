from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.data_fetcher import DataFetcher
import pandas as pd
import numpy as np

router = APIRouter(prefix="/stocks", tags=["Stocks"])

@router.get("/list", response_model=List[Dict[str, str]])
async def get_stock_list():
    """
    Returns a hardcoded list of popular A-share stocks.
    """
    stocks = [
        {"symbol": "600519", "name": "贵州茅台"},
        {"symbol": "601318", "name": "中国平安"},
        {"symbol": "600036", "name": "招商银行"},
        {"symbol": "000858", "name": "五粮液"},
        {"symbol": "002594", "name": "比亚迪"},
        {"symbol": "300750", "name": "宁德时代"},
        {"symbol": "600900", "name": "长江电力"},
        {"symbol": "601888", "name": "中国中免"},
        {"symbol": "000333", "name": "美的集团"},
        {"symbol": "603288", "name": "海天味业"}
    ]
    return stocks

@router.get("/{symbol}/kline")
async def get_stock_kline(symbol: str):
    """
    Fetches stock kline data and calculates indicators.
    Returns JSON formatted for frontend charts.
    """
    try:
        # Fetch data (defaulting to last 2 years for visualization)
        df = DataFetcher.fetch_data(symbol, start_date='20220101', end_date='20241231')

        if df.empty:
            raise HTTPException(status_code=404, detail="Stock data not found")

        # Calculate indicators
        df = DataFetcher.calculate_indicators(df)

        # Replace NaN with None (null in JSON) for frontend compatibility
        df = df.replace({np.nan: None})

        # Convert to list of dicts
        data = df.to_dict(orient="records")

        return {"symbol": symbol, "data": data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
