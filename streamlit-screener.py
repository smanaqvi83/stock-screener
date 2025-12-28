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
        # Fetches the 7-character short hash from the local git repo
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v2.2.5-Final-Production"

COMMIT_ID = get_commit_id()
APP_VERSION = f"QuantFlow {COMMIT_ID}"
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

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

# Priority: Manual input overrides dropdown
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

st.sidebar.markdown("---")
st.sidebar.caption(f"**Build Hash:** `{COMMIT_ID}`")
st.sidebar.caption(f"**Version:** {APP_VERSION}")
st.sidebar.caption(f"**Instance Sync:** {SYNC_TIME}")

# --- ANALYSIS ENGINE ---
def run_pattern_tracker(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    
    # Fetch 60 days of data for history scan
    df = ticker_obj.history(period="60d", interval="1d")
    
    if df.empty:
        return None, {"ticker": ticker_str, "found": False, "candle_found": False}
    
    # Technical Indicators
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # UNIVERSAL SCOUT: Find the most recent "Base" (Potential Unfilled Order Candle)
    # A base is a candle smaller than its neighbors (Leg-In and Leg-Out)
    best_base_idx = -1
    for i in range(len(df)-2, 2, -1):
        if df['Size'].iloc[i] < df['Size'].iloc[i-1] and df['Size'].iloc[i] < df['Size'].iloc[i+1]:
            best_base_idx = i
            break 

    res = {
        "ticker": ticker_str,
        "price": float(df['Close'].iloc[-1]),
        "tr_val": float(df['TR'].iloc[-1]),
        "atr_val": float(df['ATR'].iloc[-1]),
        "tr_atr_ratio": float(df['TR'].iloc[-1] / df['ATR'].iloc[-1]) if df['ATR'].iloc[-1] != 0 else 0,
        "momentum": bool(df['TR'].iloc[-1] > df['ATR'].iloc[-1]),
        "candle_found": False
    }

    if best_base_idx != -1:
        res["candle_found"] = True
        res["base_date"] = df.index[best_base_idx]
        res["base_high"] = float(df['High'].iloc[best_base_idx])
        res["base_low"] = float(df['Low'].iloc[best_base_idx])
        
        # STRATEGY JUDGE: Strict 1-2-4 Test
        leg_in = df['Size'].iloc[best_base_idx-1]
        base = df['Size'].iloc[best_base_idx]
        leg_out = df['Size'].iloc[best_base_idx+1]
        
        res["is_golden"] = bool(leg_in >= 2*base and leg_out >= 4*base)
        res["ratio_out"] = float(leg_out / base) if base != 0 else 0
        
        # White Area Health Checks
        post_setup_df = df.iloc[best_base_idx+1:]
        violation_days = post_setup_df[post_setup_df['Low'] < res["base_high"]]
        res["white_area_clean"] = violation_days.empty
        res["violation_count"] = len(violation_days)
        res["distance_pct"] = float(((res["price"] - res["base_high"]) / res["base_high"]) * 100)
        
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    with st.spinner(f'Scanning {ticker_to_run} history for Unfilled Orders...'):
        df, res = run_pattern_tracker(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"🏢 {res['ticker']} Analysis Dashboard")

        # --- 1. TOP METRICS (Tabs) ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Live Price", f"{res['price']:.2f}")
        
        if res["candle_found"]:
            m2.metric("Base Ceiling", f"{res['base_high']:.2f}")
            w_status = "CLEAN" if res['white_area_clean'] else "VIOLATED"
            m3.metric("White Area", w_status, 
                      delta=f"{res['violation_count']} Dips" if not res['white_area_clean'] else "Perfect", 
                      delta_color="normal" if res['white_area_clean'] else "inverse")
        else:
            m2.metric("Base Ceiling", "N/A")
            m3.metric("White Area", "None Found")
            
        m4.metric("Power Meter (TR/ATR)", f"{res['tr_atr_ratio']:.2f}x", 
                  delta=f"TR: {res['tr_val']:.1f} | ATR: {res['atr_val']:.1f}",
                  delta_color="normal" if res['momentum'] else "inverse")

        # --- 2. THE CHART (Always First) ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price')])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='EMA 50'))
        
        if res["candle_found"]:
            # Mark the Unfilled Order Candle (Box)
            box_color = "Red" if res['is_golden'] else "Yellow"
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'], 
                          fillcolor=box_color, opacity=0.5, line=dict(color=box_color, width=2))
            
            # Label
            fig.add_annotation(x=res['base_date'], y=res['base_high'], text="UNFILLED ORDER CANDLE",
                               showarrow=True, arrowhead=2, arrowcolor=box_color, bgcolor=box_color, font=dict(color="white"))

            # White Area Shading (Light Blue)
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=df['High'].max() * 1.15,
                          fillcolor="rgba(173, 216, 230, 0.15)", line=dict(width=0))
            
            # Watermark
            fig.add_annotation(
                x=df.index[int((len(df) + df.index.get_loc(res['base_date']))/2)],
                y=(res['base_high'] + df['High'].max()) / 2,
                text="WHITE AREA",
                font=dict(color="rgba(173, 216, 230, 0.3)", size=45),
                showarrow=False, textangle=-15
            )
            # Ceiling Line
            fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot", annotation_text=f"CEILING: {res['base_high']:.2f}")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # --- 3. ENTRY ADVICE & RISK (Below Chart) ---
        if res["candle_found"]:
            st.markdown("---")
            a1, a2 = st.columns([1, 2])
            with a1:
                st.subheader("💡 Entry Advice")
                if res['distance_pct'] < 2.5:
                    st.success(f"**GOLDEN ENTRY:** Price is {res['distance_pct']:.2f}% from ceiling. Unfilled orders are close.")
                    if res['is_golden']: st.balloons()
                elif res['distance_pct'] < 5.0:
                    st.info(f"**FAIR ENTRY:** Price is {res['distance_pct']:.2f}% from ceiling.")
                else:
                    st.warning(f"**OVEREXTENDED:** Price is {res['distance_pct']:.2f}% above ceiling. Risk of pullback is high.")
            with a2:
                st.subheader("🛡️ Risk Parameters")
                st.write(f"**Pattern Anchor Date:** {res['base_date'].strftime('%Y-%m-%d')}")
                st.write(f"**Stop Loss (Base Low):** {res['base_low']:.2f}")
                st.write(f"**1-2-4 Strategy Match:** {'YES (Golden)' if res['is_golden'] else 'NO (Potential Base Only)'}")
                st.write(f"**Current Leg-Out Ratio:** {res['ratio_out']:.2f}x")

        else:
            st.error(f"❌ No Unfilled Order Candle (Base) found for {res['ticker']} in the last 60 days.")