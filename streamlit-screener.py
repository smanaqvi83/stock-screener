import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(page_title="QuantFlow 1-2-4 Dashboard", layout="wide")
st.title("📈 QuantFlow: Pro 1-2-4 & Pulse Screener")
st.markdown("### PSX Sharia & NYSE Technical Dashboard")

# --- SIDEBAR ---
st.sidebar.header("Navigation")
market_choice = st.sidebar.radio("Select Market", ["PSX (Pakistan)", "NYSE/NASDAQ (US)"])

# Sharia Top 5 & NYSE Top 5
psx_sharia = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL"]
us_top = ["TSM", "V", "ORCL", "BRK-B", "JPM"]

if market_choice == "PSX (Pakistan)":
    selected_ticker = st.sidebar.selectbox("Quick Select Sharia Top 5", psx_sharia)
    is_psx = True
else:
    selected_ticker = st.sidebar.selectbox("Quick Select NYSE Top 5", us_top)
    is_psx = False

manual_ticker = st.sidebar.text_input("OR Enter Manual Ticker (e.g. NVDA or OGDC)")
ticker_to_run = manual_ticker.upper() if manual_ticker else selected_ticker

# --- LOGIC FUNCTION ---
def run_analysis(symbol, is_psx):
    ticker_str = f"{symbol}.KA" if is_psx else symbol
    data = yf.download(ticker_str, period="60d", interval="1d")
    
    if data.empty:
        return None, f"No data found for {ticker_str}"
    
    # Technical Calcs
    df = data.copy()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Size'] = df['High'] - df['Low']
    
    # 1-2-4 Logic
    leg_in, base, leg_out = df['Size'].iloc[-3], df['Size'].iloc[-2], df['Size'].iloc[-1]
    ratio_pass = (leg_in >= 2 * base) and (leg_out >= 4 * base)
    
    # White Area
    prev_7d_high = df['High'].iloc[-8:-1].max()
    white_area_pass = df['Low'].iloc[-1] > prev_7d_high
    
    # Pulse
    pulse = df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1] and df['Close'].iloc[-1] > df['Open'].iloc[-1]
    
    return df, {
        "ticker": ticker_str,
        "price": df['Close'].iloc[-1],
        "pulse": pulse,
        "ratio": ratio_pass,
        "white_area": white_area_pass,
        "base_range": (df['Low'].iloc[-2], df['High'].iloc[-2]),
        "white_barrier": prev_7d_high
    }

# --- MAIN DISPLAY ---
if ticker_to_run:
    df, result = run_analysis(ticker_to_run, is_psx)
    
    if df is not None:
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Price", f"{result['price']:.2f}")
        col2.metric("1-2-4 Status", "✅ DETECTED" if result['ratio'] else "❌ FAILED")
        col3.metric("White Area", "✅ CLEAN" if result['white_area'] else "❌ OVERLAP")

        # Verdict Alert
        if result['pulse'] and result['ratio'] and result['white_area']:
            st.success(f"🟢 **STRATEGY ALIGNMENT:** {result['ticker']} is SAFE TO INVEST for next 7 days.")
        else:
            st.warning("🟡 **WAIT:** Criteria not fully met for a high-probability trade.")

        # --- PLOTLY INTERACTIVE CHART ---
        fig = go.Figure()

        # Candlesticks
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))

        # EMAs
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='cyan', width=1.5), name='EMA 20 (Pulse)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='yellow', width=1.5), name='EMA 50 (Trend)'))

        # Demand Zone Box
        fig.add_shape(type="rect", x0=df.index[-2], x1=df.index[-1], y0=result['base_range'][0], y1=result['base_range'][1],
                      fillcolor="lime", opacity=0.3, line_width=0, name="Demand Zone")

        # White Area Line
        fig.add_hline(y=result['white_barrier'], line_dash="dash", line_color="white", annotation_text="Maturity Ceiling")

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error(result)