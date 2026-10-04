from flask import Flask, render_template, request, redirect, url_for, session, send_file
import yfinance as yf
import csv
import json
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"  # required for session management
app.permanent_session_lifetime = timedelta(minutes=30)

# --- Persistence functions ---
def load_data(filename, default_data):
    if not os.path.exists(filename):
        return default_data
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            # Migration check: if data is a list (old format) but we expect a dict
            if isinstance(data, list) and isinstance(default_data, dict):
                return {"legacy_user": data}
            return data
    except json.JSONDecodeError:
        return default_data

def save_data(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except OSError as e:
        # Vercel serverless has a read-only filesystem (except /tmp)
        # We catch the error so the app doesn't crash, but note that 
        # data will NOT be saved permanently on Vercel without a real database.
        print(f"Warning: Could not write to {filename}: {e}")

# Watchlist data structure: {"username": ["AAPL", "MSFT"]}
# Users data structure: {"username": "hashed_password"}

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
    if "user" in session:
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username").strip()
        password = request.form.get("password")
        
        users = load_data("users.json", {})
        
        if action == "register":
            if username in users:
                return render_template("login.html", error="Username already exists!")
            if len(username) < 3 or len(password) < 3:
                return render_template("login.html", error="Username and password must be at least 3 characters.")
            
            users[username] = generate_password_hash(password)
            save_data("users.json", users)
            session["user"] = username
            session.permanent = True
            return redirect(url_for("dashboard"))
            
        elif action == "login":
            if username in users and check_password_hash(users[username], password):
                session["user"] = username
                session.permanent = True
                return redirect(url_for("dashboard"))
            else:
                return render_template("login.html", error="Invalid username or password!")
                
    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
        
    username = session["user"]
    all_watchlists = load_data("watchlist.json", {})
    user_watchlist = all_watchlists.get(username, [])

    if request.method == "POST":
        stock = request.form.get("stock").upper().strip()
        if stock and stock not in user_watchlist:
            user_watchlist.append(stock)
            all_watchlists[username] = user_watchlist
            save_data("watchlist.json", all_watchlists)

    data = [get_stock_data(s) for s in user_watchlist if get_stock_data(s)]
    return render_template("index.html", stocks=data, username=username)

@app.route("/export")
def export():
    if "user" not in session:
        return redirect(url_for("login"))
        
    username = session["user"]
    all_watchlists = load_data("watchlist.json", {})
    user_watchlist = all_watchlists.get(username, [])

    filename = f"{username}_watchlist.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol", "Current Price", "Day Change %", "Market Cap", "Sector"])
        for s in user_watchlist:
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
