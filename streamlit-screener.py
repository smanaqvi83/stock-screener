import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- VERSION & AUTH ---
def get_commit_id():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v3.6.0-TR-ATR-Live"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Hunter Pro", layout="wide", page_icon="🎯")

# --- SIDEBAR ---
st.sidebar.header("System Authentication")
st.sidebar.success(f"**Build:** {COMMIT_ID}\n**Sync:** {SYNC_TIME}")

market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT", "PIBTL"]
us_list = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

# --- THE HUNTER ENGINE ---
def run_hunter_engine(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="75d", interval="1d")
    
    if df.empty: return None, {"found": False}
    
    # Technical Calculations
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    
    # Standard TR Calculation: Max(H-L, H-PC, L-PC)
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    valid_setups = []
    for i in range(2, len(df)-1):
        leg_in, base, leg_out = df['Size'].iloc[i-1], df['Size'].iloc[i], df['Size'].iloc[i+1]
        
        if base > 0 and leg_in >= 2*base and leg_out >= 4*base:
            base_high = float(df['High'].iloc[i])
            post_df = df.iloc[i+1:]
            violations = len(post_df[post_df['Low'] < base_high])
            
            valid_setups.append({
                "date": df.index[i], "high": base_high, "low": float(df['Low'].iloc[i]),
                "leg_out_high": float(df['High'].iloc[i+1]), "is_pristine": violations == 0,
                "violation_count": violations, "strength": leg_out / base, "age": len(post_df)
            })

    # Data for the TR/ATR metrics
    last_tr = df['TR'].iloc[-1]
    last_atr = df['ATR'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]

    res = {
        "ticker": ticker_str, "price": float(df['Close'].iloc[-1]), 
        "found": False, "tr": last_tr, "atr": last_atr,
        "tr_atr_ratio": last_tr / last_atr,
        "ema_cross": "Bullish" if ema20 > ema50 else "Bearish"
    }
    
    if valid_setups:
        res["found"] = True
        best = max(valid_setups, key=lambda x: (x['is_pristine'], x['strength']))
        res.update(best)
        res["distance_pct"] = ((res["price"] - res["high"]) / res["high"]) * 100
        
    return df, res

# --- MAIN UI ---
if ticker_to_run:
    df, res = run_hunter_engine(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"🏢 {res['ticker']} Technical Dashboard")
        
        # --- TOP METRIC BLOCKS (8 Blocks for maximum detail) ---
        r1 = st.columns(4)
        r1[0].metric("Price", f"{res['price']:.2f}")
        r1[1].metric("Current TR", f"{res['tr']:.2f}")
        r1[2].metric("14D ATR", f"{res['atr']:.2f}")
        r1[3].metric("Volatility Ratio", f"{res['tr_atr_ratio']:.2f}x", 
                     delta="High Vol" if res['tr_atr_ratio'] > 1 else "Low Vol")
        
        if res['found']:
            r2 = st.columns(4)
            r2[0].metric("Anchor Ceiling", f"{res['high']:.2f}")
            r2[1].metric("White Area", "PRISTINE" if res['is_pristine'] else "VIOLATED")
            r2[2].metric("EMA Pulse", res['ema_cross'])
            r2[3].metric("Anchor Age", f"{res['age']}d")

        # --- THE CHART ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='EMA 50'))
        
        if res['found']:
            box_fill = "rgba(0, 255, 255, 0.4)" if res['is_pristine'] else "rgba(255, 165, 0, 0.3)"
            fig.add_shape(type="rect", x0=res['date'], x1=df.index[df.index.get_loc(res['date'])+1], 
                          y0=res['low'], y1=res['high'], fillcolor=box_fill, line=dict(color="Yellow", width=2))
            fig.add_hline(y=res['high'], line_color="red", line_dash="dot")
        
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- EDUCATIONAL TOOLTIP ---
        with st.expander("📝 Understanding TR vs ATR"):
            st.write("""
            * **TR (True Range):** Today's price movement. It measures the distance between high and low, including any gaps from yesterday.
            * **ATR (Average True Range):** The average TR over the last 14 days. 
            * **The Signal:** If TR is higher than ATR (Ratio > 1.0), the stock is making a bigger-than-normal move.
            """)