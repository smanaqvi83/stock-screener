import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- VERSION & GIT LOGIC ---
def get_commit_id():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v1.2.7-Live"

COMMIT_ID = get_commit_id()
APP_VERSION = f"QuantFlow {COMMIT_ID}"
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Dashboard", layout="wide", page_icon="📈")

# --- SIDEBAR & NAVIGATION ---
st.sidebar.header("Market Control")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

psx_sharia = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL"]
us_top = ["TSM", "V", "ORCL", "BRK-B", "JPM"]

if market_choice == "PSX (Pakistan)":
    selected_ticker = st.sidebar.selectbox("Sharia Compliant Stocks", psx_sharia)
    is_psx = True
else:
    selected_ticker = st.sidebar.selectbox("Global Market Leaders", us_top)
    is_psx = False

manual_ticker = st.sidebar.text_input("Manual Search (e.g. NVDA or OGDC)")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_ticker

st.sidebar.markdown("---")
st.sidebar.caption(f"**Build Hash:** `{COMMIT_ID}`")
st.sidebar.caption(f"**Instance Sync:** {SYNC_TIME}")

# --- THE STRATEGY ENGINE ---
def run_analysis(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    data = yf.download(ticker_str, period="60d", interval="1d", progress=False)
    
    if data.empty:
        return None, f"No data found for {ticker_str}"
    
    df = data.copy()
    ticker_info = yf.Ticker(ticker_str).info
    company_name = ticker_info.get('longName', ticker_str)

    # Technical Indicators
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    
    # TR vs ATR Calculation
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    try:
        curr_price = float(df['Close'].iloc[-1].item())
        open_price = float(df['Open'].iloc[-1].item())
        curr_tr = float(df['TR'].iloc[-1].item())
        curr_atr = float(df['ATR'].iloc[-1].item())
        
        # 1-2-4 Sizes
        leg_out = float(df['Size'].iloc[-1].item())
        base = float(df['Size'].iloc[-2].item())
        leg_in = float(df['Size'].iloc[-3].item())
        
        # Calculations
        ratio_val = leg_out / base if base != 0 else 0
        ratio_pass = bool(leg_in >= 2 * base and leg_out >= 4 * base)
        
        # White Area Check
        white_barrier = float(df['High'].iloc[-8:-1].max().item())
        white_area_pass = bool(float(df['Low'].iloc[-1].item()) > white_barrier)
        
        # Pulse & Momentum Checks
        ema20_val = float(df['EMA20'].iloc[-1].item())
        ema50_val = float(df['EMA50'].iloc[-1].item())
        pulse_pass = bool(ema20_val > ema50_val and curr_price > open_price)
        momentum_ratio = curr_tr / curr_atr if curr_atr != 0 else 0
        momentum_pass = bool(curr_tr > curr_atr)
        
        return df, {
            "name": company_name,
            "ticker": ticker_str,
            "price": curr_price,
            "ratio_pass": ratio_pass,
            "ratio_val": ratio_val,
            "white_area_pass": white_area_pass,
            "momentum_pass": momentum_pass,
            "momentum_ratio": momentum_ratio,
            "pulse_pass": pulse_pass,
            "tr": curr_tr,
            "atr": curr_atr,
            "base_range": (float(df['Low'].iloc[-2].item()), float(df['High'].iloc[-2].item())),
            "white_barrier": white_barrier
        }
    except Exception as e:
        return None, f"Analysis Error: {str(e)}"

# --- MAIN DASHBOARD UI ---
if ticker_to_run:
    df, res = run_analysis(ticker_to_run, is_psx)
    
    if df is not None:
        # DISPLAY CURRENT SELECTED SHARE
        st.markdown(f"## 🏢 {res['name']} ({res['ticker']})")
        st.markdown(f"**Current Status:** {'🟢 ACTIVE SIGNAL' if all([res['ratio_pass'], res['white_area_pass'], res['momentum_pass'], res['pulse_pass']]) else '⚪ MONITORING'}")
        
        # Metrics Header
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current Price", f"{res['price']:.2f}")
        
        m2.metric("1-2-4 Ratio", f"{res['ratio_val']:.1f}x", 
                  delta="PASS" if res['ratio_pass'] else "FAIL", 
                  delta_color="normal" if res['ratio_pass'] else "inverse")
        
        m3.metric("White Area", "CLEAN" if res['white_area_pass'] else "OVERLAP", 
                  delta="SAFE" if res['white_area_pass'] else "RISKY", 
                  delta_color="normal" if res['white_area_pass'] else "inverse")
        
        m4.metric("Power Meter (TR/ATR)", f"{res['momentum_ratio']:.1f}x", 
                  delta="EXPLOSIVE" if res['momentum_pass'] else "NORMAL", 
                  delta_color="normal" if res['momentum_pass'] else "inverse")

        st.markdown("---")
        
        # Detailed Verdict Section
        v1, v2 = st.columns(2)
        with v1:
            st.subheader("Strategy Checklist")
            st.write(f"{'✅' if res['pulse_pass'] else '❌'} **Trend Pulse:** {'Strong Bullish' if res['pulse_pass'] else 'Weak/Sideways'}")
            st.write(f"{'✅' if res['ratio_pass'] else '❌'} **Demand Imbalance:** {'Institutional 1-2-4' if res['ratio_pass'] else 'Insufficient Ratio'}")
            st.write(f"{'✅' if res['white_area_pass'] else '❌'} **Clean Traffic:** {'White Area Clear' if res['white_area_pass'] else 'Blocked'}")
            st.write(f"{'✅' if res['momentum_pass'] else '❌'} **Force (TR > ATR):** {'High Velocity' if res['momentum_pass'] else 'Low Volatility'}")

        with v2:
            st.subheader("Final Verdict")
            if all([res['ratio_pass'], res['white_area_pass'], res['momentum_pass'], res['pulse_pass']]):
                st.success(f"🚀 **GOLDEN SETUP:** {res['ticker']} is aligned for a 7-day run.")
                st.balloons()
            else:
                st.info("⚠️ **WAITING:** Looking for institutional force or cleaner traffic.")

        # Plotly Chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='Pulse (20)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='Trend (50)'))
        
        # Mark the Demand Zone (Base)
        fig.add_shape(type="rect", x0=df.index[-2], x1=df.index[-1], y0=res['base_range'][0], y1=res['base_range'][1],
                      fillcolor="rgba(0, 255, 0, 0.2)", line_width=0)
        
        # Mark the White Area Ceiling
        fig.add_hline(y=res['white_barrier'], line_dash="dash", line_color="white", annotation_text="7D Ceiling")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(res)