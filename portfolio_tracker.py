from flask import Flask, render_template, request, redirect, url_for, session, send_file
import yfinance as yf
import csv
import json
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key"  # required for session management
app.permanent_session_lifetime = timedelta(minutes=30)  # keep login alive for 30 minutes

watchlist = []

# --- Persistence functions ---
def save_watchlist():
    with open("watchlist.json", "w") as f:
        json.dump(watchlist, f)

def load_watchlist():
    global watchlist
    try:
        with open("watchlist.json", "r") as f:
            watchlist = json.load(f)
    except FileNotFoundError:
        watchlist = []

# Load watchlist at startup
load_watchlist()

# --- Stock data fetch ---
def get_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "symbol": symbol,
            "current_price": info.get("currentPrice"),
            "day_change": info.get("regularMarketChangePercent"),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector", "N/A")
        }
    except Exception:
        return None

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # Simple static credentials (replace with DB later if needed)
        if username == "admin" and password == "123":
            session["user"] = username
            session.permanent = True  # keep session alive
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        stock = request.form.get("stock").upper()
        if stock not in watchlist:
            watchlist.append(stock)
            save_watchlist()  # save permanently

    data = [get_stock_data(s) for s in watchlist if get_stock_data(s)]
    return render_template("index.html", stocks=data)

@app.route("/export")
def export():
    if "user" not in session:
        return redirect(url_for("login"))

    filename = "watchlist.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol", "Current Price", "Day Change %", "Market Cap", "Sector"])
        for s in watchlist:
            data = get_stock_data(s)
            if data:
                writer.writerow([
                    data["symbol"],
                    data["current_price"],
                    data["day_change"],
                    data["market_cap"],
                    data["sector"]
                ])
    return send_file(filename, as_attachment=True)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
