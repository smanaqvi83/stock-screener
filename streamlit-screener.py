import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Hunter", layout="wide", page_icon="🎯")

# --- SIDEBAR ---
st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
manual_ticker = st.sidebar.text_input("Type Symbol (e.g. SYS, LUCK, NVDA)")
ticker_to_run = manual_ticker.upper() if manual_ticker else "SYS"

# --- THE HUNTER ENGINE ---
def run_strategic_hunter(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="70d", interval="1d") # 70d to ensure 60d scan range
    
    if df.empty: return None, {"found": False, "ticker": ticker_str}
    
    df['Size'] = df['High'] - df['Low']
    valid_setups = []

    # SCAN ENTIRE HISTORY FOR THE "PRISTINE ANCHOR"
    for i in range(2, len(df)-1):
        leg_in = df['Size'].iloc[i-1]
        base = df['Size'].iloc[i]
        leg_out = df['Size'].iloc[i+1]
        
        # Validation: 1-2-4 Rule
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
        # Pick the most robust setup (highest explosion ratio)
        best = max(valid_setups, key=lambda x: x['strength'])
        res.update({
            "found": True,
            "base_date": best['date'],
            "base_high": best['high'],
            "base_low": best['low'],
            "leg_out_high": best['leg_out_high'],
            "age": best['age_days'],
            "strength": best['strength']
        })
        
    return df, res

# --- MAIN DASHBOARD ---
if ticker_to_run:
    df, res = run_strategic_hunter(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"📊 Hunter View: {res['ticker']}")
        
        # Metrics Row
        if res['found']:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Live Price", f"{res['price']:.2f}")
            m2.metric("Pristine Age", f"{res['age']} Days", help="Number of days price has stayed above the ceiling")
            m3.metric("Anchor Ceiling", f"{res['base_high']:.2f}")
            m4.metric("Explosion", f"{res['strength']:.1f}x")
        
        # Chart
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        
        if res['found']:
            # Highlight Unfilled Anchor (Cyan/Yellow)
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[df.index.get_loc(res['base_date'])+1], 
                          y0=res['base_low'], y1=res['base_high'], 
                          fillcolor="rgba(0, 255, 255, 0.4)", line=dict(color="Yellow", width=3))
            
            # Pristine Shading (Localized)
            fig.add_shape(type="rect", x0=res['base_date'], x1=df.index[-1], 
                          y0=res['base_high'], y1=res['leg_out_high'],
                          fillcolor="rgba(0, 255, 0, 0.1)", line=dict(width=0))
            
            fig.add_annotation(x=res['base_date'], y=res['base_high'], text=f"PRISTINE ({res['age']}d)", showarrow=True, bgcolor="cyan")
            fig.add_hline(y=res['base_high'], line_color="red", line_dash="dot")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        if not res['found']:
            st.error(f"❌ No Pristine 1-2-4 Setups found in the scan range. Price may have violated previous anchors.")