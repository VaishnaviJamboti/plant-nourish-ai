import tensorflow as tf
import numpy as np
import os
import requests
import json
import socket
from dotenv import load_dotenv

# ============================================================
# DNS FIX — Forces reliable DNS resolution for api.groq.com
# Works on any network including college/campus networks
# ============================================================

# Known resolved IPs for api.groq.com (from nslookup)
GROQ_IPS = [
    "104.18.38.236",
    "172.64.149.20",
]

_original_getaddrinfo = socket.getaddrinfo

def _patched_getaddrinfo(host, port, *args, **kwargs):
    """
    If normal DNS resolution fails for api.groq.com,
    fall back to hardcoded IPs so the chatbot works on any network.
    """
    if host == "api.groq.com":
        try:
            # Try normal DNS first
            result = _original_getaddrinfo(host, port, *args, **kwargs)
            return result
        except Exception:
            # DNS failed — use hardcoded IPs as fallback
            print("⚠️  DNS failed for api.groq.com — using fallback IP")
            for ip in GROQ_IPS:
                try:
                    return _original_getaddrinfo(ip, port, *args, **kwargs)
                except Exception:
                    continue
            raise  # all fallbacks failed
    return _original_getaddrinfo(host, port, *args, **kwargs)

# Apply the DNS patch globally
socket.getaddrinfo = _patched_getaddrinfo

# ============================================================
# Load API key from enviro.env file
# ============================================================
load_dotenv("enviro.env")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Store models in memory
_interpreters = {}

# ============================================================
# Stage identification models  (growth stage per plant)
# ============================================================
STAGE_MODEL_MAP = {
    "Chilli Pepper": ("chillipepper.tflite",    "chillipepper_labels"),
    "Tomato":        ("tomato.tflite",           "tomato_labels"),
    "Cucumber":      ("cucumber.tflite",          "cucumber_labels"),
    "Coriander":     ("coriander_model.tflite",   "coriander_labels"),
    "Brinjal":       ("brinjal_model.tflite",     "brinjal_labels"),
}

# ============================================================
# Disease class ranges for COMBINED disease.tflite model
# ============================================================
DISEASE_CLASS_RANGES = {
    "Chilli Pepper": (0, 3),    # Classes 0-3
    "Coriander":     (4, 7),    # Classes 4-7
    "Cucumber":      (8, 11),   # Classes 8-11
    "Tomato":        (12, 15),  # Classes 12-15
    "Brinjal":       (16, 19),  # Classes 16-19
}

# ============================================================
# FALLBACK KNOWLEDGE BASE (used if API call fails)
# ============================================================
PLANT_KNOWLEDGE = {
    "Chilli Pepper": {
        "common_diseases": ["Chilli_Anthracnose", "Cercospora Spot", "Leaf Curl", "Bacterial Wilt"],
        "watering": "Water every 2-3 days. Keep soil moist but not waterlogged.",
        "sunlight": "Requires 6-8 hours of direct sunlight daily.",
        "temperature": "Ideal temperature: 20-30°C. Avoid temperatures below 15°C.",
        "fertilizer": "Feed every 2 weeks with balanced NPK (10:10:10) or potassium-rich fertilizer.",
        "spacing": "Plant seedlings 30-45 cm apart.",
        "harvest": "Harvest when fruits turn red (60-90 days after flowering).",
    },
    "Tomato": {
        "common_diseases": ["Early_Blight", "Late_Blight", "Yellow_Leaf_Curl", "Septoria_Leaf_Spot"],
        "watering": "Water deeply at the base once daily. Avoid wetting leaves.",
        "sunlight": "Requires 6-8 hours of direct sunlight daily.",
        "temperature": "Ideal temperature: 21-28°C. Fruiting stops below 12°C or above 35°C.",
        "fertilizer": "Apply balanced fertilizer (10:10:10) every 2 weeks. High potassium supports fruiting.",
        "spacing": "Plant seedlings 45-60 cm apart.",
        "harvest": "Harvest when fully ripe (60-85 days after flowering).",
    },
    "Cucumber": {
        "common_diseases": ["Powdery_Mildew", "Downy_Mildew", "Mosaic_Virus", "Angular_Leaf_Spot"],
        "watering": "Water deeply every 2-3 days. Soil should stay consistently moist.",
        "sunlight": "Requires 6-8 hours of direct sunlight daily.",
        "temperature": "Ideal temperature: 20-30°C. Growth stops below 15°C.",
        "fertilizer": "Feed every 10-14 days with nitrogen-rich fertilizer.",
        "spacing": "Plant seedlings 30-45 cm apart. Use trellises for vertical growth.",
        "harvest": "Harvest when 15-20 cm long for best taste (45-60 days after flowering).",
    },
    "Coriander": {
        "common_diseases": ["Powdery_Mildew", "Stem_Gall", "Bacterial_Spot", "Fusarium_Wilt"],
        "watering": "Water regularly but don't overwater. Soil should be moist, not wet.",
        "sunlight": "Prefers partial shade. 4-6 hours of sunlight is optimal.",
        "temperature": "Ideal temperature: 15-25°C. Prefers cooler climate.",
        "fertilizer": "Light feeding with balanced fertilizer (10:10:10) every 3 weeks.",
        "spacing": "Sow seeds 15-20 cm apart. Can be grown in containers.",
        "harvest": "Harvest leaves in 3-4 weeks. Seeds ready in 8-10 weeks.",
    },
    "Brinjal": {
        "common_diseases": ["Phomopsis_Blight", "Little_Leaf", "Cercospora_Spot", "Mosaic_Virus"],
        "watering": "Water every 2-3 days. Keep soil moist but well-drained.",
        "sunlight": "Requires 6-8 hours of direct sunlight daily.",
        "temperature": "Ideal temperature: 20-28°C. Sensitive to cold.",
        "fertilizer": "Feed every 2 weeks with balanced NPK (10:10:10).",
        "spacing": "Plant seedlings 60 cm apart for good air circulation.",
        "harvest": "Harvest when fruit is glossy and firm (60-90 days after flowering).",
    },
}

# ============================================================
# HELPERS
# ============================================================

def _load_labels(label_filename):
    """Read label file and return list of class names."""
    label_path = os.path.join("models", label_filename)
    if not os.path.exists(label_path):
        return []
    with open(label_path, "r") as f:
        lines = []
        for line in f.readlines():
            line = line.strip()
            if line:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    lines.append(parts[1])
                else:
                    lines.append(line)
        return lines


def load_model(plant_type, mode="stage"):
    """
    Load a TFLite interpreter from the 'models' folder.
    mode='stage'   → growth stage identification model (per-plant)
    mode='disease' → disease detection model (combined disease.tflite)
    Returns (interpreter, labels_list) or (None, [])
    """
    global _interpreters

    if mode == "stage":
        entry = STAGE_MODEL_MAP.get(plant_type)
        if not entry:
            return None, []
        model_filename, label_filename = entry
    else:
        model_filename = "disease.tflite"
        label_filename = "disease_labels.txt"

    model_path = os.path.join("models", model_filename)
    cache_key = model_path

    if cache_key not in _interpreters:
        try:
            if os.path.exists(model_path):
                interpreter = tf.lite.Interpreter(model_path=model_path)
                interpreter.allocate_tensors()
                _interpreters[cache_key] = interpreter
            else:
                return None, []
        except Exception:
            return None, []

    labels = _load_labels(label_filename)
    return _interpreters.get(cache_key), labels


# ============================================================
# INFERENCE
# ============================================================

def _run_tflite(interpreter, image_array):
    """Run inference and return raw prediction array."""
    input_details  = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    img_resized    = tf.image.resize(image_array, [224, 224])
    img_normalized = np.array(img_resized, dtype=np.float32) / 255.0
    img_batch      = np.expand_dims(img_normalized, axis=0)

    interpreter.set_tensor(input_details[0]['index'], img_batch)
    interpreter.invoke()
    return interpreter.get_tensor(output_details[0]['index'])


def run_inference(image_array, plant_type):
    """Run STAGE inference — returns {'stage': ..., 'confidence': ...}"""
    try:
        interpreter, labels = load_model(plant_type, mode="stage")
        if interpreter is None:
            return {"error": f"Stage model for '{plant_type}' not found in models/"}

        prediction = _run_tflite(interpreter, image_array)
        class_idx  = int(np.argmax(prediction))
        conf       = float(np.max(prediction))

        if labels and class_idx < len(labels):
            stage_name = labels[class_idx]
        else:
            fallback = ["Seedling", "Vegetative", "Flowering", "Fruiting"]
            stage_name = fallback[class_idx] if class_idx < len(fallback) else "Unknown"

        return {"stage": stage_name, "confidence": conf}
    except Exception as e:
        return {"error": str(e)}


def run_disease_inference(image_array, plant_type):
    """Run DISEASE inference using combined disease.tflite — returns {'disease': ..., 'confidence': ...}"""
    try:
        interpreter, labels = load_model(plant_type, mode="disease")
        if interpreter is None:
            return {"error": "Disease model not found in models/"}

        prediction = _run_tflite(interpreter, image_array)
        class_idx  = int(np.argmax(prediction))
        conf       = float(np.max(prediction))

        if labels and class_idx < len(labels):
            disease_name = labels[class_idx]
            plant_prefix = plant_type.lower().replace(" ", "_")
            if disease_name.lower().startswith(plant_prefix + "_"):
                disease_name = disease_name.split("_", 1)[1]
        else:
            disease_name = f"Class_{class_idx}"

        return {"disease": disease_name, "confidence": conf}
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# AI-POWERED CHATBOT  (Groq API — llama3)
# ============================================================

_chat_history = []

def chat_with_plant_doctor(question, plant_type="Tomato"):
    global _chat_history

    plant_data = PLANT_KNOWLEDGE.get(plant_type, PLANT_KNOWLEDGE["Tomato"])

    system_prompt = f"""You are PlantDoc, an expert agricultural assistant specializing in plant health, 
diseases, and care. The farmer is currently growing {plant_type}.

Key facts about {plant_type}:
- Watering: {plant_data['watering']}
- Sunlight: {plant_data['sunlight']}
- Temperature: {plant_data['temperature']}
- Fertilizer: {plant_data['fertilizer']}
- Spacing: {plant_data['spacing']}
- Harvest: {plant_data['harvest']}
- Common diseases: {', '.join(plant_data['common_diseases'])}

Instructions:
- Answer ONLY about plant care, farming, agriculture, and related topics.
- If asked about unrelated topics, politely redirect to plant care.
- Use simple language. Add relevant emojis to make responses friendly.
- Keep answers concise (under 150 words) but helpful.
- Always give practical, actionable advice."""

    _chat_history.append({"role": "user", "content": question})
    recent_history = _chat_history[-10:]
    messages = [{"role": "system", "content": system_prompt}] + recent_history

    try:
        import httpx
        with httpx.Client(http2=True, timeout=20, verify=True) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": messages,
                    "max_tokens": 300,
                    "temperature": 0.7,
                },
            )

        if response.status_code == 200:
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            _chat_history.append({"role": "assistant", "content": reply})
            if len(_chat_history) > 20:
                _chat_history = _chat_history[-20:]
            return reply
        else:
            error_info = response.json().get("error", {}).get("message", "Unknown error")
            return _fallback_response(question, plant_type, plant_data, error_info)

    except Exception as e:
        return _fallback_response(question, plant_type, plant_data, str(e))

def _fallback_response(question, plant_type, plant_data, error_info=""):
    """Keyword-based fallback if API is unavailable."""
    q = question.lower()

    if any(w in q for w in ["water", "how often", "thirsty", "dry"]):
        return f"🌊 **Watering Guide for {plant_type}:**\n{plant_data['watering']}"
    elif any(w in q for w in ["light", "sun", "shade"]):
        return f"☀️ **Sunlight for {plant_type}:**\n{plant_data['sunlight']}"
    elif any(w in q for w in ["temperature", "cold", "hot", "heat"]):
        return f"🌡️ **Temperature for {plant_type}:**\n{plant_data['temperature']}"
    elif any(w in q for w in ["fertilizer", "feed", "nutrient", "npk"]):
        return f"🌿 **Fertilizer for {plant_type}:**\n{plant_data['fertilizer']}"
    elif any(w in q for w in ["harvest", "pick", "ripe", "ready"]):
        return f"🍴 **Harvesting {plant_type}:**\n{plant_data['harvest']}"
    elif any(w in q for w in ["disease", "sick", "spots", "blight", "wilt", "mold"]):
        diseases = ", ".join(plant_data['common_diseases'])
        return (f"🔬 **Common Diseases in {plant_type}:**\n{diseases}\n\n"
                f"💡 Prevention: Good air circulation, water at the base, remove infected leaves.")
    elif "yellow" in q:
        return (f"🟡 **Yellow Leaves on {plant_type}:**\n"
                "Possible causes: Overwatering, nitrogen deficiency, or disease.\n"
                "💡 Check soil moisture first, then apply balanced fertilizer if needed.")
    elif any(w in q for w in ["wilt", "droop"]):
        return (f"💔 **Wilting {plant_type}:**\n"
                "Causes: Underwatering, root damage, or fungal infection.\n"
                "💡 Water thoroughly and check if soil is soggy. Improve drainage if needed.")
    else:
        return (f"🌱 **PlantDoc is here!** Ask me about watering, sunlight, temperature, "
                f"fertilizer, diseases, or harvesting your {plant_type}.\n\n"
                f"_(Note: AI service temporarily unavailable — {error_info})_")


def reset_chat_history():
    """Call this when the user switches plant type to clear conversation context."""
    global _chat_history
    _chat_history = []


# ============================================================
# PUBLIC API  (called by app1.py)
# ============================================================

def get_plant_analysis(image_array, plant_type, mode="stage"):
    """
    Main analysis function.
    mode='stage'   → identifies growth stage
    mode='disease' → identifies disease
    """
    if mode == "disease":
        result = run_disease_inference(image_array, plant_type)
        if "error" in result:
            return {"status": "error", "message": result["error"]}

        disease = result["disease"]
        confidence = f"{result['confidence'] * 100:.1f}%"

        if "healthy" in disease.lower():
            recommendation = "Your plant looks healthy! Keep up the care routine."
        else:
            recommendation = (f"Detected: {disease}. Remove affected leaves, "
                              "improve air circulation, and consider a suitable fungicide/pesticide.")
        return {
            "status":         "success",
            "disease":        disease,
            "confidence":     confidence,
            "recommendation": recommendation,
            "message":        f"AI identified {plant_type} as: {disease}."
        }

    else:  # stage
        result = run_inference(image_array, plant_type)
        if "error" in result:
            return {"status": "error", "message": result["error"]}

        return {
            "status":     "success",
            "stage":      result["stage"],
            "confidence": f"{result['confidence'] * 100:.1f}%",
            "message":    f"AI identified {plant_type} in {result['stage']} stage."
        }


def get_global_diagnosis(soil_moisture, humidity, temperature, light_level):
    """Analyzes health based on sensor data."""
    health_score = 0
    if 30 <= soil_moisture <= 80: health_score += 40
    if 40 <= humidity     <= 85:  health_score += 30
    if 18 <= temperature  <= 32:  health_score += 30

    status = "Excellent" if health_score >= 80 else "Fair" if health_score >= 50 else "Poor"
    color  = "green"     if status == "Excellent" else "orange" if status == "Fair" else "red"
    return {"status": status, "score": health_score, "color": color}