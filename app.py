from flask import Flask, jsonify, render_template
import btc_trading_bot

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/bot-data')
def bot_data():
    try:
        data = btc_trading_bot.run_bot()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
