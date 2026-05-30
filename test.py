import cv2
import urllib.request
import numpy as np

# Pastikan IP ini sama persis dengan yang ada di Serial Monitor terakhir
url = "http://192.168.18.163:81/stream"
print("Menghubungkan ke kamera secara manual...")

try:
    # Membuka jalur langsung ke IP Kamera
    stream = urllib.request.urlopen(url)
    bytes_data = b''
    print("Koneksi berhasil! Menunggu gambar...")
    
    while True:
        # Mengambil data video sedikit demi sedikit
        bytes_data += stream.read(1024)
        
        # Mencari titik awal (ffd8) dan akhir (ffd9) dari sebuah foto JPEG
        a = bytes_data.find(b'\xff\xd8')
        b = bytes_data.find(b'\xff\xd9')
        
        if a != -1 and b != -1:
            jpg = bytes_data[a:b+2]
            bytes_data = bytes_data[b+2:]
            
            # Mengubah data mentah menjadi gambar yang bisa dibaca OpenCV
            img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            
            if img is not None:
                cv2.imshow("TES LIVE STREAM (JALUR BELAKANG)", img)
                
            # Tekan 'q' untuk keluar
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

except Exception as e:
    print(f"Terjadi Error: {e}")

cv2.destroyAllWindows()