from fpdf import FPDF
from flask import Flask, request, jsonify, render_template, send_file, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy 
from functools import wraps
import psutil
import datetime
import time
import os
import numpy as np
from sklearn.linear_model import LinearRegression
from twilio.rest import Client

app = Flask(__name__)

# ✅ SECURITY & DATABASE CONFIGURATION
app.secret_key = "SUPER_SECRET_KEY_CHANGE_THIS"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sentinel.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app) 

API_SECRET_KEY = "Sentinel-X99-Secure-Token"
ADMIN_USER = "admin"
ADMIN_PASS = "secure2026"

# ✅ Twilio Keys
TWILIO_SID = "AC1c973015b194761b1a9a65736d7951bb"
TWILIO_TOKEN = "c25ebce926e56bfc4d8ecb3afb9f8a0f"
TWILIO_FROM = "+17755879396"
TWILIO_TO = "+919082123246"

# Initialize Twilio
sms_client = None
if "PASTE" not in TWILIO_FROM:
    try:
        sms_client = Client(TWILIO_SID, TWILIO_TOKEN)
        print("✅ SMS System Online")
    except Exception as e:
        print(f"⚠️ Twilio Connection Failed: {e}")
else:
    print("⚠️ NOTE: SMS is disabled until you paste your Twilio Number.")

# --- DATABASE MODELS (TABLES) ---
class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)
    temperature = db.Column(db.Float)
    gas = db.Column(db.Integer)
    motion = db.Column(db.Integer)

class IncidentLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)
    event_type = db.Column(db.String(50))
    value = db.Column(db.String(50))
    status = db.Column(db.String(20))

# --- GLOBAL STORAGE (For Real-Time Dashboard) ---
system_state = {
    "iot_metrics": { "temperature": 0, "gas_level": 0, "motion": 0, "last_update": "Waiting..." },
    "security_metrics": { "cpu_usage": 0, "ram_usage": 0, "alert_status": "SAFE", "ml_prediction": "Calibrating..." },
    "system_controls": { "sprinklers": False, "alarm": False, "door_lock": True, "firewall": "Standard" }
}

# --- LOGIC VARIABLES ---
last_alert_sent = "SAFE"
last_ddos_time = 0
last_sms_time = 0

# --- HELPER FUNCTIONS ---
def log_incident(event_type, value):
    """Writes to SQLite Database"""
    new_incident = IncidentLog(event_type=event_type, value=str(value), status="CRITICAL")
    db.session.add(new_incident)
    db.session.commit()
    print(f"💾 Incident Logged to DB: {event_type}")

def send_sms_alert(message):
    global last_alert_sent, last_sms_time
    current_time = time.time()
    if message != last_alert_sent and (current_time - last_sms_time > 60):
        if sms_client:
            try:
                sms_client.messages.create(body=f"🚨 SecureSentinel: {message}", from_=TWILIO_FROM, to=TWILIO_TO)
                print(f"📲 SMS Sent: {message}")
                last_alert_sent = message
                last_sms_time = current_time 
            except Exception as e:
                print(f"❌ SMS Failed: {e}")
    elif not sms_client:
        last_alert_sent = message

def run_ml_prediction():
    """Fetches last 20 readings from DB for Prediction"""
    history = SensorData.query.order_by(SensorData.id.desc()).limit(20).all()
    
    if len(history) < 10: return "Gathering Data..."

    temps = [r.temperature for r in reversed(history)]

    X = np.array(range(len(temps))).reshape(-1, 1)
    y = np.array(temps).reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, y)
    
    predicted_temp = model.predict(np.array([[len(temps) + 5]]))[0][0]
    trend = model.coef_[0][0]
    
    if predicted_temp > 50: return f"⚠️ OVERHEAT RISK (Pred: {predicted_temp:.1f}°C)"
    elif trend > 0.5: return "📈 Rapid Warming Detected"
    elif trend < -0.5: return "📉 Cooling Down"
    else: return "✅ Thermal Stability Normal"

# --- DECORATORS ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-Key') != API_SECRET_KEY:
            return jsonify({"error": "Unauthorized Access"}), 403
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="❌ Access Denied")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/api/telemetry', methods=['POST'])
@require_api_key
def update_telemetry():
    data = request.json
    temp = data.get('temperature', 0)
    gas = data.get('gas', 0)
    motion = data.get('motion', 0)

    # Update In-Memory State
    system_state['iot_metrics']['temperature'] = temp
    system_state['iot_metrics']['gas_level'] = gas
    system_state['iot_metrics']['motion'] = motion
    system_state['iot_metrics']['last_update'] = datetime.datetime.now().strftime("%H:%M:%S")

    # SAVE TO DATABASE
    new_reading = SensorData(temperature=temp, gas=gas, motion=motion)
    db.session.add(new_reading)
    db.session.commit()

    return jsonify({"status": "success"}), 200

@app.route('/api/monitor', methods=['GET'])
@login_required
def get_monitor_data():
    global last_ddos_time
    cpu = psutil.cpu_percent(interval=None) 
    ram = psutil.virtual_memory().percent
    current_temp = system_state['iot_metrics']['temperature']
    gas = system_state['iot_metrics']['gas_level']
    motion = system_state['iot_metrics']['motion']
    
    prediction_msg = run_ml_prediction()
    alert_msg = "SAFE"
    
    # RESET CONTROLS
    system_state['system_controls'] = {"sprinklers": False, "alarm": False, "door_lock": True, "firewall": "Standard"}

    # --- THREAT INTELLIGENCE LOGIC ---
    if gas > 1000:
        alert_msg = "🔥 DANGER: FIRE - DEFENSE ACTIVE"
        log_incident("FIRE DETECTED", f"Gas: {gas}")
        system_state['system_controls'].update({"sprinklers": True, "door_lock": False, "alarm": True})

    elif cpu > 50 and current_temp > 30 and gas < 500:
        alert_msg = "☣️ MALWARE: CRYPTO-MINER DETECTED"
        if "MALWARE" not in system_state['security_metrics']['alert_status']:
            log_incident("MALWARE DETECTED", f"CPU: {cpu}% | Temp: {current_temp}C")
        system_state['system_controls']['firewall'] = "⛔ PROCESS KILL"

    elif cpu > 40 or (time.time() - last_ddos_time < 5):
        if cpu > 40: 
            last_ddos_time = time.time()
            log_incident("DDoS ATTACK", f"CPU: {cpu}%")
        alert_msg = "⚠️ CRITICAL: DDoS - FIREWALL LOCKDOWN"
        system_state['system_controls']['firewall'] = "⛔ BLOCKING TRAFFIC"

    elif motion == 1:
        alert_msg = "👁️ INTRUDER - ALARM TRIGGERED"
        system_state['system_controls']['alarm'] = True

    if "SAFE" not in alert_msg:
        send_sms_alert(alert_msg)

    system_state['security_metrics'].update({
        "cpu_usage": cpu, 
        "ram_usage": ram, 
        "alert_status": alert_msg, 
        "ml_prediction": prediction_msg
    })
    return jsonify(system_state)

@app.route('/api/report', methods=['GET'])
@login_required
def download_report():
    # Fetch Incidents from DB
    incidents = IncidentLog.query.order_by(IncidentLog.timestamp.desc()).all()
    
    if not incidents:
        return jsonify({"error": "No logs found"}), 404

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_font("Arial", 'B', 16)
    
    # ✅ RENAMED HERE
    pdf.cell(200, 10, txt="Cyber-Physical SOC - Security Audit Report", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(10)
    
    # Calculate Stats
    total = len(incidents)
    fire = sum(1 for i in incidents if "FIRE" in i.event_type)
    ddos = sum(1 for i in incidents if "DDoS" in i.event_type)
    malware = sum(1 for i in incidents if "MALWARE" in i.event_type)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Executive Summary:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"- Total Security Incidents: {total}", ln=True)
    pdf.cell(0, 8, f"- Fire/Hazard Alerts: {fire}", ln=True)
    pdf.cell(0, 8, f"- Network DDoS Attempts: {ddos}", ln=True)
    pdf.cell(0, 8, f"- Crypto-Mining Events: {malware}", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(50, 10, "Timestamp", 1, 0, 'C', 1)
    pdf.cell(50, 10, "Event Type", 1, 0, 'C', 1)
    pdf.cell(50, 10, "Value", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Status", 1, 1, 'C', 1)
    pdf.set_font("Arial", size=9)
    
    for i in incidents[:20]: # Last 20
        pdf.cell(50, 10, str(i.timestamp), 1)
        pdf.cell(50, 10, i.event_type, 1)
        pdf.cell(50, 10, i.value, 1)
        pdf.cell(40, 10, i.status, 1, 1)

    report_filename = "Security_Report.pdf"
    pdf.output(report_filename)
    return send_file(report_filename, as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
        print("✅ Database Connected: sentinel.db")
    
    print("🚀 Cyber-Physical SOC Server Starting...")
    app.run(host='0.0.0.0', port=5001, debug=True)