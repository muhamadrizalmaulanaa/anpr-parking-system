"""
cari_esp32.py — Script untuk menemukan IP ESP32-CAM di jaringan lokal
Jalankan: python cari_esp32.py
"""

import socket
import threading
import time
import urllib.request
import urllib.error

print("=" * 55)
print("  PENCARI IP ESP32-CAM di Jaringan Lokal")
print("=" * 55)

# Ambil IP komputer ini untuk tahu subnet jaringan
hostname = socket.gethostname()
ip_lokal = socket.gethostbyname(hostname)
print(f"\n[INFO] IP Komputer Anda: {ip_lokal}")

# Ambil prefix subnet (misal: 192.168.18.)
bagian = ip_lokal.rsplit('.', 1)
prefix = bagian[0] + '.'
print(f"[INFO] Scanning subnet: {prefix}0/24")
print(f"[INFO] Mencari ESP32-CAM (port 81)...\n")

esp_ditemukan = []
lock = threading.Lock()

def cek_host(ip):
    """Coba akses port 81 dan path /stream untuk identifikasi ESP32-CAM."""
    url = f"http://{ip}:81/stream"
    try:
        req = urllib.request.Request(url, method='GET')
        # Timeout sangat singkat — hanya mau tahu apakah port terbuka
        conn = urllib.request.urlopen(req, timeout=1)
        # Cek apakah response adalah MJPEG stream
        content_type = conn.headers.get('Content-Type', '')
        conn.close()
        if 'multipart' in content_type or 'mjpeg' in content_type:
            with lock:
                esp_ditemukan.append(ip)
                print(f"  [OK] DITEMUKAN! ESP32-CAM di: http://{ip}:81/stream")
    except Exception:
        pass  # Host tidak merespons atau bukan ESP32

# Scan semua IP di subnet secara paralel
threads = []
for i in range(1, 255):
    ip = prefix + str(i)
    t = threading.Thread(target=cek_host, args=(ip,))
    t.daemon = True
    threads.append(t)
    t.start()

# Tunggu semua thread selesai
for t in threads:
    t.join(timeout=3)

print("\n" + "=" * 55)
if esp_ditemukan:
    print(f"\n[OK] ESP32-CAM ditemukan di {len(esp_ditemukan)} alamat:")
    for ip in esp_ditemukan:
        print(f"   -> http://{ip}:81/stream")
    print(f"\n[Langkah selanjutnya]:")
    print(f"   1. Buka file config.py")
    print(f"   2. Ubah IP_ESP32 = \"{esp_ditemukan[0]}\"")
    print(f"   3. Jalankan ulang app.py")
else:
    print("\n[GAGAL] ESP32-CAM tidak ditemukan di jaringan.")
    print("\nKemungkinan penyebab:")
    print("  1. ESP32 belum dinyalakan")
    print("  2. ESP32 belum terhubung ke WiFi (lihat Serial Monitor)")
    print("  3. ESP32 dan komputer beda jaringan WiFi")
    print("  4. WiFi yang dipakai ESP32 berbeda dari komputer Anda")
    print("\n[Tips] Cara manual:")
    print("  1. Buka Arduino IDE")
    print("  2. Hubungkan ESP32 ke komputer via USB")
    print("  3. Buka Serial Monitor (115200 baud)")
    print("  4. Restart ESP32 -> IP akan tercetak di Serial Monitor")
    print("  5. Salin IP tersebut ke config.py")

print()
