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
        return "v1.8.5-Watermark-Final"

COMMIT_ID = get_commit_id()
APP_VERSION = f"QuantFlow {COMMIT_ID}"
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

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

st.sidebar.markdown("---")
st.sidebar.caption(f"**Build Hash:** `{COMMIT_ID}`")
st.sidebar.caption(f"**Version:** {APP_VERSION}")
st.sidebar.caption(f"**Instance Sync:** {SYNC_TIME}")

# --- ANALYSIS ENGINE ---
def run_pattern_tracker(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    
    df = ticker_obj.history(period="60d", interval="1d")
    if df.empty: return None, {"ticker": ticker_str, "found": False}
    
    # Technical Indicators
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # Scan history for 1-2-4 setup (Searching back 60 days)
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
    res["price"] = float(df['Close'].iloc[-1])
    res["tr_val"] = float(df['TR'].iloc[-1])
    res["atr_val"] = float(df['ATR'].iloc[-1])
    res["tr_atr_ratio"] = float(res["tr_val"] / res["atr_val"]) if res["atr_val"] != 0 else 0
    res["momentum"] = bool(res["tr_val"] > res["atr_val"])

    if setup_found:
        base_high = float(df['High'].iloc[base_idx])
        base_low = float(df['Low'].iloc[base_idx])
        base_date = df.index[base_idx]
        
        post_setup_df = df.iloc[base_idx+1:]
        violation_days = post_setup_df[post_setup_df['Low'] < base_high]
        
        dist_from_ceiling = ((res["price"] - base_high) / base_high) * 100
        
        res.update({
            "base_high": base_high,
            "base_low": base_low,
            "base_date": base_date,
            "white_area_clean": violation_days.empty,
            "violation_count": len(violation_days),
            "distance_pct": dist_from_ceiling
        })
    
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    with st.spinner(f'Searching 60-day history for {ticker_to_run}...'):
        df, res = run_pattern_tracker(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"🏢 {res['ticker']} Analysis Dashboard")

        # --- TOP METRICS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Live Price", f"{res['price']:.2f}")
        
        if res['found']:
            m2.metric("Ceiling (Unfilled High)", f"{res['base_high']:.2f}")
            w_status = "CLEAN" if res['white_area_clean'] else "VIOLATED"
            m3.metric("White Area Integrity", w_status, 
                      delta=f"{res['violation_count']} Dips" if not res['white_area_clean'] else "No Dips", 
                      delta_color="normal" if res['white_area_clean'] else "inverse")
            
            m4.metric("Power Meter", f"{res['tr_atr_ratio']:.2f}x", 
                      delta=f"TR: {res['tr_val']:.1f}",
                      delta_color="normal" if res['momentum'] else "inverse")

            # --- ENTRY ADVICE BOX ---
            st.markdown("---")
            a1, a2 = st.columns([1, 2])
            with a1:
                st.subheader("💡 Entry Advice")
                if res['distance_pct'] < 2.5:
                    st.success(f"**GOLDEN ENTRY:** Price is {res['distance_pct']:.2f}% from ceiling. Unfilled orders are close.")
                elif res['distance_pct'] < 5.0:
                    st.info(f"**FAIR ENTRY:** Price is {res['distance_pct']:.2f}% from ceiling.")
                else:
                    st.warning(f"**OVEREXTENDED:** Price is {res['distance_pct']:.2f}% above ceiling. Risk is high.")
            with a2:
                st.subheader("🛡️ Strategy Bounds")
                st.write(f"**Pattern Anchor Date:** {res['base_date'].strftime('%Y-%m-%d')}")
                st.write(f"**Stop Loss (Base Low):** {res['base_low']:.2f}")

        # --- THE CHART ---
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='EMA 50'))
        
        if res['found']:
            # 1. Unfilled Order Candle (RED BOX)
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'],
                          fillcolor="rgba(255, 0, 0, 0.6)", line=dict(color="Red", width=2))
            
            # 2. UNFILLED ORDER TEXT LABEL
            fig.add_annotation(x=res['base_date'], y=res['base_high'], text="UNFILLED ORDER CANDLE",
                               showarrow=True, arrowhead=2, arrowcolor="red", ax=0, ay=-40,
                               bgcolor="red", font=dict(color="white"))

            # 3. LIGHT BLUE WHITE AREA (THE SKY)
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=df['High'].max() * 1.15,
                          fillcolor="rgba(173, 216, 230, 0.15)", line=dict(width=0))
            
            # 4. WATERMARK: "WHITE AREA"
            fig.add_annotation(
                x=df.index[int((len(df) + df.index.get_loc(res['base_date']))/2)], # Centered in the zone
                y=(res['base_high'] + df['High'].max()) / 2,
                text="WHITE AREA",
                font=dict(color="rgba(173, 216, 230, 0.25)", size=50),
                showarrow=False, textangle=-20
            )
            fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot", annotation_text=f"CEILING: {res['base_high']:.2f}")

        fig.update_layout(template="plotly_dark", height=650, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

        if not res['found']:
            st.error(f"❌ No valid 1-2-4 setup found for {res['ticker']} in 60d scan.")