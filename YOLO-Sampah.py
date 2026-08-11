import time
import cv2
import numpy as np
import urllib.request
import paho.mqtt.client as mqtt
from ultralytics import YOLO

ESP32_CAM_URL = "http://10.178.104.209:81/stream" 

MQTT_BROKER = "rmq230.pptik.id"
MQTT_PORT = 1883
MQTT_USER = "/prd:prd26-kel11"
MQTT_PASS = "Smart123System"
MQTT_TOPIC = "Trigger"

MODEL_PATH = r"C:\Users\aufam\Downloads\AksangKel2.yolov8\runs\detect\train\weights\best.pt"

print("[YOLO] Memuat model...")
model = YOLO(MODEL_PATH)

try:
    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2, 
        client_id="Python-YOLO-Publisher"
    )
except AttributeError:
    # Fallback untuk paho-mqtt versi lama
    mqtt_client = mqtt.Client(client_id="Python-YOLO-Publisher")

mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Terhubung ke Broker PPTIK (rmq230.pptik.id)!")
    else:
        print(f"[MQTT] Gagal terhubung, return code: {rc}")

mqtt_client.on_connect = on_connect

try:
    print("[MQTT] Membuka koneksi ke broker PPTIK...")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"[MQTT Error] Gagal konek ke broker: {e}")

def send_mqtt_trigger():
    """Mengirim sinyal trigger via MQTT PPTIK"""
    try:
        mqtt_client.publish(MQTT_TOPIC, "TRIGGER", qos=0)
        print(f"\n>>> [MQTT SENT] Trigger dikirim ke topic '{MQTT_TOPIC}' <<<")
    except Exception as e:
        print(f"\n[MQTT Error] Gagal publish: {e}")

def connect_stream(url):
    """Mencoba menghubungkan ke stream ESP32-CAM"""
    while True:
        try:
            print(f"Mencoba menghubungkan ke ESP32-CAM ({url})...")
            stream = urllib.request.urlopen(url, timeout=5)
            print("Terhubung ke ESP32-CAM! Memulai deteksi AI...")
            return stream
        except Exception as e:
            print(f"Gagal terhubung ({e}). Pastikan IP benar & terhubung ke Wi-Fi AksangKel2. Re-trying dalam 2 detik...")
            time.sleep(2)

stream = connect_stream(ESP32_CAM_URL)
bytes_buffer = b''
last_trigger_time = 0

try:
    while True:
        try:
            chunk = stream.read(4096)
            if not chunk:
                raise Exception("Stream terputus (0 bytes received).")
                
            bytes_buffer += chunk
            a = bytes_buffer.find(b'\xff\xd8')
            b = bytes_buffer.find(b'\xff\xd9')

            if a != -1 and b != -1:
                jpg = bytes_buffer[a:b+2]
                bytes_buffer = bytes_buffer[b+2:]
                
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

                if frame is not None:
                    results = model(frame)
                    annotated_frame = results[0].plot()

                    boxes = results[0].boxes
                    if len(boxes) > 0:
                        current_time = time.time()
                        if current_time - last_trigger_time > 4.0:
                            send_mqtt_trigger()
                            last_trigger_time = current_time

                    cv2.imshow('CCTV AI - ESP32 CAM Stream', annotated_frame)

        except Exception as e:
            print(f"\n[Warning] Stream terputus: {e}")
            time.sleep(1)
            bytes_buffer = b''
            stream = connect_stream(ESP32_CAM_URL)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    cv2.destroyAllWindows()
    print("[SYSTEM] Program dihentikan.")
