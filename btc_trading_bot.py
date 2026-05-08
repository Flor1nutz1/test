import yfinance as yf
import pandas as pd
import numpy as np
import ta
import datetime

def fetch_data():
    ticker = "BTC-USD"
    df = yf.download(ticker, period="150d", interval="1d", progress=False)
    
    if df.empty:
        raise ValueError("Failed to fetch data. Please check your internet connection or try again later.")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        
    df.dropna(inplace=True)
    return df

def calculate_indicators(df):
    df['EMA_7'] = ta.trend.EMAIndicator(close=df['Close'], window=7).ema_indicator()
    df['EMA_30'] = ta.trend.EMAIndicator(close=df['Close'], window=30).ema_indicator()
    
    macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()
    
    df['RSI'] = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()
    
    bollinger = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_High'] = bollinger.bollinger_hband()
    df['BB_Low'] = bollinger.bollinger_lband()
    df['BB_Mid'] = bollinger.bollinger_mavg()
    
    df['ATR'] = ta.volatility.AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14).average_true_range()
    
    df.dropna(inplace=True)
    return df

def score_signals(row):
    score = 0
    if row['EMA_7'] > row['EMA_30']:
        score += 30
    if row['MACD'] > row['MACD_Signal']:
        score += 25
    if row['RSI'] < 30:
        score += 25
    elif 30 <= row['RSI'] < 50:
        score += 15
    elif 50 <= row['RSI'] < 70:
        score += 5
    if row['Close'] < row['BB_Low']:
        score += 20 
    elif row['Close'] < row['BB_Mid']:
        score += 10 
    return score

def determine_sell_signal(row):
    sell_score = 0
    if row['EMA_7'] < row['EMA_30']:
        sell_score += 40
    if row['MACD'] < row['MACD_Signal']:
        sell_score += 30
    if row['RSI'] > 70:
        sell_score += 30
    return sell_score >= 60

def simulate_trading(df, initial_balance=100.0, fee_rate=0.001):
    balance_usd = initial_balance
    btc_held = 0.0
    
    highest_price_since_buy = 0.0
    entry_price = 0.0
    
    ledger = []
    chart_data = []
    
    for date, row in df.iterrows():
        current_price = float(row['Close'])
        atr = float(row['ATR'])
        action_taken = None
        
        if btc_held > 0:
            highest_price_since_buy = max(highest_price_since_buy, current_price)
            stop_loss_price = highest_price_since_buy - (2 * atr)
            hard_stop_price = entry_price * 0.95
            
            actual_stop_loss = max(stop_loss_price, hard_stop_price)
            
            if current_price <= actual_stop_loss:
                sell_amount_usd = btc_held * current_price
                fee = sell_amount_usd * fee_rate
                net_usd = sell_amount_usd - fee
                
                balance_usd += net_usd
                action_taken = "STOP-LOSS SELL"
                
                ledger.append({
                    "Date": date.strftime('%Y-%m-%d'),
                    "Action": action_taken,
                    "Price": round(current_price, 2),
                    "BTC_Amount": round(float(btc_held), 6),
                    "USD_Value": round(net_usd, 2),
                    "Fee": round(fee, 2),
                    "Reason": f"Stop loss ({round(actual_stop_loss, 2)})",
                    "Portfolio_Value": round(balance_usd, 2)
                })
                btc_held = 0.0
                highest_price_since_buy = 0.0
        
        if not action_taken:
            buy_score = score_signals(row)
            is_sell_signal = determine_sell_signal(row)
            
            if btc_held == 0 and buy_score >= 50:
                investment_ratio = buy_score / 100.0
                invest_amount_usd = balance_usd * investment_ratio
                
                if invest_amount_usd > 10: 
                    fee = invest_amount_usd * fee_rate
                    usable_usd = invest_amount_usd - fee
                    bought_btc = usable_usd / current_price
                    
                    balance_usd -= invest_amount_usd
                    btc_held += bought_btc
                    entry_price = current_price
                    highest_price_since_buy = current_price
                    action_taken = "BUY"
                    
                    ledger.append({
                        "Date": date.strftime('%Y-%m-%d'),
                        "Action": action_taken,
                        "Price": round(current_price, 2),
                        "BTC_Amount": round(float(bought_btc), 6),
                        "USD_Value": round(invest_amount_usd, 2),
                        "Fee": round(fee, 2),
                        "Reason": f"Buy Score: {buy_score}/100",
                        "Portfolio_Value": round(balance_usd + (btc_held * current_price), 2)
                    })
                    
            elif btc_held > 0 and is_sell_signal:
                sell_amount_usd = btc_held * current_price
                fee = sell_amount_usd * fee_rate
                net_usd = sell_amount_usd - fee
                
                balance_usd += net_usd
                action_taken = "SELL"
                
                ledger.append({
                    "Date": date.strftime('%Y-%m-%d'),
                    "Action": action_taken,
                    "Price": round(current_price, 2),
                    "BTC_Amount": round(float(btc_held), 6),
                    "USD_Value": round(net_usd, 2),
                    "Fee": round(fee, 2),
                    "Reason": "Sell indicators triggered",
                    "Portfolio_Value": round(balance_usd, 2)
                })
                btc_held = 0.0
                highest_price_since_buy = 0.0

        chart_data.append({
            "date": date.strftime('%Y-%m-%d'),
            "price": round(current_price, 2),
            "action": action_taken
        })

    final_portfolio_value = balance_usd + (btc_held * float(df.iloc[-1]['Close']))
    
    return ledger, final_portfolio_value, balance_usd, btc_held, chart_data

def generate_live_prediction(df):
    latest_data = df.iloc[-1]
    date = latest_data.name.strftime('%Y-%m-%d')
    buy_score = score_signals(latest_data)
    is_sell = determine_sell_signal(latest_data)
    price = float(latest_data['Close'])
    
    result = {
        "date": date,
        "price": round(price, 2),
        "score": buy_score
    }
    
    if buy_score >= 50:
        result['action'] = "BUY"
        result['reason'] = "Indicators suggest strong upward momentum and favorable conditions."
    elif is_sell:
        result['action'] = "SELL"
        result['reason'] = "Indicators (EMA, MACD, RSI) suggest a downtrend or overbought conditions."
    else:
        result['action'] = "HOLD"
        result['reason'] = "Conditions are mixed. Not enough momentum to buy, but not weak enough to sell."
        
    return result

def run_bot():
    df = fetch_data()
    df = calculate_indicators(df)
    df_sim = df.tail(60).copy()
    
    ledger, final_value, final_usd, final_btc, chart_data = simulate_trading(df_sim)
    prediction = generate_live_prediction(df)
    
    return {
        "ledger": ledger,
        "performance": {
            "start_balance": 100.00,
            "final_balance": round(final_value, 2),
            "profit_usd": round(final_value - 100, 2),
            "profit_pct": round(((final_value - 100) / 100) * 100, 2),
            "final_usd": round(final_usd, 2),
            "final_btc": round(float(final_btc), 6)
        },
        "prediction": prediction,
        "chart": chart_data
    }

if __name__ == "__main__":
    import json
    print(json.dumps(run_bot(), indent=2))
