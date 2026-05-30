/*
 * ESP32-CAM ANPR — Snapshot Mode
 * ================================
 * Mode: Snapshot (tidak streaming) — foto diambil saat Flask meminta.
 * Endpoint: GET http://<IP_ESP32>/capture  → mengembalikan JPEG tunggal
 *
 * LANGKAH SETUP:
 * 1. Ganti WIFI_SSID dan WIFI_PASSWORD
 * 2. Upload ke ESP32-CAM (Board: AI Thinker ESP32-CAM)
 *    Partition Scheme: Huge APP (3MB No OTA)
 * 3. Buka Serial Monitor 115200 baud
 * 4. Salin IP yang muncul → update IP_ESP32 di config.py
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

// ─── WiFi ─────────────────────────────────────────────────────
const char* WIFI_SSID     = "KASYIFA KEY";      // Harus sama dengan WiFi laptop!
const char* WIFI_PASSWORD = "PINGINSURGAibadah";

// ─── IP Statis (opsional tapi direkomendasikan) ────────────────
// Uncomment 4 baris di bawah untuk IP tetap, sesuaikan dengan jaringan Anda:
// IPAddress staticIP(192, 168, 1, 15);    // IP yang ingin dipakai
// IPAddress gateway(192, 168, 1, 1);      // IP router (cek dengan "ipconfig" di cmd)
// IPAddress subnet(255, 255, 255, 0);
// IPAddress dns(8, 8, 8, 8);

// ─── Pin AI Thinker ESP32-CAM ─────────────────────────────────
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

httpd_handle_t server = NULL;

// ─── Handler /capture ─────────────────────────────────────────
// Flask memanggil ini saat tombol ditekan → ESP32 ambil 1 foto dan kirim
static esp_err_t capture_handler(httpd_req_t* req) {
    Serial.println("[CAPTURE] Permintaan foto diterima dari Flask...");

    // Buang frame lama yang tersisa di buffer (ambil fresh frame)
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("[ERROR] Gagal ambil frame dari sensor kamera!");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    esp_camera_fb_return(fb);  // Buang frame pertama (mungkin stale)
    
    // Ambil frame segar
    fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("[ERROR] Gagal ambil frame segar!");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    // Set response header
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache");

    // Kirim data JPEG
    esp_err_t res = httpd_resp_send(req, (const char*)fb->buf, fb->len);
    
    Serial.printf("[CAPTURE] Foto terkirim: %u bytes\n", fb->len);
    esp_camera_fb_return(fb);
    return res;
}

// ─── Handler / (info) ─────────────────────────────────────────
static esp_err_t info_handler(httpd_req_t* req) {
    char buf[256];
    snprintf(buf, sizeof(buf),
        "ESP32-CAM ANPR Snapshot Server\r\n"
        "================================\r\n"
        "Endpoint foto : http://%s/capture\r\n"
        "Salin IP ini ke config.py!\r\n",
        WiFi.localIP().toString().c_str());
    httpd_resp_set_type(req, "text/plain");
    httpd_resp_send(req, buf, strlen(buf));
    return ESP_OK;
}

// ─── Start HTTP Server ────────────────────────────────────────
void startServer() {
    httpd_config_t config    = HTTPD_DEFAULT_CONFIG();
    config.server_port       = 80;   // Port standar HTTP
    config.max_open_sockets  = 7;
    config.recv_wait_timeout = 10;
    config.send_wait_timeout = 10;

    if (httpd_start(&server, &config) != ESP_OK) {
        Serial.println("[ERROR] Gagal menjalankan HTTP server!");
        return;
    }

    httpd_uri_t capture_uri = {
        .uri     = "/capture",
        .method  = HTTP_GET,
        .handler = capture_handler,
        .user_ctx = NULL
    };

    httpd_uri_t info_uri = {
        .uri     = "/",
        .method  = HTTP_GET,
        .handler = info_handler,
        .user_ctx = NULL
    };

    httpd_register_uri_handler(server, &capture_uri);
    httpd_register_uri_handler(server, &info_uri);

    Serial.println("[SERVER] HTTP server aktif di port 80");
}

// ─── Setup ───────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial.setDebugOutput(false);
    Serial.println("\n===== ESP32-CAM ANPR Snapshot =====");

    // Inisialisasi kamera
    camera_config_t cam;
    cam.ledc_channel = LEDC_CHANNEL_0;
    cam.ledc_timer   = LEDC_TIMER_0;
    cam.pin_d0       = Y2_GPIO_NUM;
    cam.pin_d1       = Y3_GPIO_NUM;
    cam.pin_d2       = Y4_GPIO_NUM;
    cam.pin_d3       = Y5_GPIO_NUM;
    cam.pin_d4       = Y6_GPIO_NUM;
    cam.pin_d5       = Y7_GPIO_NUM;
    cam.pin_d6       = Y8_GPIO_NUM;
    cam.pin_d7       = Y9_GPIO_NUM;
    cam.pin_xclk     = XCLK_GPIO_NUM;
    cam.pin_pclk     = PCLK_GPIO_NUM;
    cam.pin_vsync    = VSYNC_GPIO_NUM;
    cam.pin_href     = HREF_GPIO_NUM;
    cam.pin_sscb_sda = SIOD_GPIO_NUM;
    cam.pin_sscb_scl = SIOC_GPIO_NUM;
    cam.pin_pwdn     = PWDN_GPIO_NUM;
    cam.pin_reset    = RESET_GPIO_NUM;
    cam.xclk_freq_hz = 20000000;
    cam.pixel_format = PIXFORMAT_JPEG;

    // Gunakan XGA (1024x768) untuk akurasi OCR yang lebih baik saat snapshot
    // Jika gambar terlalu besar/lambat, ganti ke FRAMESIZE_VGA
    cam.frame_size   = FRAMESIZE_XGA;
    cam.jpeg_quality = 10;   // 10 = kualitas sangat baik, cocok untuk OCR
    cam.fb_count     = 1;    // 1 buffer sudah cukup untuk snapshot
    cam.grab_mode    = CAMERA_GRAB_LATEST;  // Selalu ambil frame terbaru

    esp_err_t err = esp_camera_init(&cam);
    if (err != ESP_OK) {
        Serial.printf("[ERROR] Kamera gagal init: 0x%x\n", err);
        Serial.println("Cek koneksi ribbon kamera, lalu restart.");
        delay(5000);
        ESP.restart();
    }

    // Optimasi sensor untuk baca plat nomor
    sensor_t* s = esp_camera_sensor_get();
    if (s) {
        s->set_brightness(s,  1);   // Sedikit lebih terang
        s->set_contrast(s,    2);   // Kontras tinggi untuk teks plat
        s->set_saturation(s, -1);   // Kurangi saturasi (lebih natural)
        s->set_sharpness(s,   2);   // Tajam untuk OCR
        s->set_whitebal(s,    1);   // Auto white balance
        s->set_awb_gain(s,    1);
        s->set_exposure_ctrl(s, 1); // Auto exposure
        s->set_aec2(s,        1);   // AEC2 stabil
        s->set_gain_ctrl(s,   1);   // Auto gain
    }
    Serial.println("[KAMERA] Siap!");

    // Koneksi WiFi
    // WiFi.config(staticIP, gateway, subnet, dns); // Uncomment untuk IP statis
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.print("[WiFi] Menghubungkan ke: ");
    Serial.println(WIFI_SSID);

    int coba = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        if (++coba > 40) {
            Serial.println("\n[ERROR] WiFi gagal! Restart...");
            ESP.restart();
        }
    }

    // Cetak info penting ke Serial Monitor
    Serial.println("\n\n==============================================");
    Serial.print("  IP ESP32-CAM    : ");
    Serial.println(WiFi.localIP());
    Serial.print("  URL Capture     : http://");
    Serial.print(WiFi.localIP());
    Serial.println("/capture");
    Serial.println("----------------------------------------------");
    Serial.println("  >>> Salin IP di atas ke config.py <<<");
    Serial.println("  Ubah baris: IP_ESP32 = \"<IP di atas>\"");
    Serial.println("==============================================\n");

    startServer();
    Serial.println("[SIAP] Tunggu Flask menekan tombol untuk foto!");
}

// ─── Loop ────────────────────────────────────────────────────
void loop() {
    // Watchdog WiFi: reconnect jika terputus
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WiFi] Terputus! Mencoba reconnect...");
        WiFi.reconnect();
        delay(10000);
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[WiFi] Gagal reconnect, restart...");
            ESP.restart();
        }
    }
    delay(30000); // Cek WiFi tiap 30 detik
}
