import machine
import time
import json
import network
import socket
import dht

# ============================================
# WIFI CREDENTIALS LIST
# ============================================
WIFI_NETWORKS = [
    ("FTTH-AD9C",     "12345678"),
    ("Panda",         "saloni12"),
    ("CS260",         "3yj5zk"),
    ("MobileHotspot", "hotspot789"),
]

# ============================================
# PC IP LIST (tries each one until one works)
# ============================================
PC_IPS = [
    "192.168.1.2",
    "192.168.1.3",
    "192.168.1.4",
    "192.168.1.5",
]
API_PORT = 5000

# ============================================
# SENSOR SETUP
# ============================================
try:
    print("📌 Initializing DHT11 sensor on Pin D4 (GPIO 4)...")
    dht_sensor = dht.DHT11(machine.Pin(4))
    print("✓ DHT11 initialized")
except Exception as e:
    print(f"❌ DHT11 Error: {e}")
    dht_sensor = None

try:
    print("📌 Initializing light sensor on Pin D34 (GPIO 34)...")
    light_sensor = machine.ADC(machine.Pin(34))
    light_sensor.atten(machine.ADC.ATTN_11DB)
    print("✓ Light sensor initialized")
except Exception as e:
    print(f"❌ Light sensor error: {e}")
    light_sensor = None

try:
    print("📌 Initializing soil sensor on Pin D35 (GPIO 35)...")
    soil_sensor = machine.ADC(machine.Pin(35))
    soil_sensor.atten(machine.ADC.ATTN_11DB)
    print("✓ Soil sensor initialized")
except Exception as e:
    print(f"❌ Soil sensor error: {e}")
    soil_sensor = None

try:
    print("📌 Initializing relay on Pin 18...")
    relay = machine.Pin(18, machine.Pin.OUT)
    relay.value(0)
    print("✓ Relay initialized")
except Exception as e:
    print(f"❌ Relay error: {e}")
    relay = None

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_moisture():
    try:
        if soil_sensor is None:
            return 50.0
        raw = soil_sensor.read()
        return round(max(0, min(100, ((4095 - raw) / (4095 - 1500)) * 100)), 1)
    except Exception as e:
        print(f"⚠️  Moisture read error: {e}")
        return 50.0

def get_light():
    try:
        if light_sensor is None:
            return 300.0
        raw = light_sensor.read()
        return round((raw / 4095) * 1000, 1)
    except Exception as e:
        print(f"⚠️  Light read error: {e}")
        return 300.0

def get_dht_data(retries=5):
    if dht_sensor is None:
        return 0.0, 0.0

    for attempt in range(retries):
        try:
            dht_sensor.measure()
            time.sleep_ms(200)
            temp  = round(dht_sensor.temperature(), 1)
            humid = round(dht_sensor.humidity(), 1)

            if temp > 0 or humid > 0:
                if attempt > 0:
                    print(f"✅ DHT11 OK on attempt {attempt + 1}")
                return temp, humid
            else:
                print(f"🔄 DHT11 attempt {attempt + 1}: zero values, retrying...")
        except Exception as e:
            print(f"⚠️  DHT11 attempt {attempt + 1} error: {e}")

        time.sleep(2)

    print("❌ DHT11 failed all retries, using 0.0")
    return 0.0, 0.0

def connect_wifi():
    """Try each saved WiFi network until one connects."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("✅ Already connected:", wlan.ifconfig()[0])
        return True

    print("📡 Scanning for available networks...")
    try:
        available = [net[0].decode() for net in wlan.scan()]
        print("Found networks:", available)
    except:
        available = []

    for ssid, password in WIFI_NETWORKS:
        if available and ssid not in available:
            print(f"⏭️  '{ssid}' not in range, skipping...")
            continue

        print(f"🔄 Trying: {ssid}")
        wlan.connect(ssid, password)

        for _ in range(15):
            if wlan.isconnected():
                break
            time.sleep(1)

        if wlan.isconnected():
            print(f"✅ Connected to '{ssid}'! IP: {wlan.ifconfig()[0]}")
            return True
        else:
            print(f"❌ Failed: {ssid}")
            wlan.disconnect()
            time.sleep(1)

    print("❌ Could not connect to any WiFi network.")
    return False

def try_send(pc_ip, payload):
    """Try sending to a single IP. Returns True if successful."""
    sock = None
    try:
        request = (
            "POST /sensor HTTP/1.1\r\n"
            f"Host: {pc_ip}:{API_PORT}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Connection: close\r\n"
            "\r\n"
            f"{payload}"
        )
        sock = socket.socket()
        sock.settimeout(20)
        sock.connect((pc_ip, API_PORT))
        sock.send(request.encode())
        sock.recv(1024)
        sock.close()
        return True
    except Exception as e:
        print(f"❌ {pc_ip} error: {e}")
        if sock:
            try:
                sock.close()
            except:
                pass
        return False

def send_to_api(data, working_ip):
    """
    Smart sender:
    - First tries the last known working IP directly
    - Only scans all IPs if that fails
    - Returns the new working IP so it is remembered
    """
    payload = json.dumps(data)

    # Step 1 — Try last known working IP first
    if working_ip:
        print(f"📤 Sending to last known IP: {working_ip}")
        if try_send(working_ip, payload):
            print(f"🚀 Data Sent Successfully to {working_ip}")
            return working_ip  # still works, keep using it

        print(f"⚠️  {working_ip} failed, scanning all IPs...")

    # Step 2 — Scan all IPs to find a new working one
    for pc_ip in PC_IPS:
        if pc_ip == working_ip:
            continue  # already tried this one above
        print(f"🔍 Trying: {pc_ip}")
        if try_send(pc_ip, payload):
            print(f"🚀 Data Sent Successfully to {pc_ip} (new IP saved!)")
            return pc_ip  # remember this new working IP

    print("❌ All IPs failed")
    return working_ip  # keep last known even if failed, try again next round

# ============================================
# MAIN LOOP
# ============================================

print("\n=== ESP32 Sensor System ===\n")

wifi_ok = connect_wifi()
working_ip = None  # no known working IP yet — will scan on first send

# DHT11 warm-up
if dht_sensor:
    print("🔥 Warming up DHT11...")
    for i in range(2):
        try:
            dht_sensor.measure()
            print(f"  Warm-up read {i+1} done")
        except:
            pass
        time.sleep(2)
    print("✅ DHT11 warm-up complete\n")

while True:
    # Reconnect WiFi if dropped
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print("⚠️  WiFi dropped! Reconnecting...")
        wifi_ok = connect_wifi()
        working_ip = None  # reset IP memory after reconnect

    try:
        temperature, humidity = get_dht_data()
        moisture  = get_moisture()
        light_lux = get_light()

        data = {
            "moisture":    moisture,
            "temperature": temperature,
            "humidity":    humidity,
            "light_lux":   light_lux
        }

        print(f"📊 Current Stats: {data}")

        if wifi_ok:
            working_ip = send_to_api(data, working_ip)

    except Exception as e:
        print(f"Loop Error: {e}")
        import traceback
        traceback.print_exc()

    time.sleep(30)