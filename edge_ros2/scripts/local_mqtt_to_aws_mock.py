import json
import time
import requests
import paho.mqtt.client as mqtt

# ─── Configuration (matches local dev environments) ───────────
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC_VIOLATION = "footwatch/+/+/violation"
MQTT_TOPIC_TELEMETRY = "footwatch/+/+/health"

INGEST_API_URL = "http://127.0.0.1:8000/v1"
INGEST_API_KEY = "dev-key"  # Default in footwatch/Backend config

HEADERS = {
    "x-api-key": INGEST_API_KEY,
    "Content-Type": "application/json"
}

print("=========================================================")
print("🌐 FOOTWATCH LOCAL AWS IOT MOCK BRIDGE")
print(f"Listening to MQTT: {MQTT_BROKER}:{MQTT_PORT}")
print(f"Forwarding to HTTP: {INGEST_API_URL}")
print("=========================================================\n")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[+] Connected to local MQTT Broker (from edge_ros2)")
        client.subscribe(MQTT_TOPIC_VIOLATION)
        client.subscribe(MQTT_TOPIC_TELEMETRY)
        print(f"[-] Subscribed to {MQTT_TOPIC_VIOLATION}")
        print(f"[-] Subscribed to {MQTT_TOPIC_TELEMETRY}\n")
    else:
        print(f"[!] Failed to connect to MQTT broker. Code: {rc}")


def on_message(client, userdata, msg):
    topic = msg.topic
    print(f"[{time.strftime('%H:%M:%S')}] Received MQTT message on topic: {topic}")
    
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
    except json.JSONDecodeError:
        print("[!] Invalid JSON payload received. Skipping.")
        return

    # Route based on topic
    if "violation" in topic:
        # edge_ros2 schema uses timestamp_utc, backend might expect timestamp. Send as is.
        print(f"    -> Forwarding Violation: {payload.get('violation_id')}")
        
        # We simulate the AWS IoT Rule by passing an idempotency key 
        headers = HEADERS.copy()
        headers["x-idempotency-key"] = f"idem-{payload.get('violation_id')}"
        
        try:
            res = requests.post(
                f"{INGEST_API_URL}/violations",
                json=payload,
                headers=headers,
                timeout=5
            )
            print(f"    <- Backend Response: {res.status_code} {res.text}")
        except Exception as e:
            print(f"    [!] Error forwarding to Ingest API: {e}")

    elif "health" in topic:
        print(f"    -> Forwarding Telemetry from: {payload.get('device_id')}")
        try:
            res = requests.post(
                f"{INGEST_API_URL}/telemetry",
                json=payload,
                headers=HEADERS,
                timeout=5
            )
            print(f"    <- Backend Response: {res.status_code} {res.text}")
        except Exception as e:
            print(f"    [!] Error forwarding to Ingest API: {e}")


# Run Client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except ConnectionRefusedError:
    print("[!] Cannot connect to MQTT Broker. Is edge_ros2 'docker compose -f docker/compose.dev.yml up' running?")
    exit(1)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\nShutting down bridge...")
    client.disconnect()
