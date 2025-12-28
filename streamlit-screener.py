import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- VERSION CONTROL ---
COMMIT_ID = "v1.5.0-Unfilled-Label-Fix"

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Pro", layout="wide", page_icon="📈")

# --- SIDEBAR ---
st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT"]
us_list = ["TSM", "NVDA", "ORCL", "V", "JPM"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol")

ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

# --- ANALYSIS ENGINE ---
def run_pattern_tracker(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    
    df = ticker_obj.history(period="60d", interval="1d")
    if df.empty: return None, None
    
    # Technical Indicators
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # Scan history for 1-2-4 setup
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

    res = {"found": setup_found, "ticker": ticker_str}
    
    if setup_found:
        base_high = float(df['High'].iloc[base_idx].item())
        base_low = float(df['Low'].iloc[base_idx].item())
        
        # Violation Check
        post_setup_df = df.iloc[base_idx+1:]
        violation_days = post_setup_df[post_setup_df['Low'] < base_high]
        
        res.update({
            "base_high": base_high,
            "base_low": base_low,
            "base_date": df.index[base_idx],
            "white_area": violation_days.empty,
            "violation_count": len(violation_days),
            "momentum": bool(df['TR'].iloc[-1].item() > df['ATR'].iloc[-1].item()),
            "pulse": bool(df['EMA20'].iloc[-1].item() > df['EMA50'].iloc[-1].item()),
            "curr_price": float(df['Close'].iloc[-1].item())
        })
    
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    with st.spinner(f'Analyzing {ticker_to_run}...'):
        df, res = run_pattern_tracker(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"📊 {res['ticker']} Analysis")
        
        # --- 1. THE CHART ---
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='EMA 50'))
        
        if res['found']:
            # Highlight Base Candle
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'],
                          fillcolor="rgba(255, 0, 0, 0.5)", line=dict(color="Red", width=2))
            
            # UNFILLED ORDER LABEL
            fig.add_annotation(
                x=res['base_date'], 
                y=res['base_high'],
                text="UNFILLED ORDER CANDLE",
                showarrow=True,
                arrowhead=2,
                arrowcolor="red",
                ax=0,
                ay=-40,
                bgcolor="red",
                font=dict(color="white", size=12)
            )

            # White Zone Highlighting
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=df['High'].max() * 1.05,
                          fillcolor="rgba(255, 255, 255, 0.05)", line=dict(color="white", width=1, dash="dash"))
            fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot")

        fig.update_layout(template="plotly_dark", height=650, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- 2. THE VERDICT ---
        if res['found']:
            if res['white_area'] and res['pulse'] and res['momentum']:
                # ALL GREEN SUCCESS MESSAGE
                st.success(f"✅ **Valid 1-2-4 Setup Found for {res['ticker']}!** The Unfilled Order Candle has been identified. White Area is clean and momentum is explosive.")
                st.balloons()
            else:
                # PARTIAL MATCH WARNING
                st.warning(f"⚠️ **Setup Found for {res['ticker']}**, but some health checks failed. Check the chart for White Area violations or weak momentum.")
        else:
            # NOT FOUND ERROR
            st.error(f"❌ **No valid 1-2-4 setup found for {res['ticker']}** in the last 60 days.")

    else:
        st.error(f"Data Error: {ticker_to_run} not found.")