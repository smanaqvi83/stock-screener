import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow 1-2-4 Dashboard", layout="wide")
st.title("📊 QuantFlow: 1-2-4 Strategy & Pulse Dashboard")

# --- SIDEBAR NAVIGATION ---
st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Region", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

# Sharia & Global Top Picks
psx_sharia = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL"]
us_top = ["TSM", "V", "ORCL", "BRK-B", "JPM"]

if market_choice == "PSX (Pakistan)":
    selected_ticker = st.sidebar.selectbox("Sharia Compliant Picks", psx_sharia)
    is_psx = True
else:
    selected_ticker = st.sidebar.selectbox("Global Large Cap", us_top)
    is_psx = False

manual_ticker = st.sidebar.text_input("Search Ticker Manually")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_ticker

# --- ANALYSIS ENGINE ---
def run_analysis(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    # Fetch data
    data = yf.download(ticker_str, period="60d", interval="1d", progress=False)
    
    if data.empty:
        return None, f"Ticker {ticker_str} not found."
    
    df = data.copy()
    
    # Technicals
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    
    # 1-2-4 Logic (Converted to float to prevent Metric TypeErrors)
    leg_in = float(df['Size'].iloc[-3])
    base = float(df['Size'].iloc[-2])
    leg_out = float(df['Size'].iloc[-1])
    
    ratio_pass = (leg_in >= 2 * base) and (leg_out >= 4 * base)
    
    # White Area (Last 7 Days High)
    prev_7d_high = float(df['High'].iloc[-8:-1].max())
    current_low = float(df['Low'].iloc[-1])
    white_area_pass = current_low > prev_7d_high
    
    # Pulse Check
    latest_close = float(df['Close'].iloc[-1])
    latest_open = float(df['Open'].iloc[-1])
    ema20 = float(df['EMA20'].iloc[-1])
    ema50 = float(df['EMA50'].iloc[-1])
    pulse_bullish = (ema20 > ema50) and (latest_close > latest_open)
    
    return df, {
        "ticker": ticker_str,
        "price": latest_close,
        "pulse": pulse_bullish,
        "ratio": ratio_pass,
        "white_area": white_area_pass,
        "base_range": (float(df['Low'].iloc[-2]), float(df['High'].iloc[-2])),
        "white_barrier": prev_7d_high
    }

# --- UI EXECUTION ---
if ticker_to_run:
    df, result = run_analysis(ticker_to_run, is_psx)
    
    if df is not None:
        # Top Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Current Price", f"{result['price']:.2f}")
        m2.metric("1-2-4 Imbalance", "✅ DETECTED" if result['ratio'] else "❌ FAILED")
        m3.metric("White Area", "✅ CLEAN" if result['white_area'] else "❌ OVERLAP")

        # Summary Notification
        if result['pulse'] and result['ratio'] and result['white_area']:
            st.success(f"🟢 **TRADE ALERT:** {result['ticker']} meets all 1-2-4 and Pulse criteria.")
        else:
            st.info("ℹ️ **WAITING:** Looking for maturation or a stronger 4x Leg Out.")

        # --- INTERACTIVE CHART ---
        fig = go.Figure()

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='Market Data'
        ))

        # EMAs
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#00d2ff', width=1.5), name='Pulse (20)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='#ffcc00', width=1.5), name='Trend (50)'))

        # Visualizing Demand Zone
        fig.add_shape(
            type="rect", x0=df.index[-2], x1=df.index[-1],
            y0=result['base_range'][0], y1=result['base_range'][1],
            fillcolor="rgba(0, 255, 0, 0.3)", line_width=0, name="Demand Zone"
        )

        # Visualizing White Area Barrier
        fig.add_hline(y=result['white_barrier'], line_dash="dash", line_color="white", 
                      annotation_text="7D Maturity Line", annotation_position="top left")

        fig.update_layout(
            template="plotly_dark",
            height=650,
            xaxis_rangeslider_visible=False,
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(result)