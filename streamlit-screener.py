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
        return "v2.4.0-Production-Ready"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Pro", layout="wide", page_icon="📈")

# --- SIDEBAR: TICKER SELECTION ---
st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

psx_presets = ["PPL", "OGDC", "SYS", "LUCK", "HUBC", "ENGRO", "MCB", "EFERT"]
us_presets = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD"]

selected_preset = st.sidebar.selectbox("Preset List", psx_presets if market_choice == "PSX (Pakistan)" else us_presets)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol (e.g. OGDC)")

ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

st.sidebar.markdown("---")
st.sidebar.caption(f"**Build Hash:** `{COMMIT_ID}`")
st.sidebar.caption(f"**Instance Sync:** {SYNC_TIME}")

# --- ANALYSIS ENGINE ---
def run_pattern_tracker(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    
    # Fetch 60 days of daily data
    df = ticker_obj.history(period="60d", interval="1d")
    
    if df.empty:
        return None, {"ticker": ticker_str, "found": False, "candle_found": False}
    
    # Technical Calculations
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # THE SCOUT: Find the most recent "Base" candle
    best_base_idx = -1
    for i in range(len(df)-2, 2, -1):
        # A Base is smaller than the candle before and after it
        if df['Size'].iloc[i] < df['Size'].iloc[i-1] and df['Size'].iloc[i] < df['Size'].iloc[i+1]:
            best_base_idx = i
            break 

    res = {
        "ticker": ticker_str,
        "price": float(df['Close'].iloc[-1]),
        "tr_val": float(df['TR'].iloc[-1]),
        "atr_val": float(df['ATR'].iloc[-1]),
        "tr_atr_ratio": float(df['TR'].iloc[-1] / df['ATR'].iloc[-1]) if df['ATR'].iloc[-1] != 0 else 0,
        "candle_found": False
    }

    if best_base_idx != -1:
        res["candle_found"] = True
        res["base_date"] = df.index[best_base_idx]
        res["base_high"] = float(df['High'].iloc[best_base_idx])
        res["base_low"] = float(df['Low'].iloc[best_base_idx])
        res["leg_out_high"] = float(df['High'].iloc[best_base_idx + 1])
        
        # THE JUDGE: 1-2-4 Logic Test
        leg_in_sz = df['Size'].iloc[best_base_idx-1]
        base_sz = df['Size'].iloc[best_base_idx]
        leg_out_sz = df['Size'].iloc[best_base_idx+1]
        res["is_golden"] = (leg_in_sz >= 2*base_sz and leg_out_sz >= 4*base_sz)
        
        # White Area Check
        post_setup_df = df.iloc[best_base_idx+1:]
        violation_days = post_setup_df[post_setup_df['Low'] < res["base_high"]]
        res["white_area_clean"] = violation_days.empty
        res["violation_count"] = len(violation_days)
        res["distance_pct"] = ((res["price"] - res["base_high"]) / res["base_high"]) * 100
        
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    with st.spinner(f'Processing {ticker_to_run}...'):
        df, res = run_pattern_tracker(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"📊 {res['ticker']} Institutional Scan")

        # --- 1. TOP METRICS TABS ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Live Price", f"{res['price']:.2f}")
        
        if res["candle_found"]:
            col2.metric("Base Ceiling", f"{res['base_high']:.2f}")
            w_status = "CLEAN" if res['white_area_clean'] else "VIOLATED"
            col3.metric("White Area", w_status, delta=f"{res['violation_count']} Dips")
            col4.metric("TR/ATR Power", f"{res['tr_atr_ratio']:.2f}x", delta=f"ATR: {res['atr_val']:.1f}")

        # --- 2. THE CHART (Always First) ---
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Market'
        )])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.2), name='EMA 20'))
        
        if res["candle_found"]:
            # BRIGHT UNFILLED CANDLE HIGHLIGHT (Cyan box, Yellow border)
            fig.add_shape(type="rect", 
                          x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'], 
                          fillcolor="rgba(0, 255, 255, 0.4)", line=dict(color="Yellow", width=3))
            
            # WHITE AREA SHADING (Localized near the candle)
            fig.add_shape(type="rect", 
                          x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=res['leg_out_high'],
                          fillcolor="rgba(173, 216, 230, 0.25)", line=dict(width=0))
            
            # Label anchored to the candle
            fig.add_annotation(x=res['base_date'], y=res['base_low'], text="UNFILLED ORDER",
                               showarrow=True, arrowhead=2, arrowcolor="yellow", ay=45,
                               bgcolor="black", font=dict(color="yellow", size=12))
            
            # Ceiling Line
            fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, margin=dict(t=30, b=30))
        st.plotly_chart(fig, use_container_width=True)

        # --- 3. ENTRY ADVICE BOX ---
        if res["candle_found"]:
            st.markdown("---")
            adv_col, risk_col = st.columns(2)
            with adv_col:
                st.subheader("💡 Entry Advice")
                st.write(f"Distance from Ceiling: **{res['distance_pct']:.2f}%**")
                if res['distance_pct'] < 2.5:
                    st.success("🎯 **Value Entry Zone**: Price is sitting near institutional demand.")
                else:
                    st.warning("⚠️ **Overextended**: Wait for a pullback to the Red Ceiling.")
            
            with risk_col:
                st.subheader("🛡️ Risk Parameters")
                st.write(f"**Stop Loss (Base Low):** {res['base_low']:.2f}")
                st.write(f"**1-2-4 Strategy Match:** {'GOLDEN' if res['is_golden'] else 'POTENTIAL'}")
                if res['is_golden']: st.balloons()
        else:
            st.error(f"No Base Candle found for {res['ticker']} in 60-day history.")