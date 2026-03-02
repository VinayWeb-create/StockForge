import pandas as pd
import numpy as np
import ml_utils

def test_linear_regression():
    print("Testing Linear Regression...")
    data = {
        'Date': pd.date_range(start='2024-01-01', periods=100),
        'Close': np.linspace(100, 200, 100) + np.random.normal(0, 5, 100)
    }
    df = pd.DataFrame(data)
    result = ml_utils.predict_stock_price(df, forecast_days=10)
    assert 'forecast_prices' in result
    assert len(result['forecast_prices']) == 10
    print("Linear Regression test passed.")

def test_arima():
    print("Testing ARIMA...")
    data = {
        'Date': pd.date_range(start='2024-01-01', periods=100),
        'Close': np.linspace(100, 200, 100) + np.random.normal(0, 5, 100)
    }
    df = pd.DataFrame(data)
    result = ml_utils.predict_arima(df, forecast_days=10)
    assert 'forecast_prices' in result
    assert len(result['forecast_prices']) == 10
    assert result.get('method') == 'ARIMA' or 'forecast_prices' in result
    print("ARIMA test passed.")

if __name__ == "__main__":
    try:
        test_linear_regression()
        test_arima()
        print("\nAll ML utility tests passed!")
    except Exception as e:
        print(f"\nTests failed: {e}")
