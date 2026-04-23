import psycopg2
import pandas as pd
import streamlit as st
import time
import requests

# ============================================
# DATABASE CONNECTION
# ============================================

def get_db_connection():
    """Connects to the PostgreSQL service."""
    try:
        return psycopg2.connect(
            host="localhost",
            user="postgres",
            password="post2026",
            database="plant",
            port="5432"
        )
    except Exception as e:
        st.error(f"PostgreSQL Connection Error: {e}")
        return None

# ============================================
# 🚀 AUTO-START FLASK IN BACKGROUND THREAD
# ============================================

def is_api_running():
    """Ping the /health endpoint to check if Flask is running."""
    try:
        r = requests.get("http://127.0.0.1:5000/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def start_api_server():
    """
    Starts Flask API in a background thread inside the same process.
    No separate terminal needed. Safe to call multiple times.
    """
    if is_api_running():
        return True

    try:
        from api import start_flask_thread
        start_flask_thread()

        # Wait up to 6 seconds for Flask to come online
        for _ in range(12):
            time.sleep(0.5)
            if is_api_running():
                return True

        return False

    except Exception as e:
        st.error(f"❌ Could not start API: {e}")
        return False


def stop_api_server():
    """
    Flask thread is a daemon — it stops automatically when Streamlit stops.
    Nothing to do here, but kept for compatibility with app1.py.
    """
    pass


# ============================================
# 📡 ESP32 LIVE DATA (via WiFi → PostgreSQL)
# ============================================

def fetch_esp32_sensor_data():
    """
    Reads the LATEST sensor reading saved by ESP32 via WiFi.
    Flow: ESP32 → WiFi → Flask API → esp32_live table → this function
    """
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT moisture, temperature, humidity, light_lux, received_at
                FROM esp32_live
                ORDER BY id DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                df = pd.DataFrame([{
                    'moisture':    round(row[0], 1),
                    'temperature': round(row[1], 1),
                    'humidity':    round(row[2], 1),
                    'light_lux':   round(row[3], 1),
                }])
                received_at = row[4]
                return df, received_at
            else:
                return None, None
    except Exception as e:
        st.error(f"❌ Error reading ESP32 data: {e}")
        return None, None


# ============================================
# DATABASE FUNCTIONS
# ============================================

def fetch_sensor_data(plant_name, selected_stage, use_esp32=False):
    """
    Fetches sensor data from either:
    - Real-time ESP32 WiFi data (use_esp32=True) → reads from esp32_live table
    - Database data            (use_esp32=False) → reads from plant-specific table
    """
    if use_esp32:
        df, _ = fetch_esp32_sensor_data()
        return df

    try:
        conn = get_db_connection()
        if conn is not None:
            table_map = {
                "Chilli Pepper": "chilli_pepper_data",
                "Tomato":        "tomato_data",
                "Cucumber":      "cucumber_data",
                "Coriander":     "coriander_data",
                "Brinjal":       "brinjal_data"
            }
            table = table_map.get(plant_name)
            if not table:
                return None

            query = f"""
                SELECT t.humidity, t.temperature, t.light_lux, t.moisture
                FROM {table} AS t
                INNER JOIN growth_stages AS g ON t.stage_id = g.id
                WHERE g.stage_name = %s
                ORDER BY RANDOM()
                LIMIT 1
            """
            df = pd.read_sql_query(query, conn, params=(selected_stage,))
            conn.close()
            return df if not df.empty else None
    except Exception as e:
        print(f"DATABASE QUERY ERROR: {e}")
        return None


def get_health_recommendation(plant, stage, humidity, temperature, light, moisture):
    """
    Stage-specific health recommendations.
    Format: [min_moist, max_moist, min_temp, max_temp, min_hum, max_hum, min_light, max_light]
    """
    stage_targets = {
        "Tomato": {
            "Seedling":   [60, 75, 20, 25, 65, 80, 300, 600],
            "Vegetative": [65, 80, 21, 27, 60, 75, 400, 800],
            "Flowering":  [70, 85, 20, 26, 55, 70, 500, 900],
            "Fruiting":   [65, 80, 20, 27, 55, 70, 500, 950],
        },
        "Chilli Pepper": {
            "Seedling":   [55, 70, 22, 28, 60, 75, 250, 500],
            "Vegetative": [60, 75, 22, 30, 55, 72, 300, 700],
            "Flowering":  [60, 80, 22, 30, 55, 70, 350, 860],
            "Fruiting":   [55, 75, 22, 30, 50, 68, 350, 860],
        },
        "Cucumber": {
            "Seedling":   [65, 80, 18, 24, 75, 90, 250, 500],
            "Vegetative": [70, 85, 18, 24, 75, 90, 280, 600],
            "Flowering":  [75, 90, 18, 24, 75, 88, 300, 700],
            "Fruiting":   [70, 88, 18, 24, 72, 88, 280, 710],
        },
        "Coriander": {
            "Seedling":   [50, 65, 17, 25, 50, 65, 150, 400],
            "Vegetative": [50, 70, 17, 27, 50, 65, 180, 700],
            "Flowering":  [45, 65, 17, 27, 45, 62, 200, 860],
            "Fruiting":   [45, 60, 17, 27, 45, 60, 200, 860],
        },
        "Brinjal": {
            "Seedling":   [55, 70, 22, 28, 60, 75, 280, 600],
            "Vegetative": [60, 80, 22, 30, 60, 78, 300, 700],
            "Flowering":  [60, 85, 22, 30, 60, 78, 330, 800],
            "Fruiting":   [60, 82, 22, 30, 58, 75, 330, 810],
        },
    }

    stage_key = stage.strip().capitalize()
    t = stage_targets.get(plant, {}).get(stage_key, [60, 80, 20, 28, 55, 75, 300, 800])
    advice_list = []

    if moisture < t[0]:
        advice_list.append(f"💧 Your {plant} needs MORE WATER. Current: {moisture}% | Required: {t[0]}–{t[1]}%. Water now.")
    elif moisture > t[1]:
        advice_list.append(f"🛑 OVER-WATERED. Current: {moisture}% | Required: {t[0]}–{t[1]}%. Let soil dry.")

    if temperature < t[2]:
        advice_list.append(f"🌡️ TOO COLD. Current: {temperature}°C | Required: {t[2]}–{t[3]}°C. Move to warmer spot.")
    elif temperature > t[3]:
        advice_list.append(f"🌡️ TOO HOT. Current: {temperature}°C | Required: {t[2]}–{t[3]}°C. Provide shade.")

    if humidity < t[4]:
        advice_list.append(f"💨 TOO DRY. Current: {humidity}% | Required: {t[4]}–{t[5]}%. Mist the leaves.")
    elif humidity > t[5]:
        advice_list.append(f"💨 TOO HUMID. Current: {humidity}% | Required: {t[4]}–{t[5]}%. Improve air circulation.")

    if light < t[6]:
        advice_list.append(f"☀️ LOW LIGHT. Current: {light} lux | Required: {t[6]}–{t[7]} lux. Move to brighter spot.")
    elif light > t[7]:
        advice_list.append(f"☀️ TOO BRIGHT. Current: {light} lux | Required: {t[6]}–{t[7]} lux. Provide partial shade.")

    if not advice_list:
        return (f"✅ Your {plant} is in perfect condition at {stage_key} stage! "
                f"Moisture ({moisture}%), Temp ({temperature}°C), "
                f"Humidity ({humidity}%), Light ({light} lux) — all ideal. Keep it up!")

    return " | ".join(advice_list)


def fetch_historical_data(plant_name, limit=20):
    try:
        conn = get_db_connection()
        if conn:
            table_map = {
                "Chilli Pepper": "chilli_pepper_data",
                "Tomato":        "tomato_data",
                "Cucumber":      "cucumber_data",
                "Coriander":     "coriander_data",
                "Brinjal":       "brinjal_data"
            }
            table = table_map.get(plant_name)
            query = f"SELECT humidity, temperature, light_lux, moisture FROM {table} ORDER BY id DESC LIMIT %s"
            df = pd.read_sql_query(query, conn, params=(limit,))
            conn.close()

            if not df.empty:
                df['timestamp'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='h')
                return df.iloc[::-1]
        return pd.DataFrame()
    except Exception as e:
        print(f"Historical Data Error: {e}")
        return pd.DataFrame()