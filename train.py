from ultralytics import YOLO

model = YOLO('yolov8n.pt')

results = model.train(
    data='dataset_anpr/data.yaml', 
    epochs=100,  
    imgsz=640,
    batch=4,       # Turunkan beban RAM (defaultnya 16). Jika masih mati, ubah jadi 2.
    workers=0,     # Mencegah crash memori/CPU di Windows saat load gambar
    plots=True   
)