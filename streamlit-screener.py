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
        return subprocess.check_output(['rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except:
        return "v5.0.0-Stable-Final"

COMMIT_ID = get_commit_id()
SYNC_TIME = datetime.now().strftime("%H:%M:%S")

st.set_page_config(page_title="QuantFlow Hunter Pro", layout="wide", page_icon="🎯")

# --- 2. SIDEBAR NAVIGATION ---
st.sidebar.header("System Status")
st.sidebar.success(f"**Build:** {COMMIT_ID}\n**Sync:** {SYNC_TIME}")

market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])
psx_list = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL", "OGDC", "MCB", "EFERT", "PIBTL"]
us_list = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "ORCL"]

selected_preset = st.sidebar.selectbox("Preset List", psx_list if market_choice == "PSX (Pakistan)" else us_list)
manual_ticker = st.sidebar.text_input("OR Type Manual Symbol")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_preset

# --- 3. THE HUNTER ENGINE ---
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
    # Scan for 1-2-4 patterns
    for i in range(2, len(df)-1):
        l1_size, l2_size, l4_size = df['Size'].iloc[i-1], df['Size'].iloc[i], df['Size'].iloc[i+1]
        
        if l2_size > 0 and l1_size >= 1.5*l2_size and l4_size >= 2*l2_size:
            b_high, b_low = float(df['High'].iloc[i]), float(df['Low'].iloc[i])
            post_df = df.iloc[i+1:]
            violations = len(post_df[post_df['Low'] < b_high])
            
            is_124 = l4_size >= 4*l2_size
            # Pristine = Cyan, Violated = Orange
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
        st.header(f"📊 {ticker_to_run} Interactive Hunter Pro")
        
        # --- TOP METRIC BLOCKS ---
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Live Price", f"{ctx['price']:.2f}")
        m2.metric("Trend (30/50)", ctx['ema_status'])
        m3.metric("Power (TR/ATR)", f"{ctx['tr_atr']:.2f}x")
        m4.metric("Vol Multiplier", f"{ctx['vol_ratio']:.2f}x")
        
        pristine = [z for z in zones if z['Type'] == "PRISTINE" and z['is_124']]
        if pristine:
            best = max(pristine, key=lambda x: x['Age'])
            m5.metric("Best Anchor Age", f"{best['Age']}d")
            
            # --- FINAL VERDICT ---
            st.markdown("---")
            dist = ((ctx['price'] - best['High (Ceiling)']) / best['High (Ceiling)']) * 100
            v1, v2 = st.columns([1, 2])
            if dist < 3.5 and ctx['ema_status'] == "BULLISH":
                v1.success("🛡️ VERDICT: BUY AUTHORIZED")
                v2.success(f"Targeting Unfilled Candle at {best['High (Ceiling)']} (Dist: {dist:.1f}%).")
            else:
                v1.info("🛡️ VERDICT: MONITORING")
                v2.write(f"Wait for pullback. Nearest Pristine Anchor is {dist:.1f}% away.")
        else:
            m5.metric("Anchor", "None Found")

        # --- INTERACTIVE INSPECTOR ---
        st.markdown("---")
        selected_date = None
        if zones:
            zone_dates = [z['Date'] for z in zones]
            selected_date = st.selectbox("🎯 Unfilled Candle Inspector: Pick a date to zoom", zone_dates)
            current_z = next(z for z in zones if z['Date'] == selected_date)
            st.caption(f"Details: Ratio {current_z['Ratio']} | Age {current_z['Age']}d | {current_z['Type']}")

        # --- THE CHART ---
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA30'], line=dict(color='#00d1ff', width=2), name='EMA 30'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='#ff9900', width=2), name='EMA 50'))

        # Safe Shape Drawing
        for z in zones:
            try:
                z_dt = pd.to_datetime(z['Date']).tz_localize(df.index.tz) if df.index.tz else pd.to_datetime(z['Date'])
                idx_pos = df.index.get_loc(z_dt)
                x1_val = df.index[idx_pos + 1] if idx_pos < len(df)-1 else df.index[idx_pos] + pd.Timedelta(days=1)
                
                is_sel = (z['Date'] == selected_date)
                fig.add_shape(type="rect", x0=z['Date'], x1=x1_val, y0=z['Low (Floor)'], y1=z['High (Ceiling)'], 
                              fillcolor=z['Color'], line=dict(width=3 if is_sel else 1, color="white" if is_sel else None))
                
                # Annotations: 1, 2, 4
                fig.add_annotation(x=z['l1_idx'], y=z['l1_h'], text="1", showarrow=False, font=dict(color="white"))
                fig.add_annotation(x=z['Date'], y=z['High (Ceiling)'], text="2", showarrow=False, font=dict(color="cyan", size=14), yshift=15)
                fig.add_annotation(x=z['l4_idx'], y=z['l4_h'], text="4", showarrow=False, font=dict(color="yellow", size=16), yshift=20)
            except: continue

        # Auto-Zoom Logic
        if selected_date:
            sel_dt = pd.to_datetime(selected_date)
            fig.update_xaxes(range=[sel_dt - pd.Timedelta(days=5), sel_dt + pd.Timedelta(days=20)])

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- AUDIT LOG TABLE ---
        st.subheader("📋 Unfilled Order Candle Audit Log")
        if zones:
            zone_table = pd.DataFrame(zones).sort_values(by="Date", ascending=False)
            st.table(zone_table[['Date', 'High (Ceiling)', 'Type', 'Ratio', 'Age', 'Violations']])