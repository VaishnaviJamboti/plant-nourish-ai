import streamlit as st
import base64
import time
import numpy as np
import urllib.parse
from PIL import Image
from local import run_inference, get_plant_analysis, get_global_diagnosis, chat_with_plant_doctor
from database import (fetch_sensor_data, fetch_esp32_sensor_data,
                      get_health_recommendation, fetch_historical_data,
                      start_api_server, stop_api_server, is_api_running)
import streamlit.components.v1 as components

# ============================================
# 🚀 AUTO-START FLASK API WHEN APP LOADS
# This runs once when Streamlit starts.
# No need to run api.py manually ever again.
# ============================================
from api import start_flask_thread
start_flask_thread()

# --- 1. SET PAGE CONFIG ---
st.set_page_config(page_title="Plant Nourish AI", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

# --- 2. BACKGROUND & CSS ---
def get_base64(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

bin_str = get_base64('plant.png')
if bin_str:
    st.markdown(f'''
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
.glass-soft {{ background: rgba(255,255,255,0.45); backdrop-filter: blur(6px); padding: 25px; border-radius: 20px; margin-top: 25px; margin-bottom: 25px; }}
.glass-strong {{ background: rgba(255,255,255,0.75); backdrop-filter: blur(12px); padding: 25px; border-radius: 20px; margin-top: 40px; }}
.glass-alert {{ padding: 18px; border-radius: 15px; margin-top: 15px; font-weight: 500; }}
.glass-alert.success {{ background: rgba(46,204,113,0.15); color: #1e7e34; border: 1px solid rgba(46,204,113,0.4); }}
.glass-alert.danger {{ background: rgba(231,76,60,0.15); color: #a71d2a; border: 1px solid rgba(231,76,60,0.4); }}
.glass-alert.info {{ background: rgba(52,152,219,0.15); color: #0c5460; border: 1px solid rgba(52,152,219,0.4); }}
[data-testid="stDecoration"] {{ display: none !important; }}
button[kind="header"] {{ display: none !important; }}
header {{ background: transparent !important; }}
[data-testid="collapsedControl"] {{ display: flex !important; visibility: visible !important; opacity: 1 !important; z-index: 999999 !important; }}
section[data-testid="stSidebar"] > div {{ background: transparent !important; }}
.glass-container {{ background-color: rgba(255,255,255,0.8); backdrop-filter: blur(10px); padding: 25px; border-radius: 20px; box-shadow: 0px 8px 32px rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.3); margin-bottom: 25px; color: #000000 !important; }}
.main .block-container {{ padding-top: 2rem !important; }}
        </style>
    ''', unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'page' not in st.session_state:
    st.session_state.page = 'splash'
if 'current_stage' not in st.session_state:
    st.session_state.current_stage = "Seedling"
if 'disease_only_mode' not in st.session_state:
    st.session_state.disease_only_mode = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'use_esp32' not in st.session_state:
    st.session_state.use_esp32 = False
if 'api_process' not in st.session_state:
    st.session_state.api_process = None

# --- PAGE 1: SPLASH ---
if st.session_state.page == 'splash':
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><h1 style='text-align: center; font-size: 100px;'>🌱</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; font-style: italic; color: #1B5E20;'>\"Listening to the signals of nature.\"</h3>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
        st.session_state.page = 'dashboard'
        st.rerun()

# --- PAGE 2: DASHBOARD ---
elif st.session_state.page == 'dashboard':

    with st.sidebar:
        st.markdown("### 🌿 Control Center")
        plant_list = ["Select a Plant", "🌶️ Chilli Pepper", "🍅 Tomato", "🥒 Cucumber", "🌿 Coriander", "🍆 Brinjal"]
        selected_plant_raw = st.selectbox("Choose a plant:", plant_list)
        selected_plant = selected_plant_raw.split(" ", 1)[-1] if " " in selected_plant_raw else selected_plant_raw

        if selected_plant_raw != "Select a Plant":
            st.divider()
            st.markdown("### 🌱 AI Growth Analysis")
            unknown_stage = st.toggle("AI Photo ID 📸")

            if unknown_stage:
                tab_cam, tab_file = st.tabs(["📸 Camera", "📁 Upload"])
                stage_image = None
                with tab_cam:
                    cam_input = st.camera_input("Take a photo", key="growth_cam")
                    if cam_input:
                        stage_image = cam_input
                with tab_file:
                    file_input = st.file_uploader("Upload photo", type=['jpg', 'jpeg', 'png'], key="growth_up")
                    if file_input:
                        stage_image = file_input

                if stage_image:
                    if st.button("Identify Stage"):
                        with st.spinner("Analyzing Growth..."):
                            # FIX 1: Convert uploaded image to numpy array before passing to model
                            pil_img = Image.open(stage_image)
                            image_array = np.array(pil_img)
                            # Assuming your sidebar/selectbox variable is named 'selected_plant'
                            # Locate line 106 (or wherever you run analysis)
# 'plant_choice' should be the variable from your selectbox
                            result = get_plant_analysis(image_array, selected_plant)
                            # FIX 1b: Use correct keys returned by get_plant_analysis()
                            if result and result.get('status') == 'success':
                                detected_stage = result['stage'].strip().capitalize()
                                st.session_state.current_stage = detected_stage
                                st.success(f"Detected: {detected_stage} ({result['confidence']})")
                                time.sleep(1)
                                st.rerun()
                            else:
                                err_msg = result.get('message', 'Unknown error') if result else 'No result returned'
                                st.error(f"AI Analysis Failed: {err_msg}")
            else:
                options = ["Seedling", "Vegetative", "Flowering", "Fruiting"]
                current = st.session_state.current_stage.capitalize()
                default_idx = options.index(current) if current in options else 0
                st.session_state.current_stage = st.selectbox("Current Stage:", options, index=default_idx)

            # Data Source Selector
            st.divider()
            st.markdown("### 📡 Data Source")

            col_esp, col_db = st.columns(2)
            with col_esp:
                if st.button("📡 ESP32", use_container_width=True):
                    st.session_state.use_esp32 = True
                    st.rerun()
            with col_db:
                if st.button("💾 Database", use_container_width=True):
                    st.session_state.use_esp32 = False
                    st.rerun()

            if st.session_state.use_esp32:
                if is_api_running():
                    st.success("📡 Live ESP32 Data  •  API ✅")
                else:
                    st.warning("⚠️ API starting up... please wait a moment.")
                _, received_at = fetch_esp32_sensor_data()
                if received_at:
                    st.caption(f"Last update: {received_at.strftime('%H:%M:%S')}")
                else:
                    st.caption("⏳ Waiting for ESP32... (~1 min on first boot)")
            else:
                st.info("💾 Using Database Data")

            st.divider()
            if st.button("🔄 Sync Now", use_container_width=True):
                st.rerun()

        elif st.session_state.disease_only_mode:
            st.divider()
            st.markdown("### 🔬 Quick Diagnosis Mode")
            st.info("Upload a leaf photo below to identify plant diseases.")
            if st.button("← Back to Plant Selection"):
                st.session_state.disease_only_mode = False
                st.rerun()

    # === MAIN AREA ===
    if selected_plant_raw == "Select a Plant" and not st.session_state.disease_only_mode:
        st.markdown('''
            <div class="glass-container" style="text-align: center;">
                <h1 style="font-size: 45px;">The Plant Hospital 🌱</h1>
                <p style="font-size: 20px;">Select your Plant from the sidebar to begin.</p>
            </div>
        ''', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔬 Diagnose Disease Only", use_container_width=True):
                st.session_state.disease_only_mode = True
                st.rerun()

    else:
        # Sensor Dashboard
        if selected_plant_raw != "Select a Plant":
            data = fetch_sensor_data(selected_plant, st.session_state.current_stage, use_esp32=st.session_state.use_esp32)

            if data is not None and not data.empty:
                raw_hum   = data['humidity'].values[0]
                raw_temp  = data['temperature'].values[0]
                raw_light = data['light_lux'].values[0]
                raw_moist = data['moisture'].values[0]

                health_msg = get_health_recommendation(selected_plant, st.session_state.current_stage, raw_hum, raw_temp, raw_light, raw_moist)
                source_badge = "📡 Live ESP32" if st.session_state.use_esp32 else "💾 Database"

                dashboard_html = f"""
<div style="font-family: sans-serif; width: 100%; box-sizing: border-box; background: rgba(255,255,255,0.25); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px); padding: 30px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 8px 32px rgba(0,0,0,0.15); text-align: center; color: #000;">
    <h1 style="color: #1B5E20; margin-bottom: 5px;">Diagnosis: {selected_plant}</h1>
    <p style="font-size: 18px; color: #333;">Stage: <b>{st.session_state.current_stage}</b> &nbsp;|&nbsp; Source: <b>{source_badge}</b></p>
    <div style="display: flex; justify-content: space-around; flex-wrap: wrap; margin-top: 20px;">
        <div style="flex: 1; min-width: 120px;"><span style="font-size: 24px;">💧</span><br><small>Soil Moisture</small><h3>{raw_moist}%</h3></div>
        <div style="flex: 1; min-width: 120px;"><span style="font-size: 24px;">🌡️</span><br><small>Temperature</small><h3>{raw_temp}°C</h3></div>
        <div style="flex: 1; min-width: 120px;"><span style="font-size: 24px;">☀️</span><br><small>Light</small><h3>{raw_light} lux</h3></div>
        <div style="flex: 1; min-width: 120px;"><span style="font-size: 24px;">💨</span><br><small>Humidity</small><h3>{raw_hum}%</h3></div>
    </div>
    <div style="background: rgba(255,255,255,0.35); backdrop-filter: blur(10px); padding: 15px; border-radius: 12px; margin-top: 25px; border-left: 5px solid #4CAF50; text-align: left;">
        <b style="color: #1B5E20;">AI Recommendation:</b><br><span>{health_msg}</span>
    </div>
</div>"""
                components.html(dashboard_html, height=600, scrolling=True)

                st.markdown('<div class="glass-soft"><h2 style="margin-bottom:20px;">📈 Real-time Sensor Trends</h2>', unsafe_allow_html=True)
                hist_data = fetch_historical_data(selected_plant)
                if not hist_data.empty:
                    st.line_chart(hist_data.set_index('timestamp')[['moisture', 'temperature', 'humidity', 'light_lux']])
                st.markdown("</div>", unsafe_allow_html=True)

            else:
                if st.session_state.use_esp32:
                    st.warning("⚠️ No ESP32 data found. Make sure:\n1. ESP32 is connected to WiFi\n2. ESP32 is sending data to your PC IP")
                else:
                    st.warning("⚠️ No database data found.")

        # Disease Section
        plant_name_display = "your plant" if st.session_state.disease_only_mode else selected_plant

        st.markdown(f"""
        <p style="margin-top: 40px; margin-bottom: 15px; width: 100%;">
            <span style="background: rgba(255,255,255,0.25); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px); padding: 20px 30px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 8px 32px rgba(0,0,0,0.15); display: block; font-size: 33px; font-weight: 700; color: #000;">
                🔍 Check: Is {plant_name_display} suffering from a disease?
            </span>
        </p>""", unsafe_allow_html=True)

        d_col1, d_col2 = st.columns(2)
        with d_col1:
            st.markdown("""<p style="margin-bottom:10px;"><span style="background: rgba(255,255,255,0.35); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 8px 16px; border-radius: 10px; border-left: 5px solid #555; color: #000; font-size: 20px; font-weight: 600; display: inline-block;">📸 Live Leaf Scan</span></p>""", unsafe_allow_html=True)
            d_cam = st.camera_input(" ", key="disease_cam")
        with d_col2:
            st.markdown("""<p style="margin-bottom:10px;"><span style="background: rgba(255,255,255,0.35); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 8px 16px; border-radius: 10px; border-left: 5px solid #555; color: #000; font-size: 20px; font-weight: 600; display: inline-block;">📁 Upload Leaf Photo</span></p>""", unsafe_allow_html=True)
            d_up = st.file_uploader(" ", type=['jpg', 'png', 'jpeg'], key="disease_up")

        final_d_img = d_cam if d_cam else d_up
        if final_d_img:
            st.image(final_d_img, width=400)
            if st.button("Run Disease Diagnostic"):
                with st.spinner("Analyzing across all species..."):
                    # FIX 2: Convert image to numpy array and use get_plant_analysis (not get_global_diagnosis)
                    pil_img = Image.open(final_d_img)
                    disease_image_array = np.array(pil_img)
                    d_result = get_plant_analysis(disease_image_array, selected_plant if selected_plant_raw != "Select a Plant" else "Tomato", mode="disease")

                    if d_result.get('status') == 'error':
                        st.error(f"Analysis failed: {d_result.get('message', 'Unknown error')}")
                    else:
                        # FIX 2b: Use correct keys: 'disease' and 'confidence' (not 'display_msg' / 'label')
                        disease_name = d_result.get('disease', 'Unknown')
                        confidence_score = d_result.get('confidence', '0%')
                        recommendation = d_result.get('recommendation', '')
                        detected_plant = selected_plant if selected_plant_raw != "Select a Plant" else "Plant"

                        search_term = f"{detected_plant} {disease_name} treatment remedy"
                        yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_term)}"
                        google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_term)}"

                        if "Healthy" in disease_name:
                            st.markdown(f"""<div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 20px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.2); border-left: 5px solid #4CAF50; color: #000;"><span style="font-size: 20px;">✅</span> <b>{disease_name} — {recommendation}</b><br><small>AI Confidence: {confidence_score}</small></div>""", unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                                <div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 20px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.2); border-left: 5px solid #C62828; margin-bottom: 10px; color: #000;"><span style="font-size: 20px;">🚨</span> <b>{disease_name} detected!</b><br><small>Identification Confidence: {confidence_score}</small></div>
                                <div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 15px 20px; border-radius: 15px; border-left: 5px solid #FF9800; margin-bottom: 10px; color: #000;"><b>ℹ️ Quick Advice:</b><br>{recommendation}</div>
                                <div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 20px; border-radius: 15px; border-left: 5px solid #1565C0; color: #000;"><b>🎬 Remedy Resources:</b><br><br><a href="{yt_url}" target="_blank" style="display: inline-block; background: #FF0000; color: white; padding: 10px 20px; border-radius: 10px; text-decoration: none; font-weight: bold; margin-right: 10px;">▶ YouTube Guide</a><a href="{google_url}" target="_blank" style="display: inline-block; background: #1a73e8; color: white; padding: 10px 20px; border-radius: 10px; text-decoration: none; font-weight: bold;">🔎 Google Search</a></div>
                            """, unsafe_allow_html=True)

        # Chatbot
        st.markdown("""<p style="margin-top: 40px; margin-bottom: 15px; width: 100%;"><span style="background: rgba(255,255,255,0.25); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px); padding: 20px 30px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 8px 32px rgba(0,0,0,0.15); display: block; font-size: 33px; font-weight: 700; color: #000;">🤖 AI Plant Doctor - Ask Me Anything!</span></p>""", unsafe_allow_html=True)

        if st.session_state.chat_history:
            with st.container():
                st.markdown("""<div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 20px; border-radius: 15px; max-height: 400px; overflow-y: auto; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.2);">""", unsafe_allow_html=True)
                for chat in st.session_state.chat_history:
                    st.markdown(f"""<div style="background: rgba(255,255,255,0.35); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 12px 16px; border-radius: 12px; margin-bottom: 8px; border-left: 5px solid #4CAF50; color: #000;"><b>🧑 You:</b> {chat['question']}</div>""", unsafe_allow_html=True)
                    st.markdown(f"""<div style="background: rgba(255,255,255,0.35); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 12px 16px; border-radius: 12px; margin-bottom: 15px; border-left: 5px solid #2196F3; color: #000;"><b>🤖 Plant Doctor:</b> {chat['answer']}</div>""", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        col_input, col_btn = st.columns([4, 1])
        with col_input:
            user_question = st.text_input("Ask:", placeholder="e.g., Why are my leaves turning yellow?", label_visibility="collapsed", key="chat_input")
        with col_btn:
            send_button = st.button("🚀 Send", use_container_width=True)

        if send_button and user_question:
            with st.spinner("🤖 Plant Doctor is thinking..."):
                # FIX 3: Use correct parameter name 'plant_type' (not 'plant_name'/'sensor_data')
                plant_for_chat = selected_plant if selected_plant_raw != "Select a Plant" else "tomato"
                answer = chat_with_plant_doctor(user_question, plant_type=plant_for_chat)
                st.session_state.chat_history.append({'question': user_question, 'answer': answer})
                st.rerun()

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat History"):
                st.session_state.chat_history = []
                st.rerun()