import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- APP CONFIG ---
st.set_page_config(page_title="QuantFlow: White Area Tracker", layout="wide")
st.title("🎯 QuantFlow: Institutional White Area Tracker")

# --- SIDEBAR ---
st.sidebar.header("Settings")
market = st.sidebar.radio("Market", ["PSX", "NYSE"])
ticker_input = st.sidebar.text_input("Ticker", "SYS" if market == "PSX" else "ORCL")
ticker = f"{ticker_input.upper()}.KA" if market == "PSX" else ticker_input.upper()

# --- ENGINE ---
def analyze_history(symbol):
    df = yf.download(symbol, period="60d", interval="1d", progress=False)
    if df.empty: return None, "No Data"

    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # Scan for 1-2-4 Anchor
    base_idx = -1
    for i in range(len(df)-1, 2, -1):
        if df['Size'].iloc[i-2] >= 2 * df['Size'].iloc[i-1] and df['Size'].iloc[i] >= 4 * df['Size'].iloc[i-1]:
            base_idx = i-1
            break
    
    if base_idx == -1: return df, {"found": False}

    # Strategy Parameters
    base_high = float(df['High'].iloc[base_idx].item())
    base_low = float(df['Low'].iloc[base_idx].item())
    base_date = df.index[base_idx]
    
    # White Area Violation Check: Did any candle Low after the Base drop below Base High?
    post_setup_df = df.iloc[base_idx+1:]
    violation_days = post_setup_df[post_setup_df['Low'] < base_high]
    is_violated = not violation_days.empty
    
    return df, {
        "found": True,
        "base_high": base_high,
        "base_low": base_low,
        "base_date": base_date,
        "is_violated": is_violated,
        "violation_count": len(violation_days),
        "curr_price": float(df['Close'].iloc[-1].item()),
        "momentum": float(df['TR'].iloc[-1].item() > df['ATR'].iloc[-1].item())
    }

# --- UI ---
df, res = analyze_history(ticker)

if df is not None and res['found']:
    st.subheader(f"Analysis for {ticker}")
    
    # Status Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"{res['curr_price']:.2f}")
    c2.metric("Base High (Ceiling)", f"{res['base_high']:.2f}")
    
    status_text = "❌ VIOLATED" if res['is_violated'] else "✅ CLEAN"
    c3.metric("White Area Integrity", status_text, 
              delta=f"{res['violation_count']} Dips" if res['is_violated'] else "Perfect", 
              delta_color="inverse" if res['is_violated'] else "normal")

    if res['is_violated']:
        st.error(f"⚠️ Warning: Price has dipped back into the White Area {res['violation_count']} times since the setup. The 'Sky' is no longer clear.")
    else:
        st.success("🚀 White Area is intact. Price has stayed above the Base High since the institutional move.")

    # --- CHART ---
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
    
    # 1. MARK THE UNFILLED ORDER BASE (RED)
    fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                  y0=res['base_low'], y1=res['base_high'],
                  fillcolor="rgba(255, 0, 0, 0.6)", line=dict(color="red", width=2))
    
    # 2. MARK THE WHITE AREA (From Base High to Today)
    # Color turns orange/red if violated, stays white if clean
    zone_color = "rgba(255, 100, 100, 0.1)" if res['is_violated'] else "rgba(255, 255, 255, 0.08)"
    fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                  y0=res['base_high'], y1=res['curr_price'] * 1.2,
                  fillcolor=zone_color, line=dict(color="white", width=1, dash="dash"))

    # 3. HIGHLIGHT THE "WALL" (Base High)
    fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot", 
                  annotation_text="WHITE AREA ENTRY (WALL)", annotation_position="left")

    fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

elif df is not None:
    st.warning("No 1-2-4 Setup found in last 60 days.")