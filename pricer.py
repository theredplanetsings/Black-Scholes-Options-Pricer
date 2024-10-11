import math
import logging
from scipy.stats import norm
import yfinance as yf
import matplotlib.pyplot as plt
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import re
from fractions import Fraction

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

info_window = None  # Global variable to keep track of the info window

def black_scholes(S, K, T, r, sigma, q, option_type='call'):
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if option_type == 'call':
        option_price = S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    elif option_type == 'put':
        option_price = K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)
    else:
        raise ValueError("option_type must be 'call' or 'put'")
    
    return round(option_price, 3)

def fetch_detailed_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        sustainability = stock.sustainability
        cdp_score = sustainability.loc['cdpScore']['Value'] if 'cdpScore' in sustainability.index else 'N/A'
        return {
            'Open': round(info.get('open', 0), 6),
            'High': round(info.get('dayHigh', 0), 6),
            'Low': round(info.get('dayLow', 0), 6),
            'Market Cap': round(info.get('marketCap', 0), 6),
            'P/E Ratio': round(info.get('trailingPE', 0), 6),
            'Dividend Yield': round(info.get('dividendYield', 0), 6),
            'CDP Score': cdp_score,
            '52-Week High': round(info.get('fiftyTwoWeekHigh', 0), 6),
            '52-Week Low': round(info.get('fiftyTwoWeekLow', 0), 6)
        }
    except Exception as e:
        logging.error(e)
        raise ValueError("Failed to fetch detailed stock info. Please check the ticker symbol and try again.")

def fetch_historical_data(ticker, period):
    try:
        stock = yf.Ticker(ticker)
        if period == '1d':
            hist = stock.history(period=period, interval='1h')
        else:
            hist = stock.history(period=period)
        return hist
    except Exception as e:
        logging.error(e)
        raise ValueError("Failed to fetch historical data. Please check the ticker symbol and try again.")

def store_data(ticker, call_price, put_price):
    conn = sqlite3.connect('options_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS options
                 (date text, ticker text, call_price real, put_price real)''')
    c.execute("INSERT INTO options VALUES (?, ?, ?, ?)",
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticker, call_price, put_price))
    conn.commit()
    conn.close()

def plot_option_prices_with_info(ticker, K, T, r, sigma, q, call_price, put_price):
    S_range = range(50, 151)
    call_prices = [black_scholes(S, K, T, r, sigma, q, 'call') for S in S_range]
    put_prices = [black_scholes(S, K, T, r, sigma, q, 'put') for S in S_range]
    
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.plot(S_range, call_prices, label='Call Option Price')
    ax.plot(S_range, put_prices, label='Put Option Price')
    ax.set_xlabel('Stock Price')
    ax.set_ylabel('Option Price')
    ax.set_title('Black-Scholes Option Prices')
    ax.legend()
    ax.grid(True)
    plt.xticks(rotation=45)
    fig.tight_layout()  # Adjust layout

    # Create a new window for the graph
    graph_window = tk.Toplevel()
    graph_window.title(f"{ticker} Option Prices Graph")

    # Create a frame for the calculation info
    info_frame = tk.Frame(graph_window)
    info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Add calculation info to the frame
    info_label = tk.Label(info_frame, text=f"Implied Volatility: {sigma * 100:.2f}%\n"
                                           f"Risk-Free Rate: {r * 100:.2f}%\n"
                                           f"Maturity: {T} years\n"
                                           f"Call Option Price: {call_price}\n"
                                           f"Put Option Price: {put_price}")
    info_label.pack(padx=10, pady=10)

    # Add the graph to the window
    canvas = FigureCanvasTkAgg(fig, master=graph_window)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

def calculate_and_display_prices(ticker, S, K, T, r, implied_volatility):
    try:
        q = fetch_detailed_stock_info(ticker)['Dividend Yield']
        call_price = black_scholes(S, K, T, r, implied_volatility, q, 'call')
        put_price = black_scholes(S, K, T, r, implied_volatility, q, 'put')

        logging.info(f"Call Option Price: {call_price}")
        logging.info(f"Put Option Price: {put_price}")

        store_data(ticker, call_price, put_price)
        plot_option_prices_with_info(ticker, K, T, r, implied_volatility, q, call_price, put_price)
    except ValueError as e:
        logging.error(e)
        messagebox.showerror("Error", str(e))

def display_stock_info(ticker):
    global info_window
    try:
        if info_window is not None and info_window.winfo_exists():
            info_window.destroy()
        
        info = fetch_detailed_stock_info(ticker)
        info_text = "\n".join([f"{key}: {value}" for key, value in info.items()])
        
        # Create a new window for the stock information
        info_window = tk.Toplevel()
        info_window.title(f"{ticker} Stock Information")
        
        # Add the stock information to the window
        info_label = tk.Label(info_window, text=info_text, justify=tk.LEFT, padx=10, pady=10)
        info_label.pack(fill=tk.BOTH, expand=True)
        
    except ValueError as e:
        logging.error(e)
        messagebox.showerror("Error", str(e))

def plot_interactive_graph(ticker, period):
    try:
        hist = fetch_historical_data(ticker, period)
        fig, ax = plt.subplots(figsize=(16, 9))
        ax.plot(hist.index, hist['Close'], label='Close Price')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.set_title(f'{ticker} Price History ({period})')
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)
        fig.tight_layout()  # Adjust layout

        # Create a new window for the graph
        graph_window = tk.Toplevel()
        graph_window.title(f"{ticker} Price History Graph")

        # Add the graph to the window
        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    except ValueError as e:
        logging.error(e)
        messagebox.showerror("Error", str(e))

def validate_inputs(*inputs, numeric=False):
    for input_value in inputs:
        if not input_value:
            return False
        if numeric:
            try:
                float(input_value)
            except ValueError:
                return False
    return True

def validate_ticker(ticker):
    # Check if the ticker contains only letters and numbers
    return bool(re.match("^[A-Za-z0-9]+$", ticker))

def validate_maturity(maturity):
    try:
        # Try to convert the maturity to a fraction
        Fraction(maturity)
        return True
    except ValueError:
        return False

def create_gui():
    root = tk.Tk()
    root.title("Black-Scholes Option Pricer")
    root.geometry("600x400")  # Increase the initial size of the window

    # Create a frame to center the content
    main_frame = tk.Frame(root)
    main_frame.grid(row=0, column=0, sticky="nsew")

    tk.Label(main_frame, text="Stock Ticker:").grid(row=0, column=0, sticky="e")
    tk.Label(main_frame, text="Stock Price:").grid(row=1, column=0, sticky="e")
    tk.Label(main_frame, text="Strike Price:").grid(row=2, column=0, sticky="e")
    tk.Label(main_frame, text="Maturity (years):").grid(row=3, column=0, sticky="e")
    tk.Label(main_frame, text="Risk-Free Rate (%):").grid(row=4, column=0, sticky="e")
    tk.Label(main_frame, text="Implied Volatility (%):").grid(row=5, column=0, sticky="e")

    ticker_entry = tk.Entry(main_frame)
    stock_price_entry = tk.Entry(main_frame)
    strike_entry = tk.Entry(main_frame)
    maturity_entry = tk.Entry(main_frame)
    risk_free_rate_entry = tk.Entry(main_frame)
    volatility_entry = tk.Entry(main_frame)

    ticker_entry.grid(row=0, column=1, padx=10, pady=5)
    stock_price_entry.grid(row=1, column=1, padx=10, pady=5)
    strike_entry.grid(row=2, column=1, padx=10, pady=5)
    maturity_entry.grid(row=3, column=1, padx=10, pady=5)
    risk_free_rate_entry.grid(row=4, column=1, padx=10, pady=5)
    volatility_entry.grid(row=5, column=1, padx=10, pady=5)

    def on_calculate():
        ticker = ticker_entry.get().upper()
        if not validate_ticker(ticker):
            messagebox.showerror("Input Error", "Please enter a valid stock ticker (letters and numbers only).")
            return
        S = stock_price_entry.get()
        K = strike_entry.get()
        T = maturity_entry.get()
        r = risk_free_rate_entry.get()
        implied_volatility = volatility_entry.get()
        if validate_inputs(ticker) and validate_inputs(S, K, r, implied_volatility, numeric=True) and validate_maturity(T):
            try:
                S = float(S)
                K = float(K)
                T = float(Fraction(T))  # Convert to decimal
                r = float(r) / 100  # Convert to decimal
                implied_volatility = float(implied_volatility) / 100  # Convert to decimal
                calculate_and_display_prices(ticker, S, K, T, r, implied_volatility)
            except ValueError:
                messagebox.showerror("Input Error", "Please enter valid numerical values for all fields.")
        else:
            messagebox.showerror("Input Error", "Please fill in all required fields with valid values.")

    def on_show_info():
        ticker = ticker_entry.get().upper()
        if not validate_ticker(ticker):
            messagebox.showerror("Input Error", "Please enter a valid stock ticker (letters and numbers only).")
            return
        if validate_inputs(ticker):
            display_stock_info(ticker)
        else:
            messagebox.showerror("Input Error", "Please enter a stock ticker.")

    def on_show_graph():
        ticker = ticker_entry.get().upper()
        if not validate_ticker(ticker):
            messagebox.showerror("Input Error", "Please enter a valid stock ticker (letters and numbers only).")
            return
        period = period_var.get()
        if validate_inputs(ticker):
            plot_interactive_graph(ticker, period)
        else:
            messagebox.showerror("Input Error", "Please enter a stock ticker and select a period.")

    def on_exit():
        root.quit()

    calculate_button = tk.Button(main_frame, text="Calculate", command=on_calculate, width=20)
    calculate_button.grid(row=6, columnspan=2, pady=10)

    info_button = tk.Button(main_frame, text="Show Info", command=on_show_info, width=20)
    info_button.grid(row=7, columnspan=2, pady=10)

    period_var = tk.StringVar(value='1d')
    period_label = tk.Label(main_frame, text="Select Period:")
    period_label.grid(row=8, column=0, sticky="e")
    period_menu = ttk.Combobox(main_frame, textvariable=period_var, values=['1d', '5d', '1mo', '6mo', 'ytd', '1y', '5y', 'max'], state='readonly')
    period_menu.grid(row=8, column=1, padx=10, pady=5)

    graph_button = tk.Button(main_frame, text="Show Price History", command=on_show_graph, width=20)
    graph_button.grid(row=9, columnspan=2, pady=10)

    exit_button = tk.Button(root, text="Exit", command=on_exit)
    exit_button.place(relx=1.0, rely=0.0, anchor='ne')

    # Configure grid weights to make the window scalable
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)
    for row in range(10):
        main_frame.grid_rowconfigure(row, weight=1)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
