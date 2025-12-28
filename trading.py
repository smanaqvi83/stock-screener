import customtkinter as ctk
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StockScreenerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("QuantFlow: Pro 1-2-4 Strategy Dashboard")
        self.geometry("1200x850")

        # Layout Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.label = ctk.CTkLabel(self.sidebar, text="TRADING TERMINAL", font=("Arial", 18, "bold"))
        self.label.pack(pady=20)

        # Manual Input
        self.ticker_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Symbol (SYS, TSLA)")
        self.ticker_entry.pack(pady=5, padx=20)

        self.psx_var = ctk.BooleanVar(value=True)
        self.psx_check = ctk.CTkCheckBox(self.sidebar, text="Manual is PSX?", variable=self.psx_var)
        self.psx_check.pack(pady=5)

        self.btn_analyze = ctk.CTkButton(self.sidebar, text="RUN ANALYSIS", command=self.run_manual_analysis)
        self.btn_analyze.pack(pady=10, padx=20)

        # PSX SHARIA SECTION
        self.psx_label = ctk.CTkLabel(self.sidebar, text="PSX SHARIA TOP 5", font=("Arial", 12, "bold"), text_color="gray")
        self.psx_label.pack(pady=(20, 5))
        
        psx_sharia = ["SYS", "LUCK", "HUBC", "ENGRO", "PPL"]
        for stock in psx_sharia:
            btn = ctk.CTkButton(self.sidebar, text=stock, fg_color="transparent", border_width=1, 
                                 command=lambda s=stock: self.quick_analyze(s, True))
            btn.pack(pady=2, padx=20)

        # NYSE SECTION
        self.nyse_label = ctk.CTkLabel(self.sidebar, text="NYSE TOP 5", font=("Arial", 12, "bold"), text_color="gray")
        self.nyse_label.pack(pady=(20, 5))
        
        nyse_stocks = ["TSM", "V", "ORCL", "BRK-B", "JPM"]
        for stock in nyse_stocks:
            btn = ctk.CTkButton(self.sidebar, text=stock, fg_color="transparent", border_width=1, 
                                 command=lambda s=stock: self.quick_analyze(s, False))
            btn.pack(pady=2, padx=20)

        # --- Main Area ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.result_box = ctk.CTkTextbox(self.main_frame, height=220, font=("Consolas", 14))
        self.result_box.pack(fill="x", padx=10, pady=10)

        self.canvas_frame = ctk.CTkFrame(self.main_frame)
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def run_manual_analysis(self):
        symbol = self.ticker_entry.get().upper()
        self.quick_analyze(symbol, self.psx_var.get())

    def quick_analyze(self, symbol, is_psx):
        ticker_str = f"{symbol}.KA" if is_psx else symbol
        try:
            stock = yf.Ticker(ticker_str)
            df = stock.history(period="60d")
            
            if df.empty:
                self.result_box.delete("1.0", "end")
                self.result_box.insert("end", f"Error: {ticker_str} not found.")
                return

            # Technical Calcs
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['Size'] = df['High'] - df['Low']
            
            # 1-2-4 Logic
            leg_in, base, leg_out = df['Size'].iloc[-3], df['Size'].iloc[-2], df['Size'].iloc[-1]
            ratio_pass = (leg_in >= 2 * base) and (leg_out >= 4 * base)
            
            # White Area
            prev_7d_high = df['High'].iloc[-8:-1].max()
            white_area_pass = df['Low'].iloc[-1] > prev_7d_high

            # Pulse Check
            pulse = df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1] and df['Close'].iloc[-1] > df['Open'].iloc[-1]

            self.result_box.delete("1.0", "end")
            report = f"STARK DASHBOARD REPORT: {ticker_str}\n" + "="*40 + "\n"
            report += f"PULSE TREND:  {'✅ BULLISH' if pulse else '❌ NEUTRAL/BEAR'}\n"
            report += f"1-2-4 RATIO:  {'✅ DETECTED' if ratio_pass else '❌ FAILED'}\n"
            report += f"WHITE AREA:   {'✅ CLEAN' if white_area_pass else '❌ OVERLAP'}\n"
            report += f"ZONE RANGE:   {df['Low'].iloc[-2]:.2f} - {df['High'].iloc[-2]:.2f}\n"
            report += "="*40 + "\n"
            report += f"VERDICT: {'🟢 SAFE TO INVEST' if (pulse and ratio_pass and white_area_pass) else '🔴 AVOID - SETUP INCOMPLETE'}"
            
            self.result_box.insert("end", report)
            self.plot_chart(df, symbol, prev_7d_high)

        except Exception as e:
            self.result_box.insert("end", f"System Error: {str(e)}")

    def plot_chart(self, df, symbol, white_barrier):
        for widget in self.canvas_frame.winfo_children():
            widget.destroy()

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), dpi=100, gridspec_kw={'height_ratios': [3, 1]})
        fig.patch.set_facecolor('#1e1e1e')
        ax1.set_facecolor('#1e1e1e')
        
        # Candles
        colors = ['#26a69a' if c > o else '#ef5350' for o, c in zip(df['Open'], df['Close'])]
        ax1.bar(df.index, df['High']-df['Low'], bottom=df['Low'], color=colors, width=0.5)
        ax1.bar(df.index, df['Close']-df['Open'], bottom=df['Open'], color=colors, width=0.8)
        
        ax1.plot(df.index, df['EMA20'], color='#00d2ff', label='Pulse')
        ax1.plot(df.index, df['EMA50'], color='#ffcc00', label='Trend')
        ax1.axhline(white_barrier, color='white', linestyle='--', alpha=0.4, label="Maturity Line")
        
        base_low, base_high = df['Low'].iloc[-2], df['High'].iloc[-2]
        ax1.axhspan(base_low, base_high, color='lime', alpha=0.15, label="Demand Zone")

        ax1.legend(loc='upper left', fontsize=8, labelcolor='white', facecolor='#1e1e1e')
        ax1.tick_params(colors='white', labelsize=8)
        ax2.set_facecolor('#1e1e1e')
        ax2.bar(df.index, df['Volume'], color='gray', alpha=0.3)
        ax2.tick_params(colors='white', labelsize=8)

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

if __name__ == "__main__":
    app = StockScreenerApp()
    app.mainloop()