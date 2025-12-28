import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- VERSION ---
COMMIT_ID = "v3.0.0-Strategic-Hunter"
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Hunter", layout="wide", page_icon="🎯")

# --- SIDEBAR ---
st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
manual_ticker = st.sidebar.text_input("Type Symbol (e.g. OGDC, PPL, NVDA)")
ticker_to_run = manual_ticker.upper() if manual_ticker else "PPL"

st.sidebar.markdown("---")
st.sidebar.caption(f"**Engine:** Strategic Hunter")
st.sidebar.caption(f"**Build Hash:** `{COMMIT_ID}`")

# --- THE HUNTER ENGINE ---
def run_strategic_hunter(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="60d", interval="1d")
    
    if df.empty: return None, {"found": False}
    
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()

    valid_setups = []

    # SCAN THE ENTIRE HISTORY (Not just the most recent)
    for i in range(2, len(df)-1):
        leg_in = df['Size'].iloc[i-1]
        base = df['Size'].iloc[i]
        leg_out = df['Size'].iloc[i+1]
        
        # 1. Check strict 1-2-4 Validation
        if leg_in >= 2*base and leg_out >= 4*base:
            base_high = float(df['High'].iloc[i])
            
            # 2. Check if White Area has remained EMPTY (Price stayed above base_high)
            post_setup_df = df.iloc[i+1:]
            violation_count = len(post_setup_df[post_setup_df['Low'] < base_high])
            
            if violation_count == 0:  # PRISTINE WHITE AREA
                valid_setups.append({
                    "idx": i,
                    "date": df.index[i],
                    "high": base_high,
                    "low": float(df['Low'].iloc[i]),
                    "leg_out_high": float(df['High'].iloc[i+1]),
                    "strength": leg_out / base
                })

    res = {"ticker": ticker_str, "price": float(df['Close'].iloc[-1]), "found": False}
    
    if valid_setups:
        # Pick the one with the strongest "Leg Out" explosion
        best = max(valid_setups, key=lambda x: x['strength'])
        res.update({
            "found": True,
            "base_date": best['date'],
            "base_high": best['high'],
            "base_low": best['low'],
            "leg_out_high": best['leg_out_high'],
            "strength": best['strength'],
            "tr_atr": float(df['TR'].iloc[-1] / df['ATR'].iloc[-1])
        })
        res["distance_pct"] = ((res["price"] - res["base_high"]) / res["base_high"]) * 100
        
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    df, res = run_strategic_hunter(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        if res['found']:
            st.header(f"🎯 Strategic Setup Found: {res['ticker']}")
            
            # Top Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Live Price", f"{res['price']:.2f}")
            m2.metric("Hunter Ceiling", f"{res['base_high']:.2f}")
            m3.metric("White Area", "PRISTINE", delta="0 Violations")
            m4.metric("Explosion Ratio", f"{res['strength']:.1f}x")

            # The Chart
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
            
            # Highlight the Setup
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'], 
                          fillcolor="rgba(0, 255, 255, 0.5)", line=dict(color="Yellow", width=3))
            
            # Specialized Shading for the "Empty" White Area
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=res['leg_out_high'],
                          fillcolor="rgba(0, 255, 0, 0.1)", line=dict(width=0))
            
            fig.add_annotation(x=res['base_date'], y=res['base_high'], text="UNFILLED ANCHOR", showarrow=True, bgcolor="cyan")
            fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # Entry Logic
            st.info(f"💡 **Strategy:** This setup was found on **{res['base_date'].strftime('%Y-%m-%d')}**. Since then, the price has **NEVER** returned to the ceiling. This is a high-conviction institutional zone.")
        else:
            st.error(f"❌ No pristine 1-2-4 setups found for {res['ticker']} in 60 days. Current bases are too weak or already violated.")