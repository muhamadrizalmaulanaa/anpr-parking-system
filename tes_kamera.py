import cv2

print("Menghubungi ESP32-CAM...")
cap = cv2.VideoCapture("http://192.168.1.15:81/stream")

if not cap.isOpened():
    print("GAGAL: Tidak bisa terhubung ke kamera!")
else:
    print("BERHASIL: Kamera terhubung. Tekan 'q' pada keyboard untuk keluar.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Video terputus!")
            break
        cv2.imshow("Tes Kamera ESP32", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()