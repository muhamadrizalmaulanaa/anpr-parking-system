import cv2
from ultralytics import YOLO
import easyocr

# 1. Load model YOLOv8 (versi nano untuk performa ringan)
print("Memuat model YOLOv8...")
model = YOLO('runs/detect/train-4/weights/best.pt')

# 2. Inisialisasi EasyOCR (Gunakan gpu=False jika tidak ada GPU khusus)
print("Memuat EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False) 

# 3. Akses kamera (0 adalah ID untuk webcam default)
cap = cv2.VideoCapture(0)

print("Sistem ANPR Aktif. Tekan 'q' untuk keluar.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: 
        print("Gagal membaca dari kamera.")
        break

    # 4. Deteksi objek di dalam frame kamera
    results = model(frame, verbose=False)
    
    for res in results:
        for box in res.boxes:
            # Ambil koordinat kotak (bounding box)
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # Potong (crop) gambar sesuai area yang terdeteksi
            plate_img = frame[y1:y2, x1:x2]
            
            if plate_img.size > 0:
                # 5. Ekstraksi teks menggunakan OCR pada area yang dipotong
                ocr_res = reader.readtext(plate_img)
                for (bbox, text, prob) in ocr_res:
                    # Tampilkan teks jika tingkat keyakinan (probabilitas) cukup tinggi
                    if prob > 0.3:
                        print(f"Terbaca: {text} | Akurasi: {prob:.2f}")
                        
                        # Beri kotak hijau dan teks di layar kamera
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, text, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    # Tampilkan jendela video
    cv2.imshow('Kamera ANPR', frame)
    
    # Keluar dari loop jika tombol 'q' ditekan
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()