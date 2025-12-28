import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- VERSION ---
COMMIT_ID = "v3.1.0-Always-On-Graph"
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Hunter", layout="wide", page_icon="🎯")

# --- SIDEBAR ---
st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
manual_ticker = st.sidebar.text_input("Type Symbol (e.g. PIBTL, OGDC, PPL)")
ticker_to_run = manual_ticker.upper() if manual_ticker else "PIBTL"

st.sidebar.markdown("---")
st.sidebar.caption(f"**Engine:** Strategic Hunter")
st.sidebar.caption(f"**Sync:** {SYNC_TIME}")

# --- THE HUNTER ENGINE ---
def run_strategic_hunter(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    # Fetching slightly more data (70d) to ensure we have room for indicators
    df = ticker_obj.history(period="70d", interval="1d")
    
    if df.empty: return None, {"found": False, "ticker": ticker_str}
    
    df['Size'] = df['High'] - df['Low']
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()

    valid_setups = []

    # SCAN ENTIRE HISTORY FOR PRISTINE 1-2-4
    for i in range(2, len(df)-1):
        leg_in = df['Size'].iloc[i-1]
        base = df['Size'].iloc[i]
        leg_out = df['Size'].iloc[i+1]
        
        # Check strict 1-2-4 Validation
        if base > 0 and leg_in >= 2*base and leg_out >= 4*base:
            base_high = float(df['High'].iloc[i])
            
            # Check for White Area Violations (Price falling below base_high)
            post_setup_df = df.iloc[i+1:]
            violation_days = post_setup_df[post_setup_df['Low'] < base_high]
            
            if len(violation_days) == 0:
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
        best = max(valid_setups, key=lambda x: x['strength'])
        res.update({
            "found": True,
            "base_date": best['date'],
            "base_high": best['high'],
            "base_low": best['low'],
            "leg_out_high": best['leg_out_high'],
            "strength": best['strength'],
            "distance_pct": ((res["price"] - best['high']) / best['high']) * 100
        })
        
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    df, res = run_strategic_hunter(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"📊 Market View: {res['ticker']}")
        
        # Create Chart Object
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"
        )])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20'))

        # IF SETUP FOUND: Add visual overlays
        if res['found']:
            # Highlight Unfilled Anchor
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'], 
                          fillcolor="rgba(0, 255, 255, 0.5)", line=dict(color="Yellow", width=3))
            
            # Localized White Area
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=res['leg_out_high'],
                          fillcolor="rgba(0, 255, 0, 0.15)", line=dict(width=0))
            
            fig.add_annotation(x=res['base_date'], y=res['base_high'], text="PRISTINE ANCHOR", showarrow=True, bgcolor="cyan")
            
            # Show Metrics only if found
            m1, m2, m3 = st.columns(3)
            m1.metric("Live Price", f"{res['price']:.2f}")
            m2.metric("Ceiling", f"{res['base_high']:.2f}")
            m3.metric("Distance", f"{res['distance_pct']:.2f}%")
        
        # Display Chart (Always)
        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # Show status message below graph
        if res['found']:
            st.success(f"✅ **Pristine Setup Identified:** The unfilled order candle on {res['base_date'].strftime('%Y-%m-%d')} has not been violated.")
        else:
            st.error(f"❌ **No Pristine 1-2-4 Setups Found:** PIBTL (or selected stock) either lacks the 4x explosion ratio or the price has dipped back into the base high within the last 60 days.")
            st.info("💡 **Observation:** Look at the chart above. For a valid setup, you need a very small candle (Base) followed by a massive green candle that is 4 times its size, with the price never falling back to that base high.")