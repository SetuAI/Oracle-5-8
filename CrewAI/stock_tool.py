'''
custom tool : @tool
custom tool : when you dont have an option for in built tools
# pip install yfinance
gets share price of a stock using yfinance 
'''

import yfinance as yf
from crewai.tools import tool


# @ decorator to define a tool
@tool("Get share price")
def get_stock_price(symbol: str) -> str:
    '''
    gets the closing price and 1 month change of a stock using yfinance
    '''
    prices = yf.Ticker(symbol).history(period="1mo")["Close"]
    if prices.empty:
        return f"No data found for symbol: {symbol}"
    latest = prices.iloc[-1]
    change = (latest - prices.iloc[0]) / prices.iloc[0] * 100
    return f" {symbol} latest closing price: {latest:.2f}, 1 month change: {change:.2f}%"

if __name__ == "__main__":
    # Example usage
    print(get_stock_price.run(symbol="INFY.NS"))  # Replace "AAPL" with any stock symbol you want to check
