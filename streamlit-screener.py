import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- VERSION & GIT LOGIC (RESTORED) ---
def get_commit_id():
    try:
        # Fetches the short hash from your local git environment
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v3.2.0-Hunter-Auth"

COMMIT_ID = get_commit_id()
APP_VERSION = f"QuantFlow {COMMIT_ID}"
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Hunter", layout="wide", page_icon="🎯")

# --- SIDEBAR ---
st.sidebar.header("System Authentication")
st.sidebar.info(f"**Build Hash:** `{COMMIT_ID}`\n\n**Sync:** {SYNC_TIME}")

st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
manual_ticker = st.sidebar.text_input("Type Symbol (e.g. SYS, PPL, NVDA)")
ticker_to_run = manual_ticker.upper() if manual_ticker else "SYS"

st.sidebar.markdown("---")
st.sidebar.caption(f"**Instance:** {APP_VERSION}")

# --- THE HUNTER ENGINE ---
def run_strategic_hunter(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="75d", interval="1d") 
    
    if df.empty: return None, {"found": False, "ticker": ticker_str}
    
    df['Size'] = df['High'] - df['Low']
    valid_setups = []

    # SCAN ENTIRE HISTORY FOR THE "PRISTINE ANCHOR"
    for i in range(2, len(df)-1):
        leg_in = df['Size'].iloc[i-1]
        base = df['Size'].iloc[i]
        leg_out = df['Size'].iloc[i+1]
        
        # Validation: Strict 1-2-4 Rule
        if base > 0 and leg_in >= 2*base and leg_out >= 4*base:
            base_high = float(df['High'].iloc[i])
            
            # CHECK PRISTINE STATUS: Did price ever touch/fall below base_high?
            post_setup_df = df.iloc[i+1:]
            violation_days = post_setup_df[post_setup_df['Low'] < base_high]
            
            if len(violation_days) == 0:
                valid_setups.append({
                    "date": df.index[i],
                    "high": base_high,
                    "low": float(df['Low'].iloc[i]),
                    "leg_out_high": float(df['High'].iloc[i+1]),
                    "strength": leg_out / base,
                    "age_days": len(post_setup_df)
                })

    res = {"ticker": ticker_str, "price": float(df['Close'].iloc[-1]), "found": False}
    
    if valid_setups:
        # Pick the strongest setup based on explosion ratio
        best = max(valid_setups, key=lambda x: x['strength'])
        res.update({
            "found": True,
            "base_date": best['date'],
            "base_high": best['high'],
            "base_low": best['low'],
            "leg_out_high": best['leg_out_high'],
            "age": best['age_days'],
            "strength": best['strength'],
            "distance_pct": ((res["price"] - best['high']) / best['high']) * 100
        })
        
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    df, res = run_strategic_hunter(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"📊 Hunter View: {res['ticker']}")
        
        if res['found']:
            # TOP ALERT BANNER
            if res['distance_pct'] < 2.5:
                st.success(f"🚨 **PROXIMITY ALERT:** Price is {res['distance_pct']:.2f}% from the {res['age']}-day Pristine Anchor. High Probability Area.")
            else:
                st.warning(f"⏳ **MONITORING:** Price is {res['distance_pct']:.2f}% above the Anchor. Entry is overextended.")

            # Metrics Row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Live Price", f"{res['price']:.2f}")
            m2.metric("Pristine Age", f"{res['age']} Days")
            m3.metric("Anchor Ceiling", f"{res['base_high']:.2f}")
            m4.metric("Explosion Ratio", f"{res['strength']:.1f}x")
        
        # Chart
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        
        if res['found']:
            # Highlight Anchor Candle (Cyan/Yellow)
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'], 
                          fillcolor="rgba(0, 255, 255, 0.4)", line=dict(color="Yellow", width=3))
            
            # Localized White Area Shading (No Watermark)
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=res['leg_out_high'],
                          fillcolor="rgba(0, 255, 0, 0.1)", line=dict(width=0))
            
            fig.add_annotation(x=res['base_date'], y=res['base_high'], text=f"PRISTINE ANCHOR ({res['age']}d)", showarrow=True, bgcolor="cyan")
            fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- TRADE LOGIC & WAIT TIME ---
        if res['found']:
            st.markdown("---")
            col_wait, col_exit = st.columns(2)
            with col_wait:
                st.subheader("📅 Trade Duration")
                # Wait time based on Age
                wait_days = 15 if res['age'] > 30 else 7
                st.write(f"Based on the **{res['age']}-day age** of this anchor, the typical duration for this trade is **{wait_days} to 20 trading days**.")
            
            with col_exit:
                st.subheader("🎯 Exit Strategy")
                st.write(f"**Target (+10%):** {res['price'] * 1.10:.2f}")
                st.error(f"**Immediate Stop Loss:** {res['base_low']:.2f}")