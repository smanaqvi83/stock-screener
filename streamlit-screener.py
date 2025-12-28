import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow Pro Dashboard", layout="wide")
st.title("📊 QuantFlow: 1-2-4 Strategy & Momentum Dashboard")

# --- SIDEBAR ---
st.sidebar.header("Navigation")
market_choice = st.sidebar.radio("Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

psx_sharia = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL"]
us_top = ["TSM", "V", "ORCL", "BRK-B", "JPM"]

if market_choice == "PSX (Pakistan)":
    selected_ticker = st.sidebar.selectbox("Sharia Picks", psx_sharia)
    is_psx = True
else:
    selected_ticker = st.sidebar.selectbox("Global Picks", us_top)
    is_psx = False

manual_ticker = st.sidebar.text_input("Search Ticker Manually")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_ticker

# --- ANALYSIS ENGINE ---
def run_analysis(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    data = yf.download(ticker_str, period="60d", interval="1d", progress=False)
    
    if data.empty:
        return None, "Ticker not found."
    
    df = data.copy()
    
    # Technical Calcs
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    
    # TR vs ATR Calculation
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                           abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # Values as Floats for UI
    curr_tr = float(df['TR'].iloc[-1])
    curr_atr = float(df['ATR'].iloc[-1])
    leg_out = float(df['Size'].iloc[-1])
    base = float(df['Size'].iloc[-2])
    leg_in = float(df['Size'].iloc[-3])
    
    # Strategy Checks
    ratio_val = leg_out / base if base != 0 else 0
    ratio_pass = (leg_in >= 2 * base) and (leg_out >= 4 * base)
    
    white_barrier = float(df['High'].iloc[-8:-1].max())
    white_area_pass = float(df['Low'].iloc[-1]) > white_barrier
    
    momentum_pass = curr_tr > curr_atr
    pulse_bullish = (df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]) and (df['Close'].iloc[-1] > df['Open'].iloc[-1])
    
    return df, {
        "ticker": ticker_str,
        "price": float(df['Close'].iloc[-1]),
        "ratio_pass": ratio_pass,
        "ratio_val": ratio_val,
        "white_area_pass": white_area_pass,
        "momentum_pass": momentum_pass,
        "pulse_pass": pulse_bullish,
        "tr": curr_tr,
        "atr": curr_atr,
        "base_range": (float(df['Low'].iloc[-2]), float(df['High'].iloc[-2])),
        "white_barrier": white_barrier
    }

# --- UI DISPLAY ---
if ticker_to_run:
    df, res = run_analysis(ticker_to_run, is_psx)
    
    if df is not None:
        # 1. TOP METRICS WITH COLOR CODING
        m1, m2, m3, m4 = st.columns(4)
        
        m1.metric("Current Price", f"{res['price']:.2f}")
        
        # Color Logic for Ratio
        r_color = "normal" if res['ratio_pass'] else "inverse"
        m2.metric("1-2-4 Ratio", f"{res['ratio_val']:.1f}x", 
                  delta="PASS" if res['ratio_pass'] else "FAIL", delta_color=r_color)
        
        # Color Logic for White Area
        w_color = "normal" if res['white_area_pass'] else "inverse"
        m3.metric("White Area", "CLEAN" if res['white_area_pass'] else "OVERLAP", 
                  delta="SAFE" if res['white_area_pass'] else "RISKY", delta_color=w_color)
        
        # Color Logic for Momentum (TR vs ATR)
        mom_color = "normal" if res['momentum_pass'] else "inverse"
        m4.metric("Momentum (TR/ATR)", f"{res['tr']:.2f} / {res['atr']:.2f}", 
                  delta="EXPLOSIVE" if res['momentum_pass'] else "SLUGGISH", delta_color=mom_color)

        # 2. STATUS SUMMARY
        st.markdown("---")
        status_col1, status_col2 = st.columns(2)
        
        with status_col1:
            st.subheader("Strategy Checklist")
            st.write(f"{'✅' if res['pulse_pass'] else '❌'} **Dr. Ravi Pulse:** {'Strong' if res['pulse_pass'] else 'Weak/Red'}")
            st.write(f"{'✅' if res['ratio_pass'] else '❌'} **1-2-4 Balance:** {'Institutional' if res['ratio_pass'] else 'Retail Noise'}")
            st.write(f"{'✅' if res['white_area_pass'] else '❌'} **Traffic:** {'White Area Clear' if res['white_area_pass'] else 'Heavily Crowded'}")
            st.write(f"{'✅' if res['momentum_pass'] else '❌'} **Engine:** {'TR > ATR (Force detected)' if res['momentum_pass'] else 'Normal Volatility'}")

        with status_col2:
            st.subheader("Verdict")
            if res['ratio_pass'] and res['white_area_pass'] and res['momentum_pass'] and res['pulse_pass']:
                st.success("🔥 **GOLDEN SETUP:** This stock is in high-probability alignment.")
                st.balloons()
            else:
                st.error("⚠️ **NO TRADE:** Strategy criteria not met. Wait for maturation.")

        # 3. INTERACTIVE CHART
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1), name='EMA 50'))
        
        # Demand Zone Highlight
        fig.add_shape(type="rect", x0=df.index[-2], x1=df.index[-1], y0=res['base_range'][0], y1=res['base_range'][1],
                      fillcolor="rgba(0, 255, 0, 0.2)", line_width=0)
        
        # White Area Maturity Line
        fig.add_hline(y=res['white_barrier'], line_dash="dash", line_color="white", annotation_text="7D Maturity")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(res)