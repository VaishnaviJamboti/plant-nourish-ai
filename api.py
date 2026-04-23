import os
os.environ['FLASK_SKIP_DOTENV'] = '1'

from flask import Flask, request, jsonify
import psycopg2
import threading

app = Flask(__name__)

# ============================================
# DATABASE CONNECTION
# ============================================

def get_db_connection():
    try:
        return psycopg2.connect(
            host="localhost",
            user="postgres",
            password="post2026",
            database="plant",
            port="5432"
        )
    except Exception as e:
        print(f"❌ DB Connection Error: {e}")
        return None

# ============================================
# CREATE TABLE ON STARTUP
# ============================================

def create_esp32_table():
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS esp32_live (
                id          SERIAL PRIMARY KEY,
                moisture    REAL,
                temperature REAL,
                humidity    REAL,
                light_lux   REAL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ esp32_live table is ready in PostgreSQL.")
    except Exception as e:
        print(f"❌ Table creation error: {e}")

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/sensor', methods=['POST'])
def receive_sensor_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400

        moisture    = data.get('moisture')
        temperature = data.get('temperature')
        humidity    = data.get('humidity')
        light_lux   = data.get('light_lux')

        print(f"📡 Incoming: T:{temperature}°C | H:{humidity}% | M:{moisture}% | L:{light_lux}lx")

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO esp32_live (moisture, temperature, humidity, light_lux)
                VALUES (%s, %s, %s, %s)
            """, (moisture, temperature, humidity, light_lux))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"error": "Database connection failed"}), 500

    except Exception as e:
        print(f"❌ API Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

# ============================================
# RUN AS BACKGROUND THREAD (called by app1.py)
# ============================================

_flask_started = False

def start_flask_thread():
    """
    Starts Flask in a background daemon thread.
    Safe to call multiple times — only starts once.
    """
    global _flask_started
    if _flask_started:
        return

    create_esp32_table()

    def run():
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)  # suppress Flask request logs in Streamlit terminal
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    _flask_started = True
    print("✅ Flask API started in background thread on port 5000")

# ============================================
# STANDALONE MODE (python api.py)
# ============================================

if __name__ == '__main__':
    create_esp32_table()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)