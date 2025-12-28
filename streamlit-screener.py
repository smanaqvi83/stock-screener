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
        return "v1.2.9-Final"

COMMIT_ID = get_commit_id()
APP_VERSION = f"QuantFlow {COMMIT_ID}"
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Pro Dashboard", layout="wide", page_icon="📈")

# --- SIDEBAR ---
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

# --- ANALYSIS ENGINE ---
def run_analysis(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    data = ticker_obj.history(period="60d", interval="1d")
    
    if data.empty:
        return None, f"No data found for {ticker_str}"
    
    df = data.copy()
    try:
        company_name = ticker_obj.info.get('longName', ticker_str)
    except:
        company_name = ticker_str

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(abs(df['Low'] - df['Close'].shift(1)))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    try:
        curr_price = float(df['Close'].iloc[-1].item())
        open_price = float(df['Open'].iloc[-1].item())
        curr_tr = float(df['TR'].iloc[-1].item())
        curr_atr = float(df['ATR'].iloc[-1].item())
        
        leg_out_sz = float(df['Size'].iloc[-1].item())
        base_sz = float(df['Size'].iloc[-2].item())
        leg_in_sz = float(df['Size'].iloc[-3].item())
        
        ratio_val = leg_out_sz / base_sz if base_sz != 0 else 0
        ratio_pass = bool(leg_in_sz >= 2 * base_sz and leg_out_sz >= 4 * base_sz)
        
        # White Area Barrier: Highest High of previous 7 trading days
        white_barrier = float(df['High'].iloc[-8:-1].max().item())
        white_area_pass = bool(float(df['Low'].iloc[-1].item()) > white_barrier)
        
        momentum_ratio = curr_tr / curr_atr if curr_atr != 0 else 0
        momentum_pass = bool(curr_tr > curr_atr)
        pulse_pass = bool(float(df['EMA20'].iloc[-1].item()) > float(df['EMA50'].iloc[-1].item()) and curr_price > open_price)
        
        return df, {
            "name": company_name, "ticker": ticker_str, "price": curr_price,
            "ratio_pass": ratio_pass, "ratio_val": ratio_val,
            "white_area_pass": white_area_pass, "momentum_pass": momentum_pass,
            "momentum_ratio": momentum_ratio, "pulse_pass": pulse_pass,
            "tr": curr_tr, "atr": curr_atr,
            "base_range": (float(df['Low'].iloc[-2].item()), float(df['High'].iloc[-2].item())),
            "white_barrier": white_barrier,
            "base_date": df.index[-2]
        }
    except Exception as e:
        return None, f"Analysis Error: {str(e)}"

# --- UI DISPLAY ---
if ticker_to_run:
    df, res = run_analysis(ticker_to_run, is_psx)
    if df is not None:
        st.markdown(f"## 🏢 {res['name']} ({res['ticker']})")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current Price", f"{res['price']:.2f}")
        m2.metric("1-2-4 Ratio", f"{res['ratio_val']:.1f}x", delta="PASS" if res['ratio_pass'] else "FAIL", delta_color="normal" if res['ratio_pass'] else "inverse")
        m3.metric("White Zone Status", "CLEAN" if res['white_area_pass'] else "OVERLAP", delta="SKY OPEN" if res['white_area_pass'] else "BLOCKED", delta_color="normal" if res['white_area_pass'] else "inverse")
        m4.metric("Power Meter", f"{res['momentum_ratio']:.1f}x", delta="EXPLOSIVE" if res['momentum_pass'] else "NORMAL", delta_color="normal" if res['momentum_pass'] else "inverse")

        # --- THE CHART ---
        fig = go.Figure()
        
        # 1. Main Candles
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Market'))
        
        # 2. EMAs
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='Pulse (20)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='Trend (50)'))
        
        # 3. UNFILLED ORDERS (The Base)
        fig.add_shape(type="rect", x0=df.index[-2], x1=df.index[-1], y0=res['base_range'][0], y1=res['base_range'][1],
                      fillcolor="rgba(0, 255, 0, 0.4)", line=dict(color="green", width=2), name="Unfilled Orders")
        fig.add_annotation(x=df.index[-2], y=res['base_range'][0], text="UNFILLED ORDERS (BASE)", showarrow=True, arrowhead=1, yshift=-10)
        
        # 4. THE WHITE ZONE (Sky Area from 7D High to Infinity)
        fig.add_shape(type="rect", x0=df.index[-8], x1=df.index[-1], y0=res['white_barrier'], y1=res['price']*1.2,
                      fillcolor="rgba(255, 255, 255, 0.1)", line=dict(color="white", width=1, dash="dash"), name="White Zone")
        
        # 5. CURRENT PRICE HIGHLIGHT
        fig.add_hline(y=res['price'], line_color="lime", line_dash="solid", line_width=2,
                      annotation_text=f"Current: {res['price']:.2f}", annotation_position="right")

        # 6. MATURITY CEILING
        fig.add_hline(y=res['white_barrier'], line_color="red", line_dash="dot",
                      annotation_text="7D Maturity Ceiling", annotation_position="left")

        fig.update_layout(template="plotly_dark", height=700, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(res)