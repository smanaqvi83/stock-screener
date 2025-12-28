import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- 1. SYSTEM AUTHENTICATION ---
def get_commit_id():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v4.1.0-EMA-Cross-Ready"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="QuantFlow Hunter Pro", layout="wide", page_icon="🎯")

# --- 3. SIDEBAR ---
st.sidebar.header("System Status")
st.sidebar.success(f"**Build:** {COMMIT_ID}\n**Sync:** {SYNC_TIME}")

market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT", "PIBTL"]
us_list = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "ORCL"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

# --- 4. THE HUNTER ENGINE ---
def run_hunter_engine(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="100d", interval="1d") 
    
    if df.empty: return None, {"found": False, "ticker": ticker_str}
    
    # 30/50 EMA Calculation
    df['EMA30'] = df['Close'].ewm(span=30, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # TR/ATR and Volume
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
    
    valid_setups = []
    for i in range(2, len(df)-1):
        leg_in, base, leg_out = df['Size'].iloc[i-1], df['Size'].iloc[i], df['Size'].iloc[i+1]
        if base > 0 and leg_in >= 2*base and leg_out >= 4*base:
            base_high = float(df['High'].iloc[i])
            post_df = df.iloc[i+1:]
            violations = len(post_df[post_df['Low'] < base_high])
            if violations == 0:
                valid_setups.append({
                    "date": df.index[i], "high": base_high, "low": float(df['Low'].iloc[i]),
                    "leg_out_high": float(df['High'].iloc[i+1]), "strength": leg_out / base, "age": len(post_df)
                })

    # Current Context for UI
    ema30, ema50 = df['EMA30'].iloc[-1], df['EMA50'].iloc[-1]
    res = {
        "ticker": ticker_str, "price": float(df['Close'].iloc[-1]), "found": False,
        "tr_atr": df['TR'].iloc[-1] / df['ATR'].iloc[-1],
        "vol_ratio": df['Volume'].iloc[-1] / df['Vol_Avg'].iloc[-1] if df['Vol_Avg'].iloc[-1] > 0 else 0,
        "ema_status": "BULLISH" if ema30 > ema50 else "BEARISH",
        "ema_diff": ((ema30 - ema50) / ema50) * 100
    }
    
    if valid_setups:
        res["found"] = True
        best = max(valid_setups, key=lambda x: x['strength'])
        res.update(best)
        res["dist"] = ((res["price"] - res["high"]) / res["high"]) * 100
        
        # RELIABILITY SCORE
        score = 40 if res['ema_status'] == "BULLISH" else 20
        score += min(res['age'], 30)
        if res['tr_atr'] > 1.0: score += 15
        if res['vol_ratio'] > 1.2: score += 15
        res["score"] = score

    return df, res

# --- 5. MAIN UI ---
if ticker_to_run:
    df, res = run_hunter_engine(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"📊 {res['ticker']} Strategic Dashboard")
        
        # --- TOP METRIC BLOCKS (5 Columns) ---
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Live Price", f"{res['price']:.2f}")
        
        # EMA 30/50 Column
        m2.metric("Trend (30/50 EMA)", res['ema_status'], 
                  delta=f"{res['ema_diff']:.2f}% Gap", 
                  delta_color="normal" if res['ema_status'] == "BULLISH" else "inverse")
        
        m3.metric("Power (TR/ATR)", f"{res['tr_atr']:.2f}x")
        m4.metric("Vol Multiplier", f"{res['vol_ratio']:.2f}x")
        
        if res['found']:
            m5.metric("Hunter Score", f"{res['score']}/100", delta=f"{res['age']}d Age")

        # --- FINAL VERDICT (Buying Recommendation) ---
        st.markdown("---")
        if res['found']:
            v1, v2 = st.columns([1, 2])
            is_valid_entry = res['dist'] < 3.5
            is_bullish = res['ema_status'] == "BULLISH"
            
            if is_valid_entry and is_bullish and res['score'] >= 60:
                v1.success("🛡️ VERDICT: BUY AUTHORIZED")
                v2.success(f"Confirmed: Price is near support ({res['dist']:.1f}%). 30/50 EMA Trend is Supportive.")
            elif is_valid_entry:
                v1.warning("🛡️ VERDICT: WATCHING")
                v2.info("Price is at support, but 30/50 EMA trend or volume is not yet confirmed.")
            else:
                v1.info("🛡️ VERDICT: DO NOT CHASE")
                v2.write(f"Wait for pullback to {res['high']:.2f}. Price currently {res['dist']:.1f}% above base.")

        # --- CHART ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA30'], line=dict(color='white', width=1.5), name='EMA 30'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='orange', width=1.5), name='EMA 50'))

        if res['found']:
            fig.add_shape(type="rect", x0=res['date'], x1=df.index[df.index.get_loc(res['date'])+1], 
                          y0=res['low'], y1=res['high'], fillcolor="rgba(0, 255, 255, 0.4)", line=dict(color="Yellow", width=3))
            fig.add_hline(y=res['high'], line_color="red", line_dash="dot")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)