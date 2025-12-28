import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- 1. SYSTEM AUTHENTICATION ---
def get_commit_id():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v4.4.0-Zone-Mapper-Active"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

st.set_page_config(page_title="QuantFlow Zone Mapper", layout="wide", page_icon="🎯")

# --- 2. SIDEBAR ---
st.sidebar.header("System Status")
st.sidebar.success(f"**Build:** {COMMIT_ID}\n**Sync:** {SYNC_TIME}")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
ticker_to_run = st.sidebar.text_input("Ticker Symbol", value="SYS").upper()

# --- 3. THE ZONE ENGINE ---
def run_zone_mapper(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="120d", interval="1d") 
    
    if df.empty: return None, []
    
    df['Size'] = df['High'] - df['Low']
    all_zones = []

    # SCAN FOR EVERY POTENTIAL UNFILLED ORDER CANDLE
    for i in range(2, len(df)-1):
        leg_in, base, leg_out = df['Size'].iloc[i-1], df['Size'].iloc[i], df['Size'].iloc[i+1]
        
        # We look for the "Structure": Leg In -> Base -> Leg Out
        if base > 0 and leg_in >= 1.5*base and leg_out >= 2*base:
            base_high = float(df['High'].iloc[i])
            base_low = float(df['Low'].iloc[i])
            
            # CHECK FOR VIOLATION (Is it still unfilled?)
            post_df = df.iloc[i+1:]
            violations = len(post_df[post_df['Low'] < base_high])
            
            # Categorize the Zone
            if leg_out >= 4*base and violations == 0:
                zone_type = "PRISTINE (1-2-4)"
                color = "rgba(0, 255, 255, 0.6)" # Cyan
            elif leg_out >= 4*base and violations > 0:
                zone_type = "VIOLATED (1-2-4)"
                color = "rgba(255, 165, 0, 0.4)" # Orange
            else:
                zone_type = "WEAK BASE"
                color = "rgba(128, 128, 128, 0.3)" # Gray

            all_zones.append({
                "date": df.index[i],
                "high": base_high,
                "low": base_low,
                "type": zone_type,
                "color": color,
                "leg_out": leg_out / base,
                "violations": violations
            })

    return df, all_zones

# --- 4. MAIN UI ---
if ticker_to_run:
    df, zones = run_zone_mapper(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"🎯 Zone Mapper: {ticker_to_run}")
        
        # Summary Row
        c1, c2, c3 = st.columns(3)
        c1.metric("Live Price", f"{df['Close'].iloc[-1]:.2f}")
        c2.metric("Total Zones Found", len(zones))
        pristine_count = len([z for z in zones if "PRISTINE" in z['type']])
        c3.metric("Pristine Anchors", pristine_count)

        # --- THE CHART ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])

        # PLOT EVERY ZONE FOUND
        for z in zones:
            # Draw the box on the candle
            fig.add_shape(type="rect", x0=z['date'], x1=df.index[df.index.get_loc(z['date'])+1], 
                          y0=z['low'], y1=z['high'], fillcolor=z['color'], line=dict(width=1))
            
            # Extend the "Demand Zone" line to the right
            fig.add_shape(type="line", x0=z['date'], x1=df.index[-1], y0=z['high'], y1=z['high'],
                          line=dict(color=z['color'], width=1, dash="dot"))

        fig.update_layout(template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- ZONE AUDIT LOG ---
        st.subheader("📋 Unfilled Candle Audit Log")
        if zones:
            zone_df = pd.DataFrame(zones).sort_values(by="date", ascending=False)
            st.table(zone_df[['date', 'high', 'type', 'leg_out', 'violations']])
        else:
            st.info("No institutional bases detected in this 120-day period.")