import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- 1. SYSTEM AUTHENTICATION & VERSIONING ---
def get_commit_id():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v3.9.5-Final-Full-Logic"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="QuantFlow Hunter Pro", layout="wide", page_icon="🎯")

# --- 3. SIDEBAR: NAVIGATION & STATUS ---
st.sidebar.header("System Status")
st.sidebar.success(f"**Build Hash:** `{COMMIT_ID}`\n\n**Sync Time:** {SYNC_TIME}")

market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT", "PIBTL"]
us_list = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "ORCL"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol (e.g. OGDC)")

ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

st.sidebar.markdown("---")
st.sidebar.caption("Institutional 1-2-4 Strategy Engine")

# --- 4. THE HUNTER ENGINE ---
def run_hunter_engine(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    # Fetch 75 days to allow for 14-day ATR and 50-day EMA calculations
    df = ticker_obj.history(period="75d", interval="1d")
    
    if df.empty: return None, {"found": False, "ticker": ticker_str}
    
    # Technical Indicators
    df['Size'] = df['High'] - df['Low']
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # TR and ATR (14 Day)
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # Volume Average (20 Day)
    df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
    
    valid_setups = []
    # SCAN ENTIRE HISTORY FOR PRISTINE ANCHORS
    for i in range(2, len(df)-1):
        leg_in, base, leg_out = df['Size'].iloc[i-1], df['Size'].iloc[i], df['Size'].iloc[i+1]
        
        # Validation: 1-2-4 Rule
        if base > 0 and leg_in >= 2*base and leg_out >= 4*base:
            base_high = float(df['High'].iloc[i])
            post_df = df.iloc[i+1:]
            
            # Check for White Area Violations (Lowest price since base)
            violations = len(post_df[post_df['Low'] < base_high])
            
            if violations == 0: # PRISTINE ONLY
                valid_setups.append({
                    "date": df.index[i],
                    "high": base_high,
                    "low": float(df['Low'].iloc[i]),
                    "leg_out_high": float(df['High'].iloc[i+1]),
                    "strength": leg_out / base,
                    "age": len(post_df)
                })

    # Current Market Context
    cur_tr = df['TR'].iloc[-1]
    cur_atr = df['ATR'].iloc[-1]
    cur_vol = df['Volume'].iloc[-1]
    cur_vol_avg = df['Vol_Avg'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]

    res = {
        "ticker": ticker_str,
        "price": float(df['Close'].iloc[-1]),
        "found": False,
        "tr": cur_tr,
        "atr": cur_atr,
        "tr_atr": cur_tr / cur_atr,
        "vol_ratio": cur_vol / cur_vol_avg if cur_vol_avg > 0 else 0,
        "ema_bullish": ema20 > ema50
    }
    
    if valid_setups:
        res["found"] = True
        # Pick strongest explosion setup
        best = max(valid_setups, key=lambda x: x['strength'])
        res.update(best)
        res["dist"] = ((res["price"] - res["high"]) / res["high"]) * 100
        
        # RELIABILITY SCORE (0-100)
        score = 40 # Base for being pristine
        score += min(res['age'], 30) 
        if res['tr_atr'] > 1.0: score += 15
        if res['vol_ratio'] > 1.0: score += 15
        res["score"] = score

    return df, res

# --- 5. MAIN DASHBOARD UI ---
if ticker_to_run:
    with st.spinner(f"Hunter Engine scanning {ticker_to_run}..."):
        df, res = run_hunter_engine(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"🏢 {res['ticker']} Strategic Dashboard")
        
        # --- TOP METRIC BLOCKS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Live Price", f"{res['price']:.2f}")
        
        # Combined Power Meter (TR/ATR)
        c2.metric("Power Meter (TR/ATR)", f"{res['tr_atr']:.2f}x", 
                  delta=f"TR: {res['tr']:.1f} | ATR: {res['atr']:.1f}",
                  delta_color="normal" if res['tr_atr'] > 1 else "inverse")
        
        # Volume Multiplier
        c3.metric("Volume Multiplier", f"{res['vol_ratio']:.2f}x", 
                  delta=f"Ratio vs 20D Avg")
        
        if res['found']:
            c4.metric("Reliability Score", f"{res['score']}/100", 
                      delta=f"Age: {res['age']}d")

        # --- 6. FINAL VERDICT (Will it work?) ---
        st.markdown("---")
        if res['found']:
            v_col1, v_col2 = st.columns([1, 2])
            
            # Logic for Entry Authorization
            is_valid_entry = res['dist'] < 3.0
            has_momentum = res['tr_atr'] > 0.9 and res['vol_ratio'] > 0.8
            is_high_reliability = res['score'] > 65
            
            if is_valid_entry and has_momentum and is_high_reliability:
                v_col1.error("🛡️ VERDICT: BUY AUTHORIZED")
                v_col2.success(f"Confirmed: Entry at {res['price']:.2f} is within the institutional buy zone ({res['dist']:.1f}% from ceiling). Volume and TR confirm institutional activity.")
            elif is_valid_entry:
                v_col1.warning("🛡️ VERDICT: WATCHING")
                v_col2.info("Price is in range, but momentum (TR or Volume) is lacking. Wait for an explosive green candle to confirm the 'bounce'.")
            else:
                v_col1.info("🛡️ VERDICT: DO NOT CHASE")
                v_col2.write(f"This setup is high quality, but price is {res['dist']:.1f}% above the ceiling. Wait for a pullback to {res['high']:.2f}.")
        
        # --- 7. THE CHART ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='EMA 50'))

        if res['found']:
            # Highlight Unfilled Anchor
            fig.add_shape(type="rect", x0=res['date'], x1=df.index[df.index.get_loc(res['date'])+1], 
                          y0=res['low'], y1=res['high'], 
                          fillcolor="rgba(0, 255, 255, 0.4)", line=dict(color="Yellow", width=3))
            
            # White Area Shading
            fig.add_shape(type="rect", x0=res['date'], x1=df.index[-1], y0=res['high'], y1=res['leg_out_high'],
                          fillcolor="rgba(173, 216, 230, 0.2)", line=dict(width=0))
            
            fig.add_hline(y=res['high'], line_color="red", line_dash="dot")
            
            # Visual Buy Arrow on Chart
            if res['dist'] < 3.0 and res['tr_atr'] > 0.9:
                fig.add_annotation(x=df.index[-1], y=res['price'], text="🟢 ENTRY ZONE",
                                   showarrow=True, arrowhead=2, bgcolor="green", font=dict(color="white"))

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # --- 8. TRADE PARAMETERS ---
        if res['found']:
            st.markdown("---")
            p1, p2, p3 = st.columns(3)
            p1.write(f"**Anchor Date:** {res['date'].strftime('%Y-%m-%d')}")
            p2.write(f"**Stop Loss:** {res['low']:.2f}")
            p3.write(f"**Target (+10%):** {res['price'] * 1.10:.2f}")