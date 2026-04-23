# plant-nourish-ai
# Plant Nourish AI 🌱

An intelligent plant monitoring and health recommendation system using ESP32, AI models, and real-time data visualization.

## Features

✨ **Live Sensor Monitoring** — Real-time temperature, humidity, light, and soil moisture tracking
🤖 **AI Plant Doctor** — Chatbot powered by Groq LLaMA for plant care advice
🎯 **Growth Stage Detection** — TensorFlow Lite models identify plant growth phases
🦠 **Disease Detection** — AI-powered leaf disease recognition
📊 **Health Recommendations** — Personalized care tips based on sensor data and plant type
💧 **Auto-Watering Control** — Relay control for automatic irrigation (optional)

## Tech Stack

- **Hardware:** ESP32 microcontroller, DHT11 sensor, soil moisture sensor, light sensor
- **Backend:** Flask API, PostgreSQL database
- **Frontend:** Streamlit dashboard
- **AI/ML:** TensorFlow Lite models, Groq LLaMA API
- **Deployment:** Render, Railway, or local Docker

## Hardware Setup

### Components Required
- ESP32 development board
- DHT11 temperature/humidity sensor
- Capacitive soil moisture sensor
- Light intensity sensor (LDR/BH1750)
- 5V relay module
- USB power adapter

### Wiring
```
ESP32 Pin  → Sensor
GPIO 4     → DHT11
GPIO 34    → Light sensor (ADC)
GPIO 35    → Soil sensor (ADC)
GPIO 18    → Relay control
```

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/plant-nourish-ai.git
cd plant-nourish-ai
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Create `.env` file:
```
GROQ_API_KEY=your_api_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/plant_db
```

### 5. Run Application
```bash
streamlit run app1.py
```

Open browser → http://localhost:8501

## ESP32 Setup

### 1. Flash MicroPython
Download MicroPython for ESP32 from [micropython.org](https://micropython.org)

### 2. Upload main.py
Use Thonny IDE to upload the firmware files to ESP32

### 3. Configure WiFi
Edit main.py and add your network:
```python
WIFI_NETWORKS = [
    ("Your_WiFi_SSID", "Your_Password"),
]
```

## API Endpoints

### `/sensor` (POST)
Receives sensor data from ESP32
```json
{
  "temperature": 28.5,
  "humidity": 72,
  "moisture": 45,
  "light_lux": 1000
}
```

### `/health` (GET)
Health check for deployment monitoring

## Deployment

### Render
1. Push code to GitHub
2. Go to [render.com](https://render.com)
3. Create new Web Service
4. Select your GitHub repo
5. Add PostgreSQL plugin
6. Set environment variables
7. Deploy! 🚀

## AI Models

Three TensorFlow Lite models included:

| Model | Purpose | Input | Output |
|-------|---------|-------|--------|
| Growth Detection | Plant stage identification | Leaf image | Stage label |
| Disease Detection | Identify leaf diseases | Leaf image | Disease label |
| Health Score | Overall plant wellness | Sensor data | Score (0-100) |

## Plant Types Supported

- Tomato
- Chilli Pepper
- Cucumber
- Basil
- Mint
- And more...

## Database Schema

```
esp32_live
├── id (uuid)
├── temperature (float)
├── humidity (float)
├── moisture (float)
├── light_lux (float)
└── received_at (timestamp)

growth_stages
├── plant_id (uuid)
├── stage_name (text)
├── optimal_temp (float)
├── optimal_humidity (float)
└── optimal_moisture (float)
```

## Troubleshooting

### ESP32 not connecting
- Check WiFi SSID and password
- Verify laptop and ESP32 are on same network
- Check IP address with `ipconfig` (Windows)

### Sensor readings are 0
- Check wiring connections
- Verify pins match main.py configuration
- Test sensor directly with ohmmeter

### Flask API not starting
- Ensure port 5000 is not in use
- Check `requirements.txt` is installed
- Run `python api.py` manually to see errors

### Streamlit not loading
- Clear browser cache (Ctrl+Shift+Del)
- Restart Streamlit: `streamlit run app1.py`
- Check internet connection for AI features

## Contributing

Feel free to submit issues and pull requests!

## License

MIT License - see LICENSE file

## Author

Your Name / GitHub Username

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the documentation in `/docs`
- Email: your.email@example.com

---

**Made with ❤️ for plant lovers and IoT enthusiasts**
