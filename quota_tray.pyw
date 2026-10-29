import os
import sys
import json
import threading
import winreg
import ctypes
import math
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from winotify import Notification, audio
import sv_ttk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "quota_data.json")
FLAG_FILE = os.path.join(APP_DIR, "show_window.flag")

APP_NAME = "QuotaAITracker"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
MUTEX_NAME = "QuotaAITrackerMutex_Unique_V14"

# --- KOMUNIKASI ANTAR PROSES ---
def send_show_window_signal():
    try:
        with open(FLAG_FILE, 'w') as f: f.write("show")
    except: pass

def check_single_instance():
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183: 
        send_show_window_signal()
        return False
    global _app_mutex
    _app_mutex = mutex
    return True

# --- LOGIKA SINKRONISASI WAKTU ---
def calculate_synced_reset(anchor_str, duration_hours):
    now = datetime.now()
    try: target_time = datetime.strptime(anchor_str, "%H:%M").time()
    except ValueError: target_time = datetime.strptime("00:00", "%H:%M").time()
        
    base_dt = datetime.combine(now.date(), target_time)
    interval_secs = float(duration_hours * 3600)
    
    diff_secs = (now - base_dt).total_seconds()
    N = math.floor(diff_secs / interval_secs) + 1
    
    next_reset = base_dt + timedelta(seconds=N * interval_secs)
    return next_reset.strftime("%Y-%m-%d %H:%M:%S")

# --- DATA MANAGEMENT ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for acc, info in data.items():
                    if info.get("type") not in ["Berulang", "Manual"]: info["type"] = "Berulang"
                    if "duration" not in info: info["duration"] = 5
                    if "fixed_time" not in info: info["fixed_time"] = "00:00"
                    if "state" not in info: info["state"] = "Running"
                return data
        except json.JSONDecodeError: return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f: json.dump(data, f)
    except: pass

# --- KELAS BUBBLE MENGAMBANG (VERSI STABIL 3) ---
class BubbleWindow(tk.Toplevel):
    def __init__(self, overlay):
        super().__init__(overlay.app.root)
        self.overlay = overlay
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        transparent_color = "#000001"
        self.configure(bg=transparent_color)
        self.attributes("-transparentcolor", transparent_color)
        
        self.geometry(f"60x60+{overlay.winfo_x()}+{max(0, overlay.winfo_y())}")
        
        self.canvas = tk.Canvas(self, width=60, height=60, bg=transparent_color, highlightthickness=0)
        self.canvas.pack()
        
        self.canvas.create_oval(2, 2, 58, 58, fill="#252526", outline="#0078D7", width=2)
        self.canvas.create_text(30, 30, text="⏱️", font=("Segoe UI", 22), fill="white")
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        self.is_drag = False

    def on_press(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.win_x = self.winfo_x()
        self.win_y = self.winfo_y()
        self.is_drag = False

    def on_drag(self, event):
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        if dx*dx + dy*dy > 25: 
            self.is_drag = True
        
        new_x = self.win_x + dx
        new_y = self.win_y + dy
        if new_y < 0: new_y = 0
        
        self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        if not self.is_drag:
            self.overlay.geometry(f"+{self.winfo_x()}+{self.winfo_y()}")
            self.overlay.deiconify()
            self.destroy()

# --- OVERLAY MINI WIDGET (REVISED: SCROLL & DRAG FIX + JAM RESET) ---
class OverlayWindow(tk.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app.root)
        self.app = parent_app
        self.bubble = None
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.95)
        # Diperlebar agar waktu reset muat
        self.geometry("340x350+30+30")
        
        self.update_idletasks()
        if self.winfo_y() < 0:
            self.geometry(f"+{self.winfo_x()}+30")
        
        # Cursor diganti arrow agar rapi
        self.grip = tk.Frame(self, bg="#1E1E1E", cursor="arrow", height=28)
        self.grip.pack(fill=tk.X)
        self.grip.bind("<ButtonPress-1>", self.start_move)
        self.grip.bind("<B1-Motion>", self.do_move)
        
        lbl_title = tk.Label(self.grip, text="👁️ AI Tracker Overlay", bg="#1E1E1E", fg="white", font=("Segoe UI", 9, "bold"), cursor="arrow")
        lbl_title.pack(side=tk.LEFT, padx=10)
        lbl_title.bind("<ButtonPress-1>", self.start_move)
        lbl_title.bind("<B1-Motion>", self.do_move)
        
        btn_frame = tk.Frame(self.grip, bg="#1E1E1E")
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text="—", bg="#333333", fg="white", bd=0, font=("Segoe UI", 8, "bold"), width=3, cursor="arrow", command=self.minimize_to_bubble).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_frame, text="✖", bg="#E81123", fg="white", bd=0, font=("Segoe UI", 9), width=3, cursor="arrow", command=self.close_overlay).pack(side=tk.LEFT)
        
        self.canvas = tk.Canvas(self, bg="#252526", highlightthickness=0, cursor="arrow")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg="#252526", cursor="arrow")
        
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw", width=self.canvas.winfo_width())
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.resize_grip = ttk.Sizegrip(self)
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se")
        
        self.labels = {}
        self.current_order = []

        self.bind("<Enter>", self._bind_mousewheel)
        self.bind("<Leave>", self._unbind_mousewheel)

        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.scroll_frame.bind("<ButtonPress-1>", self.start_move)
        self.scroll_frame.bind("<B1-Motion>", self.do_move)

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def start_move(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.win_x = self.winfo_x()
        self.win_y = self.winfo_y()

    def do_move(self, event):
        deltax = event.x_root - self.start_x
        deltay = event.y_root - self.start_y
        
        new_x = self.win_x + deltax
        new_y = self.win_y + deltay
        if new_y < 0: new_y = 0
            
        self.geometry(f"+{new_x}+{new_y}")

    def minimize_to_bubble(self):
        # Menggunakan logika asli quota_tray_3
        self.withdraw()
        self.bubble = BubbleWindow(self)

    def close_overlay(self):
        if self.bubble and self.bubble.winfo_exists():
            self.bubble.destroy()
        self.destroy()
        self.app.overlay_window = None

    def create_row_widget(self, acc):
        f = tk.Frame(self.scroll_frame, bg="#333333", pady=5, padx=8, cursor="arrow")
        f.pack(fill=tk.X, pady=3, padx=5)
        
        top_row = tk.Frame(f, bg="#333333", cursor="arrow")
        top_row.pack(fill=tk.X)
        name_lbl = tk.Label(top_row, text=acc, bg="#333333", fg="white", font=("Segoe UI", 10, "bold"), cursor="arrow")
        name_lbl.pack(side=tk.LEFT)
        
        action_btn = tk.Label(top_row, text="[ - ]", bg="#333333", fg="#3E92CC", font=("Segoe UI", 9, "bold"), cursor="hand2")
        action_btn.pack(side=tk.RIGHT)
        action_btn.bind("<Button-1>", lambda e, a=acc: self.handle_overlay_action(a))
        
        bot_row = tk.Frame(f, bg="#333333", cursor="arrow")
        bot_row.pack(fill=tk.X, pady=(2,0))
        time_lbl = tk.Label(bot_row, text="--:--:--", bg="#333333", fg="#9E9E9E", font=("Segoe UI", 9), cursor="arrow")
        time_lbl.pack(side=tk.LEFT)
        
        # TAMBAHAN FITUR: LABEL WAKTU RESET
        reset_lbl = tk.Label(bot_row, text="🕒 --:--", bg="#333333", fg="#A8A8A8", font=("Segoe UI", 8, "bold"), cursor="arrow")
        reset_lbl.pack(side=tk.RIGHT)
        
        for w in (f, top_row, bot_row, name_lbl, time_lbl, reset_lbl):
            w.bind("<ButtonPress-1>", self.start_move)
            w.bind("<B1-Motion>", self.do_move)
        
        return {'frame': f, 'name': name_lbl, 'time': time_lbl, 'btn': action_btn, 'reset': reset_lbl}

    def handle_overlay_action(self, acc_name):
        if acc_name not in self.app.data: return
        state = self.app.data[acc_name]["state"]
        if state == "Idle": self.app.start_timer_for(acc_name)
        elif state == "Running": self.app.mark_exhausted_for(acc_name)
        elif state == "Exhausted": self.app.cancel_exhausted_for(acc_name)

    def update_overlay(self, current_data, tree_order):
        for acc in list(self.labels.keys()):
            if acc not in current_data:
                self.labels[acc]['frame'].destroy()
                del self.labels[acc]

        for acc in current_data:
            if acc not in self.labels:
                self.labels[acc] = self.create_row_widget(acc)

        if getattr(self, 'current_order', None) != tree_order:
            for acc in tree_order:
                if acc in self.labels:
                    self.labels[acc]['frame'].pack_forget()
                    self.labels[acc]['frame'].pack(fill=tk.X, pady=3, padx=5)
            self.current_order = list(tree_order)

        now = datetime.now()
        for acc, info in current_data.items():
            if acc not in self.labels: continue
            
            state = info["state"]
            color, text_status, btn_text = "#9E9E9E", "💤 Menunggu Dimulai", "[ ▶️ Mulai ]"
            reset_text = "🕒 --:--"
            
            if state != "Idle":
                reset_dt = datetime.strptime(info["reset_time"], "%Y-%m-%d %H:%M:%S")
                # Format penulisan waktu reset
                reset_text = f"🕒 {reset_dt.strftime('%H:%M')}"
                
                if now >= reset_dt:
                     color, text_status, btn_text = "#81C784", "✅ Mereset...", "[ - ]"
                else:
                    rem = reset_dt - now
                    h, r = divmod(rem.seconds, 3600)
                    m, s = divmod(r, 60)
                    if state == "Exhausted": 
                        color, text_status, btn_text = "#FF5252", f"🛑 Habis: {h:02d}j {m:02d}m {s:02d}d", "[ 🔵 Batal ]"
                    else: 
                        color, text_status, btn_text = "#81C784", f"▶️ Aktif: {h:02d}j {m:02d}m {s:02d}d", "[ 🛑 Habis ]"

            self.labels[acc]['time'].config(text=text_status, fg=color)
            self.labels[acc]['btn'].config(text=btn_text)
            self.labels[acc]['reset'].config(text=reset_text)

# --- JENDELA PENGATURAN ---
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app.root)
        self.app = parent_app
        self.title("Pengaturan Aplikasi")
        self.geometry("380x250")
        self.resizable(False, False)
        
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="⚙️ Pengaturan & Sistem", font=("Segoe UI", 12, "bold")).pack(pady=(0, 20))
        ttk.Button(frame, text="🔄 Reset Aplikasi (Hapus Cache Data)", command=self.reset_app).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="🛑 Matikan Aplikasi Total", style="Accent.TButton", command=self.kill_app).pack(fill=tk.X, pady=5)
        ttk.Label(frame, text="© 2026 Gunawan Ragil Rahmadhan\nQuota AI Tracker v14.0 - All Rights Reserved.", justify="center", foreground="gray", font=("Segoe UI", 8)).pack(side=tk.BOTTOM, pady=(15, 0))

        self.transient(parent_app.root)
        self.grab_set()
        self.focus_set()

    def reset_app(self):
        if messagebox.askyesno("Peringatan Kritis", "Yakin hapus semua cache secara permanen?", parent=self):
            self.app.data.clear()
            if os.path.exists(DATA_FILE):
                try: os.remove(DATA_FILE)
                except: pass
            for item in self.app.tree.get_children(): self.app.tree.delete(item)
            messagebox.showinfo("Sukses", "Aplikasi berhasil di-reset.", parent=self)
            self.destroy()

    def kill_app(self):
        if messagebox.askyesno("Konfirmasi", "Yakin ingin mematikan tracker sepenuhnya?", parent=self):
            self.destroy()
            self.app.safe_exit()

# --- JENDELA FORM TAMBAH/EDIT ---
class AccountDialog(tk.Toplevel):
    def __init__(self, parent, title, initial_data=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x250")
        self.resizable(False, False)
        self.result = None
        
        self.old_name = initial_data.get("name", "") if initial_data else ""
        self.name_var = tk.StringVar(value=self.old_name)
        self.type_var = tk.StringVar(value=initial_data.get("type", "Berulang") if initial_data else "Berulang")
        self.dur_var = tk.IntVar(value=initial_data.get("duration", 5) if initial_data else 5)
        self.time_var = tk.StringVar(value=initial_data.get("fixed_time", "00:00") if initial_data else "00:00")
        
        self.setup_ui()
        self.toggle_inputs()
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        parent.wait_window(self)

    def setup_ui(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Nama Akun / Email:").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        ttk.Entry(frame, textvariable=self.name_var).grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 15))

        ttk.Label(frame, text="Jenis Tracker:").grid(row=2, column=0, sticky="w", pady=(0, 5))
        cb = ttk.Combobox(frame, textvariable=self.type_var, values=["Berulang", "Manual"], state="readonly", width=16)
        cb.grid(row=3, column=0, sticky="w", pady=(0, 15))
        cb.bind("<<ComboboxSelected>>", self.toggle_inputs)

        ttk.Label(frame, text="Durasi (Jam):").grid(row=2, column=1, sticky="w", pady=(0, 5), padx=(15,0))
        ttk.Spinbox(frame, from_=1, to=72, textvariable=self.dur_var, width=10).grid(row=3, column=1, sticky="w", pady=(0, 15), padx=(15,0))

        self.lbl_time = ttk.Label(frame, text="Offset Acuan (HH:MM):")
        self.lbl_time.grid(row=2, column=2, sticky="w", pady=(0, 5), padx=(15,0))
        self.entry_time = ttk.Entry(frame, textvariable=self.time_var, width=12)
        self.entry_time.grid(row=3, column=2, sticky="w", pady=(0, 15), padx=(15,0))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=(15, 0), sticky="e")
        ttk.Button(btn_frame, text="Batal", command=self.destroy).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Simpan", style="Accent.TButton", command=self.save).pack(side=tk.LEFT)
        frame.columnconfigure(2, weight=1)

    def toggle_inputs(self, event=None):
        if self.type_var.get() == "Berulang":
            self.lbl_time.grid()
            self.entry_time.grid()
        else:
            self.lbl_time.grid_remove()
            self.entry_time.grid_remove()

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Error", "Nama akun kosong!", parent=self)
            return
            
        if self.type_var.get() == "Berulang":
            try: datetime.strptime(self.time_var.get(), "%H:%M")
            except:
                messagebox.showwarning("Error", "Format offset salah! Gunakan format HH:MM (contoh: 00:53)", parent=self)
                return
                
        self.result = {
            "name": name,
            "type": self.type_var.get(),
            "duration": self.dur_var.get(),
            "fixed_time": self.time_var.get()
        }
        self.destroy()

# --- APLIKASI UTAMA ---
class QuotaTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quota AI Tracker") 
        self.root.geometry("880x450")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        if os.path.exists(FLAG_FILE):
            try: os.remove(FLAG_FILE)
            except: pass

        self.overlay_window = None
        self.data = load_data()
        self.setup_ui()
        self.setup_tray()
        
        for acc in self.data:
            self.tree.insert("", "end", iid=acc)
            
        self.main_loop()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        head_frame = ttk.Frame(main_frame)
        head_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(head_frame, text="🔄 Sinkronisasi Kuota Akun AI", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)
        ttk.Button(head_frame, text="🖥️ Tampilkan Overlay", command=self.toggle_overlay).pack(side=tk.RIGHT)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("akun", "jenis", "setting", "status", "reset", "aksi")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)
        self.tree.heading("akun", text="Akun / Email")
        self.tree.heading("jenis", text="Mode")
        self.tree.heading("setting", text="Setelan Waktu")
        self.tree.heading("status", text="Status / Sisa Waktu")
        self.tree.heading("reset", text="Waktu Reset")
        self.tree.heading("aksi", text="Aksi Cepat")
        
        self.tree.column("akun", width=140)
        self.tree.column("jenis", width=90, anchor="center")
        self.tree.column("setting", width=120, anchor="center")
        self.tree.column("status", width=170, anchor="center")
        self.tree.column("reset", width=140, anchor="center")
        self.tree.column("aksi", width=80, anchor="center")
        
        order_frame = ttk.Frame(tree_frame)
        order_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0))
        ttk.Button(order_frame, text="▲", width=3, command=self.move_up).pack(side=tk.TOP, pady=(0,2))
        ttk.Button(order_frame, text="▼", width=3, command=self.move_down).pack(side=tk.TOP)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.tag_configure("idle", foreground="#9E9E9E")      
        self.tree.tag_configure("running", foreground="#81C784")   
        self.tree.tag_configure("exhausted", foreground="#FF5252") 

        self.tree.bind("<ButtonRelease-1>", self.on_single_click)
        self.tree.bind("<Button-3>", self.show_popup)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(btn_frame, text="➕ Tambah Akun", style="Accent.TButton", command=self.add_account).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(btn_frame, text="💡 Tips: Gunakan ▲▼ untuk mengatur urutan", foreground="gray").pack(side=tk.LEFT)
        
        ttk.Button(btn_frame, text="Sembunyikan ⬇️", command=self.hide_window).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="⚙️ Pengaturan", command=lambda: SettingsDialog(self)).pack(side=tk.RIGHT, padx=(0, 10))

    def move_up(self):
        selected = self.tree.selection()
        if not selected: return
        idx = self.tree.index(selected[0])
        if idx > 0:
            self.tree.move(selected[0], self.tree.parent(selected[0]), idx - 1)
            self.save_tree_order()

    def move_down(self):
        selected = self.tree.selection()
        if not selected: return
        idx = self.tree.index(selected[0])
        if idx < len(self.tree.get_children()) - 1:
            self.tree.move(selected[0], self.tree.parent(selected[0]), idx + 1)
            self.save_tree_order()

    def save_tree_order(self):
        new_data = {}
        for child_id in self.tree.get_children():
            if child_id in self.data:
                new_data[child_id] = self.data[child_id]
        self.data = new_data
        save_data(self.data)

    def toggle_overlay(self):
        if self.overlay_window is None or not self.overlay_window.winfo_exists():
            self.overlay_window = OverlayWindow(self)
        else:
            if self.overlay_window.state() == "withdrawn":
                if self.overlay_window.bubble and self.overlay_window.bubble.winfo_exists():
                    self.overlay_window.bubble.destroy()
                self.overlay_window.deiconify()
            else:
                self.overlay_window.close_overlay()

    def on_single_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#6":
                row_id = self.tree.identify_row(event.y)
                if row_id:
                    acc_data = self.data.get(row_id)
                    if acc_data:
                        if acc_data["state"] == "Idle": self.start_timer_for(row_id)
                        elif acc_data["state"] == "Running": self.mark_exhausted_for(row_id)
                        elif acc_data["state"] == "Exhausted": self.cancel_exhausted_for(row_id)

    def show_popup(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            acc_data = self.data[row_id]
            menu = tk.Menu(self.root, tearoff=0)
            
            if acc_data["type"] == "Manual" and acc_data["state"] == "Idle":
                menu.add_command(label="▶️ Mulai Timer", command=lambda: self.start_timer_for(row_id))
            if acc_data["state"] == "Running":
                menu.add_command(label="🛑 Kuota Habis (Tandai Merah)", command=lambda: self.mark_exhausted_for(row_id))
            if acc_data["state"] == "Exhausted":
                menu.add_command(label="🟢 Batal Habis (Kembali Hijau)", command=lambda: self.cancel_exhausted_for(row_id))
            menu.add_separator()
            menu.add_command(label="✏️ Edit Akun", command=self.edit_account)
            menu.add_command(label="🗑️ Hapus Akun", command=self.delete_account)
            menu.tk_popup(event.x_root, event.y_root)

    def main_loop(self):
        now = datetime.now()
        tree_order = self.tree.get_children()

        for acc, info in self.data.items():
            if acc not in tree_order: continue
            
            tipe = info.get("type", "Berulang")
            state = info.get("state", "Running")
            
            setting = f"{info['duration']} Jam"
            if tipe == "Berulang" and "fixed_time" in info: setting += f" (Acuan: {info['fixed_time']})"
                
            tag, aksi_btn = "running", "-"
            
            if state == "Idle":
                status, reset_str, tag, aksi_btn = "💤 Menunggu Dimulai", "-", "idle", "[ ▶️ Mulai ]"
            else:
                reset_dt = datetime.strptime(info["reset_time"], "%Y-%m-%d %H:%M:%S")
                if now >= reset_dt:
                    if not info.get("notified", False):
                        self.show_notification(acc, False)
                        info["notified"] = True
                    
                    if tipe == "Berulang":
                        info["reset_time"] = calculate_synced_reset(info["fixed_time"], info["duration"])
                        info["last_used"] = now.strftime("%Y-%m-%d %H:%M:%S")
                        info["state"], info["notified"] = "Running", False
                        status, reset_str, tag, aksi_btn = "🔄 Sinkronisasi Baru...", info["reset_time"], "running", "[ 🛑 Habis ]"
                    else:
                        info["state"], info["notified"] = "Idle", False
                        status, reset_str, tag, aksi_btn = "✅ Reset! (Menunggu)", "-", "idle", "[ ▶️ Mulai ]"
                    save_data(self.data)
                else:
                    rem = reset_dt - now
                    h, r = divmod(rem.seconds, 3600)
                    m, s = divmod(r, 60)
                    if state == "Exhausted":
                        status, tag, aksi_btn = f"🛑 Habis! Tunggu: {h:02d}j {m:02d}m {s:02d}d", "exhausted", "[ 🟢 Batal ]"
                    else:
                        status, tag, aksi_btn = f"▶️ Aktif: {h:02d}j {m:02d}m {s:02d}d", "running", "[ 🛑 Habis ]"
                    reset_str = info["reset_time"]
            
            self.tree.item(acc, values=(acc, tipe, setting, status, reset_str, aksi_btn), tags=(tag,))

        if self.overlay_window and self.overlay_window.winfo_exists() and self.overlay_window.state() != "withdrawn":
            self.overlay_window.update_overlay(self.data, tree_order)

        if os.path.exists(FLAG_FILE):
            try:
                os.remove(FLAG_FILE)
                self.force_show_window()
            except: pass

        self.root.after(1000, self.main_loop)

    def force_show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def start_timer_for(self, acc_name):
        info = self.data[acc_name]
        now = datetime.now()
        info["reset_time"] = (now + timedelta(hours=info["duration"])).strftime("%Y-%m-%d %H:%M:%S")
        info["state"], info["notified"], info["last_used"] = "Running", False, now.strftime("%Y-%m-%d %H:%M:%S")
        save_data(self.data)
        self.show_notification(acc_name, is_new=True, msg=f"Timer Manual dimulai! Reset dalam {info['duration']} jam.")

    def mark_exhausted_for(self, acc_name):
        self.data[acc_name]["state"] = "Exhausted"
        save_data(self.data)

    def cancel_exhausted_for(self, acc_name):
        self.data[acc_name]["state"] = "Running"
        save_data(self.data)

    def add_account(self):
        dialog = AccountDialog(self.root, "Tambah Akun Baru")
        if dialog.result:
            name = dialog.result["name"]
            now = datetime.now()
            
            is_manual = (dialog.result["type"] == "Manual")
            state = "Idle" if is_manual else "Running"
            
            reset_str = "-"
            if not is_manual: reset_str = calculate_synced_reset(dialog.result["fixed_time"], dialog.result["duration"])
            
            self.data[name] = {
                "type": dialog.result["type"],
                "duration": dialog.result["duration"],
                "fixed_time": dialog.result["fixed_time"],
                "state": state,
                "last_used": now.strftime("%Y-%m-%d %H:%M:%S"),
                "reset_time": reset_str,
                "notified": False
            }
            self.tree.insert("", "end", iid=name)
            self.save_tree_order()

    def edit_account(self):
        selected = self.tree.selection()
        if not selected: return
        old_name = selected[0]
        dialog = AccountDialog(self.root, "Edit Akun", self.data[old_name])
        if dialog.result:
            new_name = dialog.result["name"]
            if new_name != old_name:
                new_data = {}
                for key, val in self.data.items():
                    if key == old_name: new_data[new_name] = val
                    else: new_data[key] = val
                self.data = new_data
                
                idx = self.tree.index(old_name)
                self.tree.delete(old_name)
                self.tree.insert("", idx, iid=new_name)
                
            self.data[new_name]["type"] = dialog.result["type"]
            self.data[new_name]["duration"] = dialog.result["duration"]
            self.data[new_name]["fixed_time"] = dialog.result["fixed_time"]
            
            if self.data[new_name]["state"] in ["Running", "Exhausted"]:
                if dialog.result["type"] == "Berulang":
                    self.data[new_name]["reset_time"] = calculate_synced_reset(dialog.result["fixed_time"], dialog.result["duration"])
                else:
                    last_used = datetime.strptime(self.data[new_name]["last_used"], "%Y-%m-%d %H:%M:%S")
                    self.data[new_name]["reset_time"] = (last_used + timedelta(hours=dialog.result["duration"])).strftime("%Y-%m-%d %H:%M:%S")
                self.data[new_name]["notified"] = False
                
            if self.data[new_name]["type"] == "Berulang" and self.data[new_name]["state"] == "Idle":
                 self.data[new_name]["state"] = "Running"
                 self.data[new_name]["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                 self.data[new_name]["reset_time"] = calculate_synced_reset(dialog.result["fixed_time"], dialog.result["duration"])
                 
            save_data(self.data)

    def delete_account(self):
        selected = self.tree.selection()
        if not selected: return
        if messagebox.askyesno("Konfirmasi", f"Yakin ingin menghapus '{selected[0]}'?", parent=self.root):
            del self.data[selected[0]]
            self.tree.delete(selected[0])
            self.save_tree_order()

    def show_notification(self, acc_name, is_new=False, msg=""):
        try:
            if is_new: toast = Notification(app_id="Quota AI Tracker", title="Mulai!", msg=msg, duration="short")
            else:
                toast = Notification(app_id="Quota AI Tracker", title="✅ Kuota Reset!", msg=f"Silakan! Kuota {acc_name} siap digunakan kembali.", duration="long")
                toast.set_audio(audio.Default, loop=False)
            toast.show()
        except: pass

    def create_tray_image(self):
        img = Image.new('RGB', (64, 64), color=(0, 120, 215))
        dc = ImageDraw.Draw(img)
        dc.ellipse((16, 16, 48, 48), fill=(255, 255, 255))
        return img

    def setup_tray(self):
        menu = Menu(
            MenuItem("Buka Dashboard", self.show_window_from_tray, default=True),
            MenuItem("Jalankan Otomatis saat Startup", self.toggle_autostart_from_tray, checked=lambda item: self.is_autostart_enabled()),
            MenuItem("Keluar Total", self.safe_exit)
        )
        self.icon = Icon("QuotaAITracker", self.create_tray_image(), "Quota AI Tracker", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def is_autostart_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError: return False

    def toggle_autostart_from_tray(self, icon, item):
        enabled = self.is_autostart_enabled()
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enabled:
            try: winreg.DeleteValue(key, APP_NAME)
            except: pass
        else:
            python_executable = sys.executable.replace("python.exe", "pythonw.exe")
            script_path = os.path.abspath(__file__)
            command = f'"{python_executable}" "{script_path}" --minimized'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)

    def hide_window(self):
        self.root.withdraw()
        
    def show_window_from_tray(self, icon, item):
        self.root.after(0, self.force_show_window)
        
    def safe_exit(self, icon=None, item=None):
        try: self.icon.stop()
        except: pass
        try: self.root.destroy() 
        except: pass
        os._exit(0)

if __name__ == "__main__":
    if not check_single_instance():
        sys.exit(0)

    root = tk.Tk()
    sv_ttk.set_theme("dark")
    app = QuotaTrackerApp(root)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--minimized":
        root.withdraw()
        
    root.mainloop()