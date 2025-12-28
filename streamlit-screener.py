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
        return "v4.8.0-Table-Restored"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

st.set_page_config(page_title="QuantFlow Hunter Pro", layout="wide", page_icon="🎯")

# --- 2. SIDEBAR ---
st.sidebar.header("System Status")
st.sidebar.success(f"**Build:** {COMMIT_ID}\n**Sync:** {SYNC_TIME}")

market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT", "PIBTL"]
us_list = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "ORCL"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

# --- 3. THE ENGINE ---
def run_hunter_engine(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    ticker_obj = yf.Ticker(ticker_str)
    df = ticker_obj.history(period="120d", interval="1d") 
    
    if df.empty: return None, [], None
    
    # Technical Indicators
    df['EMA30'] = df['Close'].ewm(span=30, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
    
    all_zones = []
    for i in range(2, len(df)-1):
        l1_size, l2_size, l4_size = df['Size'].iloc[i-1], df['Size'].iloc[i], df['Size'].iloc[i+1]
        
        if l2_size > 0 and l1_size >= 1.5*l2_size and l4_size >= 2*l2_size:
            b_high, b_low = float(df['High'].iloc[i]), float(df['Low'].iloc[i])
            post_df = df.iloc[i+1:]
            violations = len(post_df[post_df['Low'] < b_high])
            
            is_124 = l4_size >= 4*l2_size
            color = "rgba(0, 255, 255, 0.6)" if (is_124 and violations == 0) else "rgba(255, 165, 0, 0.4)"
            
            all_zones.append({
                "Date": df.index[i].strftime('%Y-%m-%d'),
                "High (Ceiling)": b_high,
                "Low (Floor)": b_low,
                "Type": "PRISTINE" if violations == 0 else "VIOLATED",
                "Color": color,
                "Ratio": f"1:{round(l1_size/l2_size,1)} | 4:{round(l4_size/l2_size,1)}",
                "is_124": is_124,
                "Age": len(post_df),
                "Violations": violations,
                # Technical values for internal logic
                "l1_idx": df.index[i-1], "l4_idx": df.index[i+1],
                "l1_h": float(df['High'].iloc[i-1]), "l4_h": float(df['High'].iloc[i+1])
            })

    ctx = {
        "price": df['Close'].iloc[-1],
        "ema_status": "BULLISH" if df['EMA30'].iloc[-1] > df['EMA50'].iloc[-1] else "BEARISH",
        "tr_atr": df['TR'].iloc[-1] / df['ATR'].iloc[-1],
        "vol_ratio": df['Volume'].iloc[-1] / df['Vol_Avg'].iloc[-1] if df['Vol_Avg'].iloc[-1] > 0 else 0
    }
    return df, all_zones, ctx

# --- 4. MAIN UI ---
if ticker_to_run:
    df, zones, ctx = run_hunter_engine(ticker_to_run, market_choice == "PSX (Pakistan)")
    
    if df is not None:
        st.header(f"📊 {ticker_to_run} Strategic Dashboard")
        
        # --- METRIC COLUMNS ---
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Live Price", f"{ctx['price']:.2f}")
        m2.metric("Trend (30/50)", ctx['ema_status'])
        m3.metric("Power (TR/ATR)", f"{ctx['tr_atr']:.2f}x")
        m4.metric("Vol Multiplier", f"{ctx['vol_ratio']:.2f}x")
        
        pristine_zones = [z for z in zones if z['Type'] == "PRISTINE" and z['is_124']]
        if pristine_zones:
            best = max(pristine_zones, key=lambda x: x['Age'])
            m5.metric("Best Anchor Age", f"{best['Age']}d")
            
            # --- VERDICT ---
            st.markdown("---")
            dist = ((ctx['price'] - best['High (Ceiling)']) / best['High (Ceiling)']) * 100
            v1, v2 = st.columns([1, 2])
            if dist < 3.5 and ctx['ema_status'] == "BULLISH":
                v1.success("🛡️ VERDICT: BUY AUTHORIZED")
                v2.success(f"Strategy: Price is testing the Unfilled Order Candle from {best['Date']}.")
            else:
                v1.info("🛡️ VERDICT: MONITORING")
                v2.write(f"Wait for pullback. Nearest Pristine Anchor is {dist:.1f}% away.")
        else:
            m5.metric("Anchor", "None Found")

        # --- THE CHART ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA30'], line=dict(color='#00d1ff', width=2), name='EMA 30'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='#ff9900', width=2), name='EMA 50'))

        for z in zones:
            # Drawing zones
            fig.add_shape(type="rect", x0=z['Date'], x1=df.index[df.index.get_loc(pd.to_datetime(z['Date']))+1], 
                          y0=z['Low (Floor)'], y1=z['High (Ceiling)'], fillcolor=z['Color'], line=dict(width=1))
            
            # Annotations: 1, 2, 4
            fig.add_annotation(x=z['l1_idx'], y=z['l1_h'], text="1", showarrow=False, font=dict(color="white"), yshift=10)
            fig.add_annotation(x=z['Date'], y=z['High (Ceiling)'], text="2", showarrow=False, font=dict(color="cyan", size=14), yshift=15)
            fig.add_annotation(x=z['l4_idx'], y=z['l4_h'], text="4", showarrow=False, font=dict(color="yellow", size=16), yshift=20)

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- RESTORED AUDIT TABLE ---
        st.subheader("📋 Unfilled Order Candle Audit Log")
        if zones:
            # Displaying the table with only relevant columns for the user
            zone_table = pd.DataFrame(zones).sort_values(by="Date", ascending=False)
            st.table(zone_table[['Date', 'High (Ceiling)', 'Type', 'Ratio', 'Age', 'Violations']])
        else:
            st.info("No institutional bases detected in this lookback period.")