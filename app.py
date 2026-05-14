from flask import Flask, jsonify, render_template, Response, request, redirect, url_for, session
import cv2
from ultralytics import YOLO
import easyocr
import numpy as np
import base64
import sqlite3
import requests
import os
import time
from datetime import datetime
from functools import wraps

app = Flask(__name__)
# Secret key wajib ada untuk menggunakan fitur 'session' (keamanan login)
app.secret_key = 'kunci_rahasia_sistem_parkir_kampus'

# Variabel global untuk menyimpan frame kamera terakhir
frame_kamera_terakhir = None
teks_pelat_terakhir = "TIDAK TERBACA"

# Variabel untuk menyimpan log live sementara (hilang saat server mati)
riwayat_live = []

# --- FUNGSI KEAMANAN MENU ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- KONEKSI DATABASE ---
def get_db_connection():
    conn = sqlite3.connect('database_parkir.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- LOAD MODEL MACHINE LEARNING ---
print("Memuat Model YOLO dan EasyOCR...")
model = YOLO('runs/detect/train-4/weights/best.pt') 
reader = easyocr.Reader(['en'], gpu=False)

# ================= ROUTING BACKEND =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM pengguna WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['logged_in'] = True
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            error = 'Username atau Password salah!'
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
@login_required
def index():
    # Kirim data ke index.html agar sinkron
    return render_template('index.html', 
                           processed_image=None, 
                           username=session['username'],
                           resolusi_kamera="640x480", 
                           fps_kamera="30 fps",       
                           akurasi_model="99.5%")     

# 4. Fungsi Pemrosesan Kamera Live (FINAL: STABIL, ANTI-LAG, ANTI-GLARE, FIX BLACK SCREEN)
def generate_frames():
    global frame_kamera_terakhir, teks_pelat_terakhir
    cap = cv2.VideoCapture(0)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    frame_count = 0
    last_box = None 
    box_timeout = 0 
    MAX_TIMEOUT = 10 
    TOLERANSI_GERAK = 40 

    while True:
        success, frame = cap.read()
        if not success:
            break
        
        frame_count += 1
        
        # === BLOK AI: HANYA BERJALAN TIAP 5 FRAME ===
        if frame_count % 5 == 0:
            results = model(frame, verbose=False)
            teks_pelat_sementara = "TIDAK TERBACA" 
            deteksi_berhasil = False 
            
            for res in results:
                for box in res.boxes:
                    if box.conf[0] < 0.5: continue 

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    butuh_ocr = True
                    
                    if last_box is not None:
                        old_x1, old_y1, old_x2, old_y2, old_text = last_box
                        
                        if abs(x1 - old_x1) < TOLERANSI_GERAK and abs(y1 - old_y1) < TOLERANSI_GERAK:
                            x1, y1, x2, y2 = old_x1, old_y1, old_x2, old_y2 
                            
                            huruf_bersih = old_text.replace(" ", "")
                            if len(huruf_bersih) >= 4 and old_text != "TIDAK TERBACA":
                                text = old_text 
                                butuh_ocr = False 
                            else:
                                butuh_ocr = True 

                    if butuh_ocr:
                        pad = 5
                        y1_pad = max(0, y1 - pad)
                        y2_pad = min(frame.shape[0], y2 + pad)
                        x1_pad = max(0, x1 - pad)
                        x2_pad = min(frame.shape[1], x2 + pad)
                        
                        plate_img = frame[y1_pad:y2_pad, x1_pad:x2_pad]
                        
                        if plate_img.size > 0:
                            gray_plate = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                            processed_plate = cv2.adaptiveThreshold(gray_plate, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                            
                            ocr_res = reader.readtext(processed_plate)
                            teks_gabungan = ""
                            
                            for (bbox, text, prob) in ocr_res:
                                if prob > 0.3: 
                                    teks_gabungan += text + " "
                            
                            teks_gabungan = teks_gabungan.strip().upper()
                            
                            if teks_gabungan != "":
                                teks_pelat_sementara = teks_gabungan
                                last_box = (x1, y1, x2, y2, teks_gabungan) 
                                box_timeout = MAX_TIMEOUT 
                                deteksi_berhasil = True
                                break 
                if deteksi_berhasil: break 

            # Mengatur Timeout Kotak
            if not deteksi_berhasil:
                if box_timeout > 0:
                    box_timeout -= 1
                else:
                    last_box = None 

            # Mengatur Log Live
            if teks_pelat_sementara != "TIDAK TERBACA":
                if teks_pelat_sementara != teks_pelat_terakhir:
                    waktu_skrg = datetime.now().strftime('%H:%M:%S')
                    riwayat_live.insert(0, {'plat_nomor': teks_pelat_sementara, 'waktu': waktu_skrg})
                    
                    if len(riwayat_live) > 5:
                        riwayat_live.pop()

                teks_pelat_terakhir = teks_pelat_sementara
        # === AKHIR BLOK AI ===

        # MENGGAMBAR KOTAK
        if last_box is not None:
            x1, y1, x2, y2, text = last_box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3) 
            cv2.putText(frame, text, (x1, y1-15), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        frame_kamera_terakhir = frame.copy()

        time.sleep(0.03) 

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return "Tidak ada file yang diunggah"
    
    file = request.files['file']
    if file:
        file_bytes = file.read()
        np_img = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        results = model(img, verbose=False)
        pelat_terbaca = "TIDAK TERBACA"
        
        for res in results:
            for box in res.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                plate_img = img[y1:y2, x1:x2]
                
                if plate_img.size > 0:
                    gray_plate = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                    ocr_res = reader.readtext(gray_plate)
                    teks_gabungan = ""
                    
                    for (bbox, text, prob) in ocr_res:
                        if prob > 0.3:
                            teks_gabungan += text + " "
                            
                    teks_gabungan = teks_gabungan.strip().upper()
                    
                    if teks_gabungan != "":
                        pelat_terbaca = teks_gabungan
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(img, pelat_terbaca, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        waktu_sekarang = datetime.now()
        nama_file = f"pelat_{waktu_sekarang.strftime('%Y%m%d_%H%M%S')}.jpg"
        folder_simpan = 'riwayat_foto'
        
        if not os.path.exists(folder_simpan):
            os.makedirs(folder_simpan)
        cv2.imwrite(os.path.join(folder_simpan, nama_file), img)

        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO riwayat_parkir (waktu, plat_nomor, file_foto) VALUES (?, ?, ?)',
                         (waktu_sekarang.strftime('%Y-%m-%d %H:%M:%S'), pelat_terbaca, nama_file))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error Database Upload: {e}")

        _, buffer = cv2.imencode('.jpg', img)
        encoded_img = base64.b64encode(buffer).decode('utf-8')

        return render_template('index.html', 
                               processed_image=encoded_img, 
                               username=session['username'],
                               resolusi_kamera="640x480",
                               fps_kamera="30 fps",
                               akurasi_model="99.5%")

@app.route('/simpan_kamera', methods=['POST'])
@login_required
def simpan_kamera():
    global frame_kamera_terakhir, teks_pelat_terakhir
    
    if frame_kamera_terakhir is not None:
        waktu_sekarang = datetime.now()
        nama_file = f"cam_{waktu_sekarang.strftime('%Y%m%d_%H%M%S')}.jpg"
        folder_simpan = 'riwayat_foto'
        
        if not os.path.exists(folder_simpan):
            os.makedirs(folder_simpan)
            
        path_simpan = os.path.join(folder_simpan, nama_file)
        cv2.imwrite(path_simpan, frame_kamera_terakhir)
        
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO riwayat_parkir (waktu, plat_nomor, file_foto) VALUES (?, ?, ?)',
                         (waktu_sekarang.strftime('%Y-%m-%d %H:%M:%S'), teks_pelat_terakhir, nama_file))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error simpan DB Kamera: {e}")

    return redirect(url_for('index'))

# Route khusus untuk memberikan data live ke JavaScript
@app.route('/get_live_log')
@login_required
def get_live_log():
    return jsonify(riwayat_live)

# PASTIKAN INI BERADA DI BARIS PALING BAWAH
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)