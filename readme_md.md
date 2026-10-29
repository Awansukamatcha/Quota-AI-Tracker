# ⏱️ Quota AI Tracker

**Quota AI Tracker** adalah aplikasi desktop Windows ringan dan elegan yang dirancang khusus untuk melacak sisa waktu dan jadwal reset kuota penggunaan kecerdasan buatan (seperti Gemini, ChatGPT, Claude, dll). 

Aplikasi ini berjalan secara mulus di latar belakang (*System Tray*) dan dilengkapi dengan widget *Overlay* mengambang (seperti *Bubble Chat*) untuk memantau status akun AI Anda kapan saja tanpa mengganggu produktivitas.

---

## ✨ Fitur Utama

### 1. Mode Pelacakan Ganda
*   **Mode Manual:** Hitung mundur standar (misal: 5 jam setelah tombol Start ditekan).
*   **Mode Berulang (Algoritma Offset Presisi):** Tidak peduli kapan Anda menyalakan PC, aplikasi akan otomatis menghitung dan menyesuaikan waktu reset AI berdasarkan waktu acuan tetap (misal: Reset setiap 5 jam, berpatokan pada pukul `00:53`).

### 2. Widget Overlay & Bubble (Anti-Flicker)
*   **Floating Overlay:** Jendela mini transparan (95%) *always-on-top* yang bisa dipindah-pindah. Mendukung *mouse scroll* dan *drag* dari seluruh area.
*   **Bubble Mode:** Overlay dapat di-minimize menjadi gelembung bulat kecil yang bisa digeser (*drag-and-drop*) ke sudut layar manapun. Klik gelembung untuk mengembalikan overlay.
*   **Quick Actions:** Tombol pintas `[ ▶️ Mulai ]`, `[ 🛑 Habis ]`, dan `[ 🟢 Batal ]` tersedia langsung di Overlay.
*   **Anti-Flicker:** Menggunakan algoritma pembaruan teks statis untuk mencegah layar atau *mouse* berkedip (*flickering*) saat data di-refresh setiap detik.

### 3. Manajemen Cerdas
*   **Single Instance Protection:** Menggunakan Windows Mutex. Jika Anda mencoba membuka aplikasi kedua kalinya saat aplikasi sudah berjalan di Tray, ia akan otomatis memunculkan jendela yang sudah ada.
*   **Custom Reorder:** Urutkan prioritas akun AI Anda dengan tombol Naik/Turun (▲/▼). Overlay akan beradaptasi secara *real-time*.
*   **Auto-Start:** Opsi bawaan untuk menjalankan aplikasi secara diam-diam saat Windows *startup*.
*   **Native Notifications:** Menggunakan `winotify` untuk memberikan peringatan visual dan suara bawaan Windows 11 saat kuota AI siap digunakan.

---

## 🛠️ Teknologi & Library
Aplikasi ini dibangun murni menggunakan Python dengan antarmuka grafis Tkinter modern.
*   `tkinter` & `sv_ttk` (Tema Dark Mode Sun Valley Windows 11)
*   `pystray` (Manajemen ikon System Tray)
*   `winotify` (Notifikasi Windows asli)
*   `Pillow` (Pemrosesan ikon)
*   `ctypes` (Interaksi Windows API tingkat rendah)

---

## 🚀 Cara Kompilasi ke EXE (Standalone)

Agar aplikasi bisa berjalan di komputer Windows tanpa perlu menginstal Python, kompilasi kode `quota_tray.pyw` menggunakan **PyInstaller**:

1. Buka Terminal / Command Prompt di dalam folder proyek.
2. Instal PyInstaller (jika belum ada):
   ```bash
   pip install pyinstaller
   ```
3. Jalankan perintah kompilasi:
   ```bash
   pyinstaller --noconsole --onefile quota_tray.pyw
   ```
4. File aplikasi mandiri Anda (`quota_tray.exe`) akan tersedia di dalam folder `dist/`.

---

## 📂 Struktur Data
Aplikasi ini menggunakan penyimpanan JSON lokal (`quota_data.json`) untuk mempertahankan data sesi waktu. Bahkan jika aplikasi dimatikan paksa (Hard Kill) atau PC di-*restart*, perhitungan waktu akan tetap akurat membaca *timestamp* dari OS.

---
**Hak Cipta © 2026 Gunawan Ragil Rahmadhan**  
*Quota AI Tracker - All Rights Reserved.*