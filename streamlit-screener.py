import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import subprocess

# --- VERSION & AUTH ---
def get_commit_id():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v3.4.0-Full-UI-Restored"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Hunter Pro", layout="wide", page_icon="🎯")

# --- SIDEBAR: AUTH & SELECTION ---
st.sidebar.header("System Status")
st.sidebar.success(f"**Build:** {COMMIT_ID}\n\n**Sync:** {SYNC_TIME}")

st.sidebar.header("Market Selection")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

# --- RESTORED DROPDOWN LOGIC ---
psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT", "PIBTL"]
us_list = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "ORCL"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol (e.g. OGDC)")

# Manual input takes priority
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

st.sidebar.markdown("---")
st.sidebar.caption(f"**Instance:** Strategic Hunter v3")

# --- THE ENGINE ---
def run_hunter_engine(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="75d", interval="1d")
    
    if df.empty: return None, {"found": False, "ticker": ticker_str}
    
    df['Size'] = df['High'] - df['Low']
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    valid_setups = []
    
    for i in range(2, len(df)-1):
        leg_in = df['Size'].iloc[i-1]
        base = df['Size'].iloc[i]
        leg_out = df['Size'].iloc[i+1]
        
        if base > 0 and leg_in >= 2*base and leg_out >= 4*base:
            base_high = float(df['High'].iloc[i])
            post_df = df.iloc[i+1:]
            violations = len(post_df[post_df['Low'] < base_high])
            
            valid_setups.append({
                "date": df.index[i],
                "high": base_high,
                "low": float(df['Low'].iloc[i]),
                "leg_out_high": float(df['High'].iloc[i+1]),
                "is_pristine": violations == 0,
                "violation_count": violations,
                "strength": leg_out / base,
                "age": len(post_df)
            })

    res = {"ticker": ticker_str, "price": float(df['Close'].iloc[-1]), "found": False}
    
    if valid_setups:
        res["found"] = True
        # Hunter selects Best (Pristine first, then Strongest)
        best = max(valid_setups, key=lambda x: (x['is_pristine'], x['strength']))
        res.update(best)
        res["distance_pct"] = ((res["price"] - res["high"]) / res["high"]) * 100
        
    return df, res

# --- MAIN UI ---
if ticker_to_run:
    with st.spinner(f'Hunter searching {ticker_to_run}...'):
        df, res = run_hunter_engine(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"🏢 {res['ticker']} Analysis Dashboard")
        
        # --- TOP METRIC BLOCKS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Live Price", f"{res['price']:.2f}")
        
        if res['found']:
            m2.metric("Anchor Ceiling", f"{res['high']:.2f}")
            m3.metric("Status", "PRISTINE" if res['is_pristine'] else "VIOLATED", 
                      delta=f"{res['violation_count']} Dips" if not res['is_pristine'] else "Clean")
            m4.metric("Anchor Age", f"{res['age']} Days")
            
            # --- STRATEGIC ALERT BOX ---
            if res['is_pristine'] and res['distance_pct'] < 2.5:
                st.success(f"🎯 **BUY ALERT:** Price is {res['distance_pct']:.2f}% from the {res['age']}-day Pristine Anchor.")
            elif not res['is_pristine']:
                st.error(f"⚠️ **VIOLATED SETUP:** Anchor tested {res['violation_count']} times. Not Pristine.")
        else:
            m2.metric("Anchor Ceiling", "None")
            m3.metric("Status", "N/A")
            m4.metric("Anchor Age", "N/A")
            st.warning("❌ No valid 1-2-4 setup found in history.")

        # --- THE CHART ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20'))
        
        if res['found']:
            # Box Color Logic
            box_fill = "rgba(0, 255, 255, 0.4)" if res['is_pristine'] else "rgba(255, 165, 0, 0.3)"
            fig.add_shape(type="rect", x0=res['date'], x1=df.index[df.index.get_loc(res['date'])+1], 
                          y0=res['low'], y1=res['high'], fillcolor=box_fill, line=dict(color="Yellow", width=2))
            
            # White Area (Localized)
            fig.add_shape(type="rect", x0=res['date'], x1=df.index[-1], y0=res['high'], y1=res['leg_out_high'],
                          fillcolor="rgba(173, 216, 230, 0.15)", line=dict(width=0))
            
            fig.add_hline(y=res['high'], line_color="red", line_dash="dot")
            fig.add_annotation(x=res['date'], y=res['high'], text=f"ANCHOR ({res['age']}d)", showarrow=True, bgcolor="cyan")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)