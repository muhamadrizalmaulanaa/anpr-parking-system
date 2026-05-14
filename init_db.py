import sqlite3

# 1. Membuat koneksi (jika file belum ada, SQLite akan otomatis membuatnya)
conn = sqlite3.connect('database_parkir.db')
cursor = conn.cursor()

# 2. Membuat Tabel Riwayat Parkir (Sesuai dengan konsep ANPR)
cursor.execute('''
CREATE TABLE IF NOT EXISTS riwayat_parkir (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waktu DATETIME NOT NULL,
    plat_nomor TEXT NOT NULL,
    file_foto TEXT
)
''')

# 3. Membuat Tabel Pengguna (Untuk keamanan & Login)
cursor.execute('''
CREATE TABLE IF NOT EXISTS pengguna (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
''')

# 4. Memasukkan satu akun admin default (Hanya jika tabel masih kosong)
cursor.execute('SELECT COUNT(*) FROM pengguna')
if cursor.fetchone()[0] == 0:
    cursor.execute('INSERT INTO pengguna (username, password) VALUES ("admin", "admin123")')
    print("Akun default berhasil dibuat: Username: admin | Password: admin123")

# Simpan dan tutup koneksi
conn.commit()
conn.close()

print("Database 'database_parkir.db' dan tabel berhasil dibuat!")