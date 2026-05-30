"""
config.py — Konfigurasi Terpusat Sistem Parkir ANPR
"""

import os

# ─── ESP32-CAM ────────────────────────────────────────────────────────────────
# IP yang tercetak di Serial Monitor saat ESP32 menyala
IP_ESP32 = os.environ.get("ESP32_IP", "192.168.1.2")

# Endpoint snapshot — ESP32 kirim 1 foto JPEG saat dipanggil
URL_CAPTURE = f"http://{IP_ESP32}/capture"

# Timeout koneksi ke ESP32 (detik)
ESP32_TIMEOUT = 8

# ─── FLASK ────────────────────────────────────────────────────────────────────
FLASK_HOST  = "0.0.0.0"
FLASK_PORT  = 5000
FLASK_DEBUG = False

# ─── MODEL AI ─────────────────────────────────────────────────────────────────
YOLO_MODEL_PATH           = "runs/detect/train-4/weights/best.pt"
OCR_CONFIDENCE_THRESHOLD  = 0.15   # diturunkan dari 0.4
YOLO_CONFIDENCE_THRESHOLD = 0.2  # diturunkan dari 0.5

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DATABASE_PATH = "database_parkir.db"
FOTO_FOLDER   = "riwayat_foto"
