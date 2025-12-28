import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- VERSION CONTROL ---
COMMIT_ID = "v1.4.0-Stable-Scanner"

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Pro", layout="wide", page_icon="📈")

# --- SIDEBAR: DROPDOWN & INPUT ---
st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

# Preset Tickers
psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT"]
us_list = ["TSM", "NVDA", "ORCL", "V", "JPM"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol (e.g. OGDC)")

# Priority Logic: Use manual input if provided, otherwise dropdown
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

st.sidebar.markdown("---")
st.sidebar.caption(f"**Build:** {COMMIT_ID}")

# --- ANALYSIS ENGINE ---
def run_pattern_tracker(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    
    # Fetch 60 days
    df = ticker_obj.history(period="60d", interval="1d")
    
    if df.empty: return None, "No Data"
    
    # Technical Indicators
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # Scan history for 1-2-4 setup (most recent in last 60 days)
    setup_found = False
    base_idx = -1
    for i in range(len(df)-1, 2, -1):
        leg_in = df['Size'].iloc[i-2]
        base = df['Size'].iloc[i-1]
        leg_out = df['Size'].iloc[i]
        
        if leg_in >= 2*base and leg_out >= 4*base:
            base_idx = i-1
            setup_found = True
            break 

    if not setup_found:
        return df, {"found": False, "ticker": ticker_str}

    # Parameters
    base_high = float(df['High'].iloc[base_idx].item())
    base_low = float(df['Low'].iloc[base_idx].item())
    base_date = df.index[base_idx]
    curr_price = float(df['Close'].iloc[-1].item())
    
    # Violation Check (Dips back into Base High)
    post_setup_df = df.iloc[base_idx+1:]
    violation_days = post_setup_df[post_setup_df['Low'] < base_high]
    white_area_clean = violation_days.empty

    return df, {
        "found": True,
        "ticker": ticker_str,
        "price": curr_price,
        "base_high": base_high,
        "base_low": base_low,
        "base_date": base_date,
        "white_area": white_area_clean,
        "violation_count": len(violation_days),
        "momentum": bool(df['TR'].iloc[-1].item() > df['ATR'].iloc[-1].item()),
        "pulse": bool(df['EMA20'].iloc[-1].item() > df['EMA50'].iloc[-1].item()),
        "tr_atr_ratio": float(df['TR'].iloc[-1].item() / df['ATR'].iloc[-1].item())
    }

# --- MAIN DASHBOARD ---
if ticker_to_run:
    # ADDED LOADING SPINNER
    with st.spinner(f'Searching for 1-2-4 Setup in {ticker_to_run}...'):
        df, res = run_pattern_tracker(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None and res['found']:
        st.header(f"📈 {res['ticker']} Analysis")
        
        # Metrics with Color Logic
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Live Price", f"{res['price']:.2f}")
        m2.metric("Base High", f"{res['base_high']:.2f}")
        m3.metric("White Area", "CLEAN" if res['white_area'] else "VIOLATED", 
                  delta=f"{res['violation_count']} Dips" if not res['white_area'] else "Clear", 
                  delta_color="normal" if res['white_area'] else "inverse")
        m4.metric("Power Meter", f"{res['tr_atr_ratio']:.1f}x", 
                  delta="EXPLOSIVE" if res['momentum'] else "NORMAL",
                  delta_color="normal" if res['momentum'] else "inverse")

        # Visual Chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Market'))
        
        # Highlight: Unfilled Orders (The Anchor)
        fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                      y0=res['base_low'], y1=res['base_high'],
                      fillcolor="rgba(255, 0, 0, 0.5)", line=dict(color="Red", width=2))
        
        # Highlight: White Zone
        zone_color = "rgba(255, 255, 255, 0.05)" if res['white_area'] else "rgba(255, 0, 0, 0.05)"
        fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                      y0=res['base_high'], y1=res['price'] * 1.2,
                      fillcolor=zone_color, line=dict(color="white", width=1, dash="dash"))
        
        fig.add_hline(y=res['price'], line_color="lime", annotation_text="PRICE")
        fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot", annotation_text="CEILING")

        fig.update_layout(template="plotly_dark", height=650, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
    elif df is not None and not res['found']:
        # ADDED SYMBOL TO ERROR MESSAGE
        st.error(f"❌ No valid 1-2-4 Setup found in the last 60 days for {res['ticker']}. Market is likely consolidating.")
    else:
        st.error("⚠️ Stock symbol not found. Please check ticker name.")