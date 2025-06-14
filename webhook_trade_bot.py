from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import *

# Load environment variables
load_dotenv()

app = Flask(__name__)

# === CONFIGURATION ===
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
PASSPHRASE = os.getenv("PASSPHRASE", "securekey123")
TRADE_AMOUNT_EUR = 100
STOP_LOSS_PERCENT = 0.02  # 2%
TRAIL_START = 0.03        # Start trailing TP at 3%
TRAIL_GAP = 0.015         # Trailing TP gap 1.5%

TOP_COINS = ['BTC', 'ETH', 'BNB', 'ADA', 'DOT', 'LTC', 'SOL', 'TRX', 'XRP', 'AVAX']
PAIR_SUFFIX = 'EUR'

client = Client(API_KEY, API_SECRET)

# === HELPER FUNCTIONS ===
def get_price(symbol):
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def place_market_order(symbol, side, quantity):
    order = client.create_order(
        symbol=symbol,
        side=side,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    return order

def set_trailing_sl_tp(symbol, entry_price, quantity):
    # Calculate SL and trailing TP trigger price
    stop_price = round(entry_price * (1 - STOP_LOSS_PERCENT), 2)
    trail_start_price = entry_price * (1 + TRAIL_START)
    trail_price = trail_start_price * (1 - TRAIL_GAP)
    print(f"[INFO] SL set at {stop_price}, trailing TP from {trail_start_price} trailing by {TRAIL_GAP*100}%")
    # NOTE: Binance Spot does not support native SL/TP; implement this via background thread or use Binance Futures.

# === WEBHOOK ENDPOINT ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

    if not data or data.get('passphrase') != PASSPHRASE:
        return jsonify({'error': 'Invalid passphrase'}), 403

    raw_symbol = data.get('symbol', '').upper()
    action = data.get('action', '').lower()

    if '/' not in raw_symbol or action not in ['buy', 'sell']:
        return jsonify({'error': 'Invalid payload'}), 400

    base, quote = raw_symbol.split('/')
    if base not in TOP_COINS or quote != PAIR_SUFFIX:
        return jsonify({'error': 'Coin not supported'}), 400

    symbol = base + quote
    try:
        price = get_price(symbol)
        quantity = round(TRADE_AMOUNT_EUR / price, 6)

        print(f"[INFO] Placing {action.upper()} order for {quantity} {base} at market price {price}")

        side = SIDE_BUY if action == 'buy' else SIDE_SELL
        order = place_market_order(symbol, side, quantity)

        if action == 'buy':
            set_trailing_sl_tp(symbol, price, quantity)

        return jsonify({'status': 'success', 'order': order})

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({'error': str(e)}), 500

# === MAIN ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
