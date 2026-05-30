from flask import Flask, jsonify, render_template, request, redirect, url_for, session
import cv2
from ultralytics import YOLO
import easyocr
import numpy as np
import base64
import sqlite3
import os
import urllib.request
import urllib.error
from datetime import datetime
from functools import wraps
import secrets
import config

app = Flask(__name__)
app.secret_key = 'super_secret_key_ta_anpr'

# ──────────────────────────────────────────────────────────────
#  LOAD MODEL (sekali saat startup)
# ──────────────────────────────────────────────────────────────
print("Memuat Model YOLO dan EasyOCR...")
model  = YOLO(config.YOLO_MODEL_PATH)
reader = easyocr.Reader(['en'], gpu=False)
print("Model siap!")

# Riwayat 5 deteksi terakhir (untuk live log di UI)
riwayat_live = []


# ──────────────────────────────────────────────────────────────
#  HELPER — DATABASE
# ──────────────────────────────────────────────────────────────
def get_db_connection():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────
#  HELPER — LOGIN
# ──────────────────────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────────────────────
#  HELPER — OCR INTERNAL (dipanggil oleh deteksi_pelat)
# ──────────────────────────────────────────────────────────────
def _ocr_plat(plate_img):
    """Coba beberapa metode preprocessing, kembalikan teks plat terbaik."""
    h, w = plate_img.shape[:2]

    # Upscale 2x agar karakter lebih besar → OCR lebih akurat
    plate_up = cv2.resize(plate_img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(plate_up, cv2.COLOR_BGR2GRAY)

    # CLAHE: perbaiki kontras adaptif (lebih baik dari hard threshold)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray_clahe = clahe.apply(gray)
    gray_blur  = cv2.GaussianBlur(gray_clahe, (3, 3), 0)

    hasil_terbaik = ""

    # Coba 3 metode preprocessing, ambil hasil teks terpanjang
    for candi in [gray_blur, gray_clahe, plate_up]:
        ocr_res = reader.readtext(
            candi,
            allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ',
            paragraph=False,
            detail=1
        )
        teks = " ".join(
            t for _, t, p in ocr_res
            if p > config.OCR_CONFIDENCE_THRESHOLD
        ).strip().upper()
        teks_bersih = " ".join(teks.split())
        if len(teks_bersih) > len(hasil_terbaik):
            hasil_terbaik = teks_bersih

    return hasil_terbaik


# ──────────────────────────────────────────────────────────────
#  HELPER — DETEKSI PELAT NOMOR
#  Input : img (numpy array BGR)
#  Output: (teks_plat, img_dengan_kotak)
# ──────────────────────────────────────────────────────────────
def deteksi_pelat(img):
    results = model(img, verbose=False)
    plat_terbaca  = "TIDAK TERBACA"
    plat_ditemukan = False

    for res in results:
        for box in res.boxes:
            if box.conf[0] < config.YOLO_CONFIDENCE_THRESHOLD:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Padding lebih besar agar seluruh plat masuk crop
            pad = 10
            y1p = max(0, y1 - pad)
            y2p = min(img.shape[0], y2 + pad)
            x1p = max(0, x1 - pad)
            x2p = min(img.shape[1], x2 + pad)

            plate_img = img[y1p:y2p, x1p:x2p]
            if plate_img.size == 0:
                continue

            teks = _ocr_plat(plate_img)

            if teks and len(teks.replace(" ", "")) >= 3:
                plat_terbaca   = teks
                plat_ditemukan = True
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 220, 80), 3)
                label_y      = max(y1 - 12, 20)
                lebar_label  = len(teks) * 13 + 14
                cv2.rectangle(img,
                              (x1, label_y - 22),
                              (x1 + lebar_label, label_y + 4),
                              (0, 220, 80), -1)
                cv2.putText(img, teks, (x1 + 5, label_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.72,
                            (0, 0, 0), 2)
                break
        else:
            continue
        break

    # ── FALLBACK: YOLO tidak deteksi → OCR langsung ke seluruh gambar ──
    if not plat_ditemukan:
        print("[INFO] YOLO tidak deteksi plat — fallback OCR full image...")
        teks_fallback = _ocr_plat(img)
        if teks_fallback and len(teks_fallback.replace(" ", "")) >= 3:
            plat_terbaca = teks_fallback
            cv2.putText(img, f"[FALLBACK] {teks_fallback}",
                        (10, 35), cv2.FONT_HERSHEY_SIMPLEX,
                        0.85, (0, 180, 255), 2)

    return plat_terbaca, img


# ──────────────────────────────────────────────────────────────
#  HELPER — SIMPAN KE DB & RIWAYAT LIVE
# ──────────────────────────────────────────────────────────────
def simpan_ke_db(waktu_sekarang, plat, nama_file):
    global riwayat_live
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO riwayat_parkir (waktu, plat_nomor, file_foto) VALUES (?, ?, ?)',
            (waktu_sekarang.strftime('%Y-%m-%d %H:%M:%S'), plat, nama_file)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

    # Update live log (maks 5 entri)
    riwayat_live.insert(0, {
        'plat_nomor': plat,
        'waktu': waktu_sekarang.strftime('%H:%M:%S')
    })
    if len(riwayat_live) > 5:
        riwayat_live.pop()


# ──────────────────────────────────────────────────────────────
#  ROUTE — AUTH
# ──────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM pengguna WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            session['username']  = user['username']
            return redirect(url_for('index'))
        error = 'Username atau Password salah!'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ──────────────────────────────────────────────────────────────
#  ROUTE — HALAMAN UTAMA
# ──────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    return render_template('index.html',
                           username=session['username'],
                           esp32_url=config.URL_CAPTURE,
                           akurasi_model="99.5%")


# ──────────────────────────────────────────────────────────────
#  ROUTE — AMBIL FOTO DARI ESP32-CAM (TRIGGER BUTTON)
# ──────────────────────────────────────────────────────────────
@app.route('/ambil_foto_kamera', methods=['POST'])
@login_required
def ambil_foto_kamera():
    """
    Ketika tombol 'Ambil & Deteksi' ditekan:
    1. Panggil ESP32-CAM /capture → dapatkan JPEG
    2. Jalankan YOLO + OCR
    3. Simpan foto + hasil ke database
    4. Kembalikan hasil ke browser (JSON)
    """
    # 1. Minta foto ke ESP32
    try:
        req = urllib.request.Request(
            config.URL_CAPTURE,
            headers={'User-Agent': 'FlaskANPR/1.0'}
        )
        with urllib.request.urlopen(req, timeout=config.ESP32_TIMEOUT) as resp:
            jpg_bytes = resp.read()
    except urllib.error.URLError as e:
        return jsonify({
            'sukses': False,
            'pesan': f'ESP32-CAM tidak terhubung: {e.reason if hasattr(e, "reason") else str(e)}'
        }), 503
    except Exception as e:
        return jsonify({'sukses': False, 'pesan': f'Error: {str(e)}'}), 500

    # 2. Decode bytes → numpy image
    np_arr = np.frombuffer(jpg_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({'sukses': False, 'pesan': 'Gambar dari ESP32 tidak valid'}), 500

    # Koreksi mirror: ESP32-CAM membalik gambar secara horizontal
    # flipCode=1 → flip horizontal. Ubah ke 0 jika terbalik vertikal, -1 jika keduanya.
    img = cv2.flip(img, 1)


    # 3. Deteksi pelat
    plat_terbaca, img_hasil = deteksi_pelat(img)

    # 4. Simpan foto ke disk
    waktu_sekarang = datetime.now()
    nama_file = f"cam_{waktu_sekarang.strftime('%Y%m%d_%H%M%S')}.jpg"
    os.makedirs(config.FOTO_FOLDER, exist_ok=True)
    cv2.imwrite(os.path.join(config.FOTO_FOLDER, nama_file), img_hasil)

    # 5. Simpan ke database + riwayat live
    simpan_ke_db(waktu_sekarang, plat_terbaca, nama_file)

    # 6. Encode gambar ke base64 untuk dikirim ke browser
    _, buffer = cv2.imencode('.jpg', img_hasil, [cv2.IMWRITE_JPEG_QUALITY, 88])
    gambar_b64 = base64.b64encode(buffer).decode('utf-8')

    return render_template('index.html',
                           username=session['username'],
                           esp32_url=config.URL_CAPTURE,
                           akurasi_model="99.5%",
                           processed_image=gambar_b64)


# ──────────────────────────────────────────────────────────────
#  ROUTE — VIDEO FEED
# ──────────────────────────────────────────────────────────────
@app.route('/video_feed')
@login_required
def video_feed():
    from flask import Response
    import time
    def gen_frames():
        while True:
            try:
                req = urllib.request.Request(config.URL_CAPTURE, headers={'User-Agent': 'FlaskANPR/1.0'})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    frame = resp.read()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.1)
            except Exception:
                time.sleep(1)
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ──────────────────────────────────────────────────────────────
#  ROUTE — STATUS ESP32 (untuk indikator di navbar)
# ──────────────────────────────────────────────────────────────
@app.route('/status_esp32')
@login_required
def status_esp32():
    """Cek apakah ESP32-CAM bisa dijangkau."""
    try:
        req = urllib.request.Request(
            config.URL_CAPTURE,
            method='HEAD',
            headers={'User-Agent': 'FlaskANPR/1.0'}
        )
        urllib.request.urlopen(req, timeout=3)
        online = True
    except Exception:
        # HEAD mungkin tidak didukung, coba GET singkat
        try:
            urllib.request.urlopen(
                f"http://{config.IP_ESP32}/",
                timeout=3
            )
            online = True
        except Exception:
            online = False

    return jsonify({'online': online, 'ip': config.IP_ESP32})


# ──────────────────────────────────────────────────────────────
#  ROUTE — UPLOAD FILE MANUAL
# ──────────────────────────────────────────────────────────────
ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'webp', 'bmp'}

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'sukses': False, 'pesan': 'Tidak ada file'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'sukses': False, 'pesan': 'File kosong'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'sukses': False, 'pesan': 'Format file tidak didukung'}), 400

    # Decode file → numpy image
    file_bytes = file.read()
    np_img = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({'sukses': False, 'pesan': 'File bukan gambar valid'}), 400

    # Deteksi pelat
    plat_terbaca, img_hasil = deteksi_pelat(img)

    # Simpan foto
    waktu_sekarang = datetime.now()
    nama_file = f"upload_{waktu_sekarang.strftime('%Y%m%d_%H%M%S')}.jpg"
    os.makedirs(config.FOTO_FOLDER, exist_ok=True)
    cv2.imwrite(os.path.join(config.FOTO_FOLDER, nama_file), img_hasil)

    # Simpan ke DB
    simpan_ke_db(waktu_sekarang, plat_terbaca, nama_file)

    # Encode hasil
    _, buffer = cv2.imencode('.jpg', img_hasil, [cv2.IMWRITE_JPEG_QUALITY, 88])
    gambar_b64 = base64.b64encode(buffer).decode('utf-8')

    return render_template('index.html',
                           username=session['username'],
                           esp32_url=config.URL_CAPTURE,
                           akurasi_model="99.5%",
                           processed_image=gambar_b64)


# ──────────────────────────────────────────────────────────────
#  ROUTE — LIVE LOG
# ──────────────────────────────────────────────────────────────
@app.route('/get_live_log')
@login_required
def get_live_log():
    return jsonify(riwayat_live)


# ──────────────────────────────────────────────────────────────
#  ROUTE — RIWAYAT PARKIR
# ──────────────────────────────────────────────────────────────
@app.route('/riwayat')
@login_required
def riwayat():
    conn = get_db_connection()
    data = conn.execute(
        'SELECT * FROM riwayat_parkir ORDER BY waktu DESC LIMIT 200'
    ).fetchall()
    conn.close()
    return render_template('riwayat.html', data=data, username=session['username'])


@app.route('/hapus_riwayat/<int:id>', methods=['POST'])
@login_required
def hapus_riwayat(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM riwayat_parkir WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('riwayat'))


# ──────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f"[INFO] ESP32-CAM Capture URL: {config.URL_CAPTURE}")
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        threaded=True
    )