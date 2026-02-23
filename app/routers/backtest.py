from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from app.services.data_fetcher import DataFetcher
from app.services.backtest_engine import BacktestEngine
import pandas as pd
import numpy as np

router = APIRouter(prefix="/backtest", tags=["Backtest"])

class BacktestRequest(BaseModel):
    symbol: str
    start_date: str = '20230101'
    end_date: str = '20231231'
    initial_capital: float = 100000.0

@router.post("/run")
async def run_backtest(request: BacktestRequest):
    """
    Executes a backtest for a given stock and date range.
    """
    try:
        # Fetch data
        df = DataFetcher.fetch_data(request.symbol, request.start_date, request.end_date)

        if df.empty:
            raise HTTPException(status_code=404, detail="No data found for the specified parameters.")

        # Run Backtest
        engine = BacktestEngine(initial_capital=request.initial_capital)
        results = engine.run_backtest(df, request.symbol)

        # Format results for frontend
        stats = results['stats']
        equity_curve = results['equity_curve']
        trades = results['trades']

        # Convert DataFrames to JSON-serializable format (list of dicts)
        # Handle NaN/None
        equity_curve = equity_curve.replace({np.nan: None})
        equity_data = equity_curve.to_dict(orient="records")

        # Trades list is already list of dicts, but need to ensure values are serializable
        # (e.g., numpy types to native python types)
        # Assuming trades dict contains simple types.

        return {
            "stats": stats,
            "equity_curve": equity_data,
            "trades": trades
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
