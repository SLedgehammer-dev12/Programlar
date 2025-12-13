import tkinter as tk
import json
from tkinter import ttk, messagebox, filedialog, Menu
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import time
import math
import os
import webbrowser
import sys

# Modüler importlar
from data import COOLPROP_GASES, PIPE_MATERIALS, PIPE_ROUGHNESS, FITTING_K_FACTORS
from calculations import GasFlowCalculator
from updater import Updater
from translations import t, t_fitting, set_language, get_language, get_fitting_name_tr

# Uygulama sürümü (semantic versioning)
APP_VERSION = "5.2.0"

# Config dosyasından dil ayarını yükle
def load_language_from_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                lang = cfg.get("language", "tr")
                set_language(lang)
    except Exception:
        pass

load_language_from_config()

class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.wait_time = 500     # miliseconds
        self.wrap_length = 180   # pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.wait_time, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       wraplength = self.wrap_length)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()

# --- DOĞRULAMA SINIFI (Canlı Kontrol) ---
class ValidationHelper:
    """Kullanıcı girişleri için canlı doğrulama yardımcısı."""
    
    # Hata stilleri
    ERROR_BG = "#ffe6e6"      # Hafif kırmızı arka plan
    ERROR_FG = "#c62828"      # Koyu kırmızı metin
    NORMAL_BG = "white"
    NORMAL_FG = "black"
    WARNING_BG = "#fff3e0"    # Hafif turuncu
    
    @staticmethod
    def normalize_number(value_str):
        """
        Virgül ve nokta ile girilen sayıları normalize eder.
        Örnek: "1,5" veya "1.5" -> 1.5
        Türk lokali desteği: virgül ondalık ayracı olarak kabul edilir.
        """
        if not value_str:
            return ""
        
        # String'e çevir (StringVar olabilir)
        s = str(value_str).strip()
        
        # Boş kontrol
        if not s:
            return ""
        
        # Virgül -> Nokta dönüşümü
        # Önce durumu analiz et:
        # 1. "1.234,56" formatı (Türk/Avrupa) -> 1234.56
        # 2. "1,234.56" formatı (ABD) -> 1234.56
        # 3. Sadece virgül veya nokta varsa -> doğrudan dönüşüm
        
        comma_count = s.count(',')
        dot_count = s.count('.')
        
        if comma_count > 0 and dot_count > 0:
            # İkisi de var - hangisi ondalık ayracı?
            last_comma = s.rfind(',')
            last_dot = s.rfind('.')
            
            if last_comma > last_dot:
                # Virgül sonda: Türk/Avrupa formatı (1.234,56)
                s = s.replace('.', '')  # Binlik noktaları kaldır
                s = s.replace(',', '.')  # Virgül -> Nokta
            else:
                # Nokta sonda: ABD formatı (1,234.56)
                s = s.replace(',', '')  # Binlik virgülleri kaldır
        elif comma_count > 0:
            # Sadece virgül var
            if comma_count == 1:
                # Tek virgül = ondalık ayracı
                s = s.replace(',', '.')
            else:
                # Birden fazla virgül = binlik ayracı
                s = s.replace(',', '')
        # Nokta sadece varsa zaten doğru formatta
        
        return s
    
    @staticmethod
    def parse_float(value_str, default=0.0):
        """Normalize edilmiş string'i float'a çevirir."""
        try:
            normalized = ValidationHelper.normalize_number(value_str)
            if not normalized:
                return default
            return float(normalized)
        except ValueError:
            return None  # Geçersiz değer
    
    @staticmethod
    def parse_int(value_str, default=0):
        """Normalize edilmiş string'i int'e çevirir."""
        try:
            normalized = ValidationHelper.normalize_number(value_str)
            if not normalized:
                return default
            return int(float(normalized))
        except ValueError:
            return None


class ValidatedEntry(ttk.Entry):
    """
    Canlı doğrulama yapan Entry widget'ı.
    - Virgül ve nokta desteği
    - Gerçek zamanlı hata gösterimi
    - Hata tooltip'i
    """
    
    def __init__(self, master, textvariable=None, validation_type="float", 
                 min_value=None, max_value=None, allow_zero=True, allow_negative=False,
                 error_callback=None, **kwargs):
        super().__init__(master, textvariable=textvariable, **kwargs)
        
        self.validation_type = validation_type  # "float", "int", "positive_float", "percentage"
        self.min_value = min_value
        self.max_value = max_value
        self.allow_zero = allow_zero
        self.allow_negative = allow_negative
        self.error_callback = error_callback
        
        self.error_tooltip = None
        self.error_message = ""
        self.is_valid = True
        
        # Orijinal arka plan rengini sakla
        self._original_bg = self.cget('background') if self.cget('background') else 'white'
        
        # Event bağlamaları
        self.bind('<KeyRelease>', self._on_key_release)
        self.bind('<FocusOut>', self._on_focus_out)
        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<Leave>', self._hide_error_tooltip)
        
    def _on_key_release(self, event=None):
        """Tuş bırakıldığında doğrulama yap."""
        self._validate_input()
        
    def _on_focus_out(self, event=None):
        """Fokus çıkışında değeri normalize et ve doğrula."""
        self._normalize_and_validate()
        self._hide_error_tooltip()
        
    def _on_focus_in(self, event=None):
        """Fokus girişinde hata varsa tooltip göster."""
        if not self.is_valid:
            self._show_error_tooltip()
    
    def _normalize_and_validate(self):
        """Değeri normalize et ve tekrar doğrula."""
        current = self.get()
        normalized = ValidationHelper.normalize_number(current)
        
        # Eğer değer değiştiyse ve geçerliyse, girişi güncelle
        if normalized != current:
            try:
                float(normalized)  # Geçerli mi kontrol et
                # Entry içeriğini güncelle
                state = self.cget('state')
                self.config(state='normal')
                self.delete(0, tk.END)
                self.insert(0, normalized)
                self.config(state=state)
            except ValueError:
                pass
        
        self._validate_input()
    
    def _validate_input(self):
        """Girişi doğrula ve görsel feedback ver."""
        value_str = self.get()
        self.error_message = ""
        self.is_valid = True
        
        # Boş değer kontrolü
        if not value_str.strip():
            self._set_normal_style()
            return True
        
        # Sayıya çevirmeyi dene
        normalized = ValidationHelper.normalize_number(value_str)
        
        try:
            if self.validation_type == "int":
                value = int(float(normalized))
            else:
                value = float(normalized)
        except ValueError:
            self.error_message = "Geçersiz sayı formatı"
            self.is_valid = False
            self._set_error_style()
            return False
        
        # Min/Max kontrolleri
        if self.min_value is not None and value < self.min_value:
            self.error_message = f"Değer en az {self.min_value} olmalıdır"
            self.is_valid = False
            self._set_error_style()
            return False
            
        if self.max_value is not None and value > self.max_value:
            self.error_message = f"Değer en fazla {self.max_value} olabilir"
            self.is_valid = False
            self._set_error_style()
            return False
        
        # Sıfır kontrolü
        if not self.allow_zero and value == 0:
            self.error_message = "Değer sıfır olamaz"
            self.is_valid = False
            self._set_error_style()
            return False
        
        # Negatif kontrolü
        if not self.allow_negative and value < 0:
            self.error_message = "Değer negatif olamaz"
            self.is_valid = False
            self._set_error_style()
            return False
        
        # Yüzde kontrolü
        if self.validation_type == "percentage":
            if value < 0 or value > 100:
                self.error_message = "Yüzde 0-100 arasında olmalıdır"
                self.is_valid = False
                self._set_error_style()
                return False
        
        # Geçerli
        self._set_normal_style()
        return True
    
    def _set_error_style(self):
        """Hata stilini uygula."""
        self.config(background=ValidationHelper.ERROR_BG, foreground=ValidationHelper.ERROR_FG)
        self._show_error_tooltip()
        if self.error_callback:
            self.error_callback(self, self.error_message)
    
    def _set_normal_style(self):
        """Normal stili geri yükle."""
        self.config(background=ValidationHelper.NORMAL_BG, foreground=ValidationHelper.NORMAL_FG)
        self._hide_error_tooltip()
        if self.error_callback:
            self.error_callback(self, None)
    
    def _show_error_tooltip(self, event=None):
        """Hata tooltip'ini göster."""
        if not self.error_message:
            return
            
        if self.error_tooltip:
            return  # Zaten gösteriliyor
        
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        
        self.error_tooltip = tk.Toplevel(self)
        self.error_tooltip.wm_overrideredirect(True)
        self.error_tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            self.error_tooltip, 
            text=f"⚠ {self.error_message}",
            background="#ffcdd2",  # Açık kırmızı
            foreground="#b71c1c",  # Koyu kırmızı
            font=("Segoe UI", 9),
            padx=8, pady=4,
            relief="solid",
            borderwidth=1
        )
        label.pack()
    
    def _hide_error_tooltip(self, event=None):
        """Hata tooltip'ini gizle."""
        if self.error_tooltip:
            self.error_tooltip.destroy()
            self.error_tooltip = None
    
    def get_value(self, default=0.0):
        """Normalize edilmiş değeri döndür."""
        if self.validation_type == "int":
            return ValidationHelper.parse_int(self.get(), default=int(default))
        return ValidationHelper.parse_float(self.get(), default=default)


class GasFlowCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(t("app_title"))
        self.root.geometry("1450x950")
        self.root.minsize(1100, 800)

        # Hesaplama Motoru
        self.calculator = GasFlowCalculator()
        self.calculator.set_log_callback(self.log_message)
        # Güncelleme yöneticisi
        self.updater = Updater(self.log_message)
        self.last_download_path = None

        # Değişkenler
        self.gas_components = {}
        self.fitting_counts = {}
        self.ball_valve_kv = tk.DoubleVar(value=0.0)
        self.ball_valve_cv = tk.DoubleVar(value=0.0)
        self.log_queue = queue.Queue()
        self.calc_queue = queue.Queue()
        
        # Şema durumu değişkenleri
        self.schematic_state = "pending"  # "pending", "calculating", "completed", "error"
        self.last_calculation_time = None
        self.last_result = None

        # Stil
        self.setup_styles()
        
        # Arayüz Kurulumu
        self.create_menu()
        self.create_main_layout()
        
        # Şema otomatik güncelleme binding'leri
        self._setup_schematic_bindings()
        
        # İlk UI görünürlük ayarı
        self.update_ui_visibility()
        
        self.log_message(t("msg_program_started") + ": V5")
        self.log_message(f"{t('msg_version')}: {APP_VERSION}")
        # Arka planda sessiz güncelleme kontrolü
        self.root.after(500, self.silent_update_check)

    def create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        # Dosya Menüsü
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=t("menu_file"), menu=file_menu)
        file_menu.add_command(label=t("menu_save_project"), command=self.save_project)
        file_menu.add_command(label=t("menu_load_project"), command=self.load_project)
        file_menu.add_separator()
        file_menu.add_command(label=t("menu_exit"), command=self.root.quit)
        
        # Güncelleme Menüsü
        update_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=t("menu_update"), menu=update_menu)
        update_menu.add_command(label=t("menu_check_updates"), command=self.check_updates)
        update_menu.add_command(label=t("menu_download_latest"), command=self.download_latest_release)
        update_menu.add_separator()
        update_menu.add_command(label=t("menu_apply_update"), command=self.apply_update_from_zip_file)
        update_menu.add_command(label=t("menu_update_config"), command=self.open_update_config)
        
        # Dil Menüsü
        lang_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=t("menu_language"), menu=lang_menu)
        lang_menu.add_command(label="🇹🇷 " + t("lang_turkish"), command=lambda: self.change_language("tr"))
        lang_menu.add_command(label="🇬🇧 " + t("lang_english"), command=lambda: self.change_language("en"))
    
    def change_language(self, lang_code):
        """Dili değiştir ve uygulamayı yeniden başlat."""
        current = get_language()
        if current == lang_code:
            return
        
        # Config dosyasını güncelle
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        try:
            cfg = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["language"] = lang_code
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror(t("dialog_error"), str(e))
            return
        
        # Kullanıcıya bildir ve yeniden başlat
        set_language(lang_code)  # Mesajların yeni dilde görünmesi için
        if messagebox.askyesno(t("lang_change_title"), t("lang_change_message") + "\n\n" + t("lang_restart_now")):
            self.root.destroy()
            os.execl(sys.executable, sys.executable, *sys.argv)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam') # Daha modern bir görünüm için
        
        # Renk Paleti
        bg_color = "#f4f6f9"
        accent_color = "#007bff"
        
        style.configure(".", background=bg_color, font=("Segoe UI", 10))
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=bg_color, relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=bg_color, foreground="#333", font=("Segoe UI", 10, "bold"))
        
        style.configure("Bold.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#0056b3")
        
        style.configure("TButton", font=("Segoe UI", 10), padding=6, background="#e2e6ea")
        style.map("TButton", background=[("active", "#dae0e5")])
        
        style.configure("TLabel", background=bg_color, font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#2c3e50", background=bg_color)
        
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=25)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        
        self.root.configure(bg=bg_color)

    def validate_float(self, event):
        """Eski stil doğrulama - geriye uyumluluk için korundu."""
        widget = event.widget
        try:
            # Virgül desteği ekle
            value_str = widget.get()
            normalized = ValidationHelper.normalize_number(value_str)
            val = float(normalized)
            if val < 0: raise ValueError
            widget.config(bg="white")
        except ValueError:
            widget.config(bg="#ffe6e6")  # Hata durumunda hafif kırmızı

    def create_main_layout(self):
        # Ana Notebook (Sekmeler)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        # 1. Hesaplama Sekmesi
        calc_tab = ttk.Frame(self.notebook)
        self.notebook.add(calc_tab, text="  " + t("tab_calculation") + "  ")
        self.create_calc_tab_content(calc_tab)

        # 2. Log Sekmesi
        log_tab = ttk.Frame(self.notebook)
        self.notebook.add(log_tab, text="  " + t("tab_logs") + "  ")
        self.create_log_tab_content(log_tab)

        # Alt Bilgi / Butonlar
        self.create_footer()
        
        # Validasyon Bağlamaları (ValidatedEntry için otomatik, diğerleri için eski stil)
        # Not: ValidatedEntry kendi bağlamalarını yapar
        self.root.bind_class("TEntry", "<FocusOut>", self.validate_float)
        self.root.bind_class("TEntry", "<KeyRelease>", self._on_entry_key_release)
    
    def _on_entry_key_release(self, event):
        """Tuş bırakıldığında hızlı doğrulama."""
        widget = event.widget
        if isinstance(widget, ValidatedEntry):
            return  # ValidatedEntry kendi doğrulamasını yapar
        
        try:
            value_str = widget.get()
            if not value_str.strip():
                widget.config(bg="white")
                return
            normalized = ValidationHelper.normalize_number(value_str)
            val = float(normalized)
            if val < 0:
                widget.config(bg="#ffe6e6")
            else:
                widget.config(bg="white")
        except ValueError:
            widget.config(bg="#ffe6e6")

    def create_calc_tab_content(self, parent):
        # PanedWindow (Ayırıcı)
        self.paned_window = ttk.PanedWindow(parent, orient="horizontal")
        self.paned_window.pack(fill="both", expand=True, padx=5, pady=5)

        # Sol Panel (Girdiler)
        left_panel = ttk.Frame(self.paned_window)
        self.paned_window.add(left_panel, weight=1)
        
        # Sağ Panel (Rapor)
        right_panel = ttk.Frame(self.paned_window, width=450)
        self.paned_window.add(right_panel, weight=0) # Sağ panel başlangıçta sabit kalsın isteyebiliriz ama esnek olması daha iyi

        # --- GİRDİ GRUPLARI ---
        self.create_gas_section(left_panel)
        self.create_process_section(left_panel)
        self.create_pipe_section(left_panel)

        # --- SAĞ PANEL (RAPOR) ---
        ttk.Label(right_panel, text=t("calculation_results"), style="Header.TLabel").pack(anchor="w", pady=(0, 5))
        
        # Sonuç Sekmeleri
        self.res_notebook = ttk.Notebook(right_panel)
        self.res_notebook.pack(fill="both", expand=True)
        
        # 1. Tablo Sekmesi
        self.tab_table = ttk.Frame(self.res_notebook)
        self.res_notebook.add(self.tab_table, text=t("results_summary"))
        
        # Treeview
        cols = ("param", "value", "unit")
        self.res_tree = ttk.Treeview(self.tab_table, columns=cols, show="headings", height=20)
        self.res_tree.heading("param", text=t("result_parameter"))
        self.res_tree.heading("value", text=t("result_value"))
        self.res_tree.heading("unit", text=t("result_unit"))
        
        self.res_tree.column("param", width=180)
        self.res_tree.column("value", width=100, anchor="e")
        self.res_tree.column("unit", width=80, anchor="w")
        
        self.res_tree.tag_configure("success", foreground="green")
        self.res_tree.tag_configure("warning", foreground="orange")
        self.res_tree.tag_configure("error", foreground="red")
        
        self.res_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 2. Şematik Görünüm
        self.tab_schematic = ttk.Frame(self.res_notebook)
        self.res_notebook.add(self.tab_schematic, text=t("results_schematic"))
        
        self.schematic_canvas = tk.Canvas(self.tab_schematic, bg="white")
        self.schematic_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.schematic_canvas.bind("<Configure>", self.draw_schematic)

        # 3. Metin Sekmesi
        self.tab_text = ttk.Frame(self.res_notebook)
        self.res_notebook.add(self.tab_text, text=t("results_report"))
        
        self.report_text = ScrolledText(self.tab_text, width=50, height=40, font=("Consolas", 10))
        self.report_text.pack(fill="both", expand=True)
        
        btn_frame = ttk.Frame(right_panel)
        btn_frame.pack(fill="x", pady=10)
        
        # Progress Button Container
        self.progress_container = tk.Frame(btn_frame, bg="#e0e0e0", height=50)
        self.progress_container.pack(fill="x")
        self.progress_container.pack_propagate(False)
        
        # Progress Bar (Canvas tabanlı)
        self.progress_canvas = tk.Canvas(self.progress_container, height=50, bg="#28a745", 
                                          highlightthickness=0)
        self.progress_canvas.pack(fill="both", expand=True)
        
        # Progress değişkenleri
        self.progress_value = 0
        self.progress_text_id = None
        self.progress_bar_id = None
        self.is_calculating = False
        
        # İlk durumu çiz
        self._draw_progress_button(t("btn_calculate"), 0, idle=True)
        
        # Tıklama olayı
        self.progress_canvas.bind("<Button-1>", lambda e: self.start_calculation())
        self.progress_canvas.bind("<Enter>", self._on_progress_hover)
        self.progress_canvas.bind("<Leave>", self._on_progress_leave)
        
        self.btn_show_graphs = ttk.Button(btn_frame, text=t("show_graphs"), command=self.show_graphs, state="disabled")
        self.btn_show_graphs.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text=t("save_report"), command=self.save_report).pack(fill="x", pady=5)
    
    def _draw_progress_button(self, text, progress, idle=False):
        """Progress button'u çiz."""
        canvas = self.progress_canvas
        canvas.delete("all")
        
        width = canvas.winfo_width() or 400
        height = canvas.winfo_height() or 50
        
        if idle:
            # Bekleme durumu - düz yeşil
            canvas.create_rectangle(0, 0, width, height, fill="#28a745", outline="")
            canvas.create_text(width/2, height/2, text=text, 
                             font=("Segoe UI", 12, "bold"), fill="white")
        else:
            # İlerleme durumu - gri arka plan + yeşil ilerleme
            # Arka plan (gri)
            canvas.create_rectangle(0, 0, width, height, fill="#6c757d", outline="")
            
            # İlerleme çubuğu (yeşil)
            progress_width = (progress / 100) * width
            if progress_width > 0:
                canvas.create_rectangle(0, 0, progress_width, height, fill="#28a745", outline="")
            
            # Metin
            canvas.create_text(width/2, height/2, text=text, 
                             font=("Segoe UI", 12, "bold"), fill="white")
    
    def _on_progress_hover(self, event):
        """Mouse hover efekti."""
        if not self.is_calculating:
            self.progress_canvas.config(cursor="hand2")
            self._draw_progress_button(t("btn_calculate"), 0, idle=True)
            # Hafif parlama efekti
            self.progress_canvas.itemconfig("all", fill="")
            width = self.progress_canvas.winfo_width() or 400
            height = self.progress_canvas.winfo_height() or 50
            self.progress_canvas.delete("all")
            self.progress_canvas.create_rectangle(0, 0, width, height, fill="#2dbe50", outline="")
            self.progress_canvas.create_text(width/2, height/2, text=t("btn_calculate"), 
                                            font=("Segoe UI", 12, "bold"), fill="white")
    
    def _on_progress_leave(self, event):
        """Mouse leave efekti."""
        if not self.is_calculating:
            self._draw_progress_button(t("btn_calculate"), 0, idle=True)
    
    def update_progress(self, value, status_text=None):
        """İlerleme durumunu güncelle."""
        self.progress_value = min(100, max(0, value))
        text = status_text or f"{t('calculating_progress')}{int(self.progress_value)}"
        self._draw_progress_button(text, self.progress_value, idle=False)
        self.progress_canvas.update_idletasks()
    
    def reset_progress_button(self):
        """Progress button'u başlangıç durumuna getir."""
        self.is_calculating = False
        self.progress_value = 0
        self._draw_progress_button(t("btn_calculate"), 0, idle=True)
        self.progress_canvas.config(cursor="hand2")
    
    def _setup_schematic_bindings(self):
        """Şema otomatik güncelleme için binding'leri kur."""
        # Hesaplama hedefi değiştiğinde şemayı güncelle
        self.calc_target.bind("<<ComboboxSelected>>", self._on_target_or_input_change)
        
        # Akış tipi değiştiğinde şemayı güncelle
        self.flow_type.bind("<<ComboboxSelected>>", self._on_target_or_input_change)
        
        # Basınç/Sıcaklık/Debi değişkenleri için trace
        self.p_in_var.trace_add("write", self._schedule_schematic_update)
        self.t_var.trace_add("write", self._schedule_schematic_update)
        self.flow_var.trace_add("write", self._schedule_schematic_update)
        self.len_var.trace_add("write", self._schedule_schematic_update)
        self.diam_var.trace_add("write", self._schedule_schematic_update)
        self.thick_var.trace_add("write", self._schedule_schematic_update)
        self.target_p_var.trace_add("write", self._schedule_schematic_update)
        self.max_vel_var.trace_add("write", self._schedule_schematic_update)
        
        # Debounce için timer ID
        self._schematic_update_timer = None
    
    def _on_target_or_input_change(self, event=None):
        """Hedef veya önemli girdi değiştiğinde."""
        # Hesaplama sonuçlarını temizle (yeni hedef seçildi)
        if event and event.widget == self.calc_target:
            self.schematic_state = "pending"
            self.last_result = None
            # UI görünürlüğünü güncelle (hedef değişti)
            self.update_ui_visibility()
        self.refresh_schematic()
    
    def _schedule_schematic_update(self, *args):
        """Şema güncellemesini 300ms gecikmeyle planla (debounce)."""
        if self._schematic_update_timer:
            self.root.after_cancel(self._schematic_update_timer)
        self._schematic_update_timer = self.root.after(300, self.refresh_schematic)
    
    def refresh_schematic(self):
        """Şemayı yeniden çiz."""
        if hasattr(self, 'schematic_canvas'):
            self.draw_schematic()

    def create_gas_section(self, parent):
        frame = ttk.LabelFrame(parent, text=t("section_gas_mixture"), style="Bold.TLabelframe", padding=10)
        frame.pack(fill="x", pady=5)
        
        # Üst kısım: Arama ve Ekleme
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill="x")
        
        ttk.Label(top_frame, text=t("gas_search")).pack(side="left")
        self.gas_search_var = tk.StringVar()
        self.gas_search_var.trace("w", self.filter_gas_list)
        entry = ttk.Entry(top_frame, textvariable=self.gas_search_var, width=20)
        entry.pack(side="left", padx=5)
        
        self.gas_combo = ttk.Combobox(top_frame, values=list(COOLPROP_GASES.values()), width=25, state="readonly")
        self.gas_combo.pack(side="left", padx=5)
        self.gas_combo.set(t("select_gas"))
        
        ttk.Button(top_frame, text="+ " + t("btn_add_gas"), command=self.add_gas_component).pack(side="left")
        
        # Alt kısım: Liste ve Seçenekler
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="x", pady=5)
        
        self.gas_list_canvas = tk.Canvas(list_frame, height=120)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.gas_list_canvas.yview)
        self.gas_list_inner = ttk.Frame(self.gas_list_canvas)
        
        self.gas_list_inner.bind("<Configure>", lambda e: self.gas_list_canvas.configure(scrollregion=self.gas_list_canvas.bbox("all")))
        self.gas_list_canvas.create_window((0, 0), window=self.gas_list_inner, anchor="nw")
        self.gas_list_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.gas_list_canvas.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bileşim Türü ve Toplam Göstergesi
        type_frame = ttk.Frame(frame)
        type_frame.pack(fill="x", pady=(5,0))
        ttk.Label(type_frame, text=t("composition_type")).pack(side="left")
        self.comp_type = ttk.Combobox(type_frame, values=[t("mol_percent"), t("mass_percent")], width=10, state="readonly")
        self.comp_type.set(t("mol_percent"))
        self.comp_type.pack(side="left", padx=5)
        
        # Toplam Göstergesi
        ttk.Label(type_frame, text="   │   " + t("gas_total")).pack(side="left", padx=(20, 5))
        self.gas_total_label = tk.Label(type_frame, text="0.00 %", font=("Segoe UI", 10, "bold"), 
                                         bg="#f4f6f9", fg="#666")
        self.gas_total_label.pack(side="left")
        
        # Durum İkonu
        self.gas_status_label = tk.Label(type_frame, text="", font=("Segoe UI", 10), 
                                          bg="#f4f6f9", fg="#666")
        self.gas_status_label.pack(side="left", padx=5)

    def create_process_section(self, parent):
        frame = ttk.LabelFrame(parent, text=t("section_process_conditions"), style="Bold.TLabelframe", padding=10)
        frame.pack(fill="x", pady=5)
        
        grid = ttk.Frame(frame)
        grid.pack(fill="x")
        
        # Satır 1: Basınç & Sıcaklık
        ttk.Label(grid, text=t("inlet_pressure")).grid(row=0, column=0, sticky="w", pady=5)
        self.p_in_var = tk.DoubleVar()
        ttk.Entry(grid, textvariable=self.p_in_var, width=10).grid(row=0, column=1, padx=5)
        self.p_unit = ttk.Combobox(grid, values=["Barg", "Bara", "Psig", "Psia"], width=8, state="readonly")
        self.p_unit.set("Barg")
        self.p_unit.grid(row=0, column=2)
        
        ttk.Label(grid, text=t("temperature")).grid(row=0, column=3, sticky="w", padx=(20, 5))
        self.t_var = tk.DoubleVar(value=25)
        ttk.Entry(grid, textvariable=self.t_var, width=10).grid(row=0, column=4, padx=5)
        self.t_unit = ttk.Combobox(grid, values=["°C", "°F", "K"], width=8, state="readonly")
        self.t_unit.set("°C")
        self.t_unit.grid(row=0, column=5)

        # Satır 2: Akış & Hedef
        ttk.Label(grid, text=t("flow_rate")).grid(row=1, column=0, sticky="w", pady=5)
        self.flow_var = tk.DoubleVar()
        ttk.Entry(grid, textvariable=self.flow_var, width=10).grid(row=1, column=1, padx=5)
        self.flow_unit = ttk.Combobox(grid, values=["Sm³/h", "kg/s"], width=8, state="readonly")
        self.flow_unit.set("Sm³/h")
        self.flow_unit.grid(row=1, column=2)
        
        ttk.Label(grid, text=t("calc_target")).grid(row=1, column=3, sticky="w", padx=(20, 5))
        self.calc_target = ttk.Combobox(grid, values=[t("target_pressure_drop"), t("target_max_length"), t("target_min_diameter")], width=18, state="readonly")
        self.calc_target.set(t("target_pressure_drop"))
        self.calc_target.grid(row=1, column=4, columnspan=2, sticky="ew")
        self.calc_target.bind("<<ComboboxSelected>>", self.update_ui_visibility)

        # Satır 3: Termodinamik Model
        ttk.Label(grid, text=t("thermo_model")).grid(row=2, column=0, sticky="w", pady=5)
        self.thermo_model = ttk.Combobox(grid, values=[
            "CoolProp (High Accuracy EOS)", "Peng-Robinson (PR EOS)", 
            "Soave-Redlich-Kwong (SRK EOS)", "Pseudo-Critical (Kay's Rule)"
        ], width=30, state="readonly")
        self.thermo_model.set("CoolProp (High Accuracy EOS)")
        self.thermo_model.grid(row=2, column=1, columnspan=3, sticky="w", padx=5)
        
        ttk.Label(grid, text=t("flow_type")).grid(row=2, column=4, sticky="w")
        self.flow_type = ttk.Combobox(grid, values=[t("flow_incompressible"), t("flow_compressible")], width=15, state="readonly")
        self.flow_type.set(t("flow_incompressible"))
        self.flow_type.grid(row=2, column=5)
        self.flow_type.bind("<<ComboboxSelected>>", self.update_ui_visibility)

    def create_pipe_section(self, parent):
        self.pipe_frame = ttk.LabelFrame(parent, text=t("section_pipe_properties"), style="Bold.TLabelframe", padding=10)
        self.pipe_frame.pack(fill="x", pady=5)
        
        # Boru Geometrisi
        geo_frame = ttk.Frame(self.pipe_frame)
        geo_frame.pack(fill="x", pady=5)
        
        ttk.Label(geo_frame, text=t("material")).grid(row=0, column=0, sticky="w")
        self.material_combo = ttk.Combobox(geo_frame, values=list(PIPE_MATERIALS.keys()), width=25, state="readonly")
        self.material_combo.set("API 5L Grade B")
        self.material_combo.grid(row=0, column=1, padx=5)
        
        self.lbl_len = ttk.Label(geo_frame, text=t("length"))
        self.lbl_len.grid(row=0, column=2, padx=(15, 5))
        self.len_var = tk.DoubleVar(value=100)
        self.ent_len = ttk.Entry(geo_frame, textvariable=self.len_var, width=10)
        self.ent_len.grid(row=0, column=3)
        
        self.lbl_diam = ttk.Label(geo_frame, text=t("outer_diameter"))
        self.lbl_diam.grid(row=1, column=0, sticky="w", pady=5)
        self.diam_var = tk.DoubleVar()
        self.ent_diam = ttk.Entry(geo_frame, textvariable=self.diam_var, width=10)
        self.ent_diam.grid(row=1, column=1, padx=5)
        
        self.lbl_thick = ttk.Label(geo_frame, text=t("wall_thickness"))
        self.lbl_thick.grid(row=1, column=2, padx=(15, 5))
        self.thick_var = tk.DoubleVar()
        self.ent_thick = ttk.Entry(geo_frame, textvariable=self.thick_var, width=10)
        self.ent_thick.grid(row=1, column=3)

        # Ekstra Hedef Girdileri (Dinamik)
        self.lbl_target_p = ttk.Label(geo_frame, text=t("target_outlet_pressure"))
        self.target_p_var = tk.DoubleVar()
        self.ent_target_p = ttk.Entry(geo_frame, textvariable=self.target_p_var, width=10)
        self.target_p_unit = ttk.Combobox(geo_frame, values=["Barg", "Bara", "Psig", "Psia"], width=8, state="readonly")
        self.target_p_unit.set("Barg")
        
        self.lbl_max_vel = ttk.Label(geo_frame, text=t("max_velocity"))
        self.max_vel_var = tk.DoubleVar(value=20)
        self.ent_max_vel = ttk.Entry(geo_frame, textvariable=self.max_vel_var, width=10)

        # Tasarım Faktörleri (Min Çap için)
        design_frame = ttk.LabelFrame(self.pipe_frame, text=t("section_design_criteria"), padding=5)
        design_frame.pack(fill="x", pady=5)

        ttk.Label(design_frame, text=t("design_pressure")).grid(row=0, column=0, sticky="w")
        self.p_design_var = tk.DoubleVar()
        ttk.Entry(design_frame, textvariable=self.p_design_var, width=10).grid(row=0, column=1, padx=5)
        self.p_design_unit = ttk.Combobox(design_frame, values=["Barg", "Bara", "Psig", "Psia"], width=8, state="readonly")
        self.p_design_unit.set("Barg")
        self.p_design_unit.grid(row=0, column=2)

        ttk.Label(design_frame, text=t("factor_f")).grid(row=0, column=3, padx=(15, 5))
        self.factor_f = tk.DoubleVar(value=0.72)
        ent_f = ttk.Entry(design_frame, textvariable=self.factor_f, width=6)
        ent_f.grid(row=0, column=4)
        ToolTip(ent_f, t("tooltip_factor_f"))

        ttk.Label(design_frame, text=t("factor_e")).grid(row=0, column=5, padx=(15, 5))
        self.factor_e = tk.DoubleVar(value=1.0)
        ent_e = ttk.Entry(design_frame, textvariable=self.factor_e, width=6)
        ent_e.grid(row=0, column=6)
        ToolTip(ent_e, t("tooltip_factor_e"))

        ttk.Label(design_frame, text=t("factor_t")).grid(row=0, column=7, padx=(15, 5))
        self.factor_t = tk.DoubleVar(value=1.0)
        ent_t = ttk.Entry(design_frame, textvariable=self.factor_t, width=6)
        ent_t.grid(row=0, column=8)
        ToolTip(ent_t, t("tooltip_factor_t"))

        # Boru Elemanları (Fittings)
        fit_frame = ttk.LabelFrame(self.pipe_frame, text=t("section_fittings"), padding=5)
        fit_frame.pack(fill="x", pady=10)
        
        # 2 Kolonlu Fittings Düzeni
        items = list(FITTING_K_FACTORS.keys())
        half = (len(items) + 1) // 2
        
        for i, item in enumerate(items):
            col = 0 if i < half else 3
            row = i if i < half else i - half
            
            ttk.Label(fit_frame, text=t_fitting(item)).grid(row=row, column=col, sticky="w", padx=5, pady=2)
            var = tk.IntVar(value=0)
            self.fitting_counts[item] = var
            ttk.Entry(fit_frame, textvariable=var, width=5).grid(row=row, column=col+1, padx=5)
            
            if item == "Küresel Vana (Tam Açık)":
                ttk.Label(fit_frame, text="Kv:").grid(row=row, column=col+2)
                ttk.Entry(fit_frame, textvariable=self.ball_valve_kv, width=5).grid(row=row, column=col+3)

    def create_log_tab_content(self, parent):
        # Kontrol Paneli
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(ctrl_frame, text=t("log_filter")).pack(side="left")
        self.log_filter_var = tk.StringVar(value=t("log_all"))
        filter_combo = ttk.Combobox(ctrl_frame, textvariable=self.log_filter_var, values=[t("log_all"), "INFO", "WARNING", "ERROR"], state="readonly", width=10)
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", self.apply_log_filter)
        
        ttk.Button(ctrl_frame, text=t("btn_clear_logs"), command=self.clear_logs).pack(side="right")
        
        # Log Tablosu (Treeview)
        cols = ("time", "level", "message")
        self.log_tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        
        self.log_tree.heading("time", text=t("log_time"))
        self.log_tree.heading("level", text=t("log_level"))
        self.log_tree.heading("message", text=t("log_message"))
        
        self.log_tree.column("time", width=80, anchor="center")
        self.log_tree.column("level", width=80, anchor="center")
        self.log_tree.column("message", width=600, anchor="w")
        
        # Renkler (Tags)
        self.log_tree.tag_configure("INFO", foreground="black")
        self.log_tree.tag_configure("WARNING", foreground="#f57c00") # Turuncu
        self.log_tree.tag_configure("ERROR", foreground="red")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scrollbar.set)
        
        self.log_tree.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=5, pady=5)
        
        self.all_logs = [] # Tüm logları hafızada tut

    def log_message(self, message, level="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        # Kuyruğa yapısal veri ekle
        self.log_queue.put({"time": timestamp, "level": level, "message": message})
        self.root.after(100, self.process_log_queue)

    def process_log_queue(self):
        while not self.log_queue.empty():
            entry = self.log_queue.get()
            self.all_logs.append(entry)
            
            # Filtre kontrolü
            current_filter = self.log_filter_var.get()
            if current_filter == "Tümü" or entry["level"] == current_filter:
                self.log_tree.insert("", "end", values=(entry["time"], entry["level"], entry["message"]), tags=(entry["level"],))
                self.log_tree.yview_moveto(1) # Otomatik kaydır

    def apply_log_filter(self, event=None):
        # Tabloyu temizle
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
            
        current_filter = self.log_filter_var.get()
        
        # Yeniden doldur
        for entry in self.all_logs:
            if current_filter == "Tümü" or entry["level"] == current_filter:
                self.log_tree.insert("", "end", values=(entry["time"], entry["level"], entry["message"]), tags=(entry["level"],))
        
        self.log_tree.yview_moveto(1)

    def clear_logs(self):
        self.all_logs.clear()
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

    def create_footer(self):
        footer = ttk.Frame(self.root)
        footer.pack(fill="x", padx=10, pady=5)
        ttk.Label(footer, text="© 2025 - Doğal Gaz Mühendislik Aracı V5", font=("Segoe UI", 8)).pack(side="left")
        ttk.Label(footer, text="Durum: Hazır", font=("Segoe UI", 8)).pack(side="right")

    # --- İŞLEVSELLİK ---
    
    def filter_gas_list(self, *args):
        search = self.gas_search_var.get().lower()
        filtered = [g for g in COOLPROP_GASES.values() if search in g.lower()]
        self.gas_combo['values'] = filtered
        if filtered: self.gas_combo.current(0)

    def add_gas_component(self):
        gas_name = self.gas_combo.get()
        if not gas_name or gas_name == "Gaz Seçin": return
        
        gas_id = next(k for k, v in COOLPROP_GASES.items() if v == gas_name)
        if gas_id in self.gas_components: return
        
        # StringVar kullan (virgül desteği için)
        var = tk.StringVar(value="0")
        self.gas_components[gas_id] = var
        
        row_frame = ttk.Frame(self.gas_list_inner)
        row_frame.pack(fill="x", pady=2)
        ttk.Label(row_frame, text=gas_name, width=25).pack(side="left")
        
        # Entry - StringVar ile bağlı
        entry = ttk.Entry(row_frame, textvariable=var, width=8)
        entry.pack(side="left", padx=5)
        
        # Her tuş vuruşunda ve değer değiştiğinde toplamı güncelle
        entry.bind("<KeyRelease>", lambda e: self.update_gas_total())
        var.trace_add("write", lambda *args: self.update_gas_total())
        
        ttk.Button(row_frame, text="X", width=3, command=lambda: self.remove_gas(gas_id, row_frame)).pack(side="left")
        
        self.update_gas_total()

    def remove_gas(self, gas_id, widget):
        del self.gas_components[gas_id]
        widget.destroy()
        self.update_gas_total()
    
    def update_gas_total(self, *args):
        """Gaz bileşimi toplamını hesapla ve göster."""
        total = 0.0
        for var in self.gas_components.values():
            try:
                # StringVar'dan string al ve normalize et
                val_str = var.get()
                normalized = ValidationHelper.normalize_number(val_str)
                if normalized:
                    val = float(normalized)
                    total += val
            except (ValueError, AttributeError, tk.TclError):
                pass
        
        # Toplam göstergesini güncelle
        self.gas_total_label.config(text=f"{total:.2f} %")
        
        # Durum kontrolü
        tolerance = 0.01  # %0.01 tolerans
        if abs(total - 100.0) <= tolerance:
            # Tam %100 - Yeşil
            self.gas_total_label.config(fg="#2e7d32")  # Koyu yeşil
            self.gas_status_label.config(text="✓", fg="#2e7d32")
        elif total == 0:
            # Boş - Gri
            self.gas_total_label.config(fg="#666")
            self.gas_status_label.config(text="", fg="#666")
        else:
            # %100 değil - Turuncu uyarı
            diff = total - 100.0
            sign = "+" if diff > 0 else ""
            self.gas_total_label.config(fg="#e65100")  # Turuncu
            self.gas_status_label.config(text=f"({sign}{diff:.2f}%)", fg="#e65100")
    
    def check_gas_composition(self):
        """
        Gaz bileşimi toplamını kontrol eder.
        Returns: (is_100_percent, total, normalized_fractions, user_confirmed)
        """
        total = 0.0
        raw_values = {}
        
        for gas_id, var in self.gas_components.items():
            val = self.get_float_value(var, 0)
            if val is not None and val > 0:
                raw_values[gas_id] = val
                total += val
        
        if total <= 0:
            return (False, 0, {}, False, "Gaz bileşenleri toplamı 0'dan büyük olmalıdır.")
        
        tolerance = 0.01  # %0.01 tolerans
        
        if abs(total - 100.0) <= tolerance:
            # Tam %100 - Normalize et ve devam
            normalized = {k: v / total for k, v in raw_values.items()}
            return (True, total, normalized, True, None)
        
        # %100 değil - Kullanıcıya sor
        diff = total - 100.0
        sign = "+" if diff > 0 else ""
        
        msg = (
            f"⚠️ GAZ BİLEŞİMİ UYARISI\n\n"
            f"Girilen gaz bileşimi toplamı: {total:.2f}%\n"
            f"Fark: {sign}{diff:.2f}%\n\n"
            f"Hesaplamaya devam etmek ister misiniz?\n\n"
            f"'Evet' seçerseniz:\n"
            f"  • Bileşenler ağırlıklı ortalamalarına göre\n"
            f"    %100'e normalize edilecek.\n"
            f"  • Orijinal oranlar korunacak.\n\n"
            f"'Hayır' seçerseniz:\n"
            f"  • Hesaplama iptal edilecek.\n"
            f"  • Değerleri manuel düzeltebilirsiniz."
        )
        
        user_choice = messagebox.askyesno("Gaz Bileşimi Kontrolü", msg, icon="warning")
        
        if user_choice:
            # Kullanıcı devam etmek istiyor - normalize et
            normalized = {k: v / total for k, v in raw_values.items()}
            return (False, total, normalized, True, None)
        else:
            # Kullanıcı iptal etti
            return (False, total, {}, False, "Hesaplama kullanıcı tarafından iptal edildi.")

    def update_ui_visibility(self, event=None):
        target = self.calc_target.get()
        
        # Temizle
        self.lbl_len.grid_remove(); self.ent_len.grid_remove()
        self.lbl_target_p.grid_remove(); self.ent_target_p.grid_remove(); self.target_p_unit.grid_remove()
        self.lbl_max_vel.grid_remove(); self.ent_max_vel.grid_remove()
        
        if target == t("target_pressure_drop"):
            self.lbl_len.grid(row=0, column=2, padx=(15, 5)); self.ent_len.grid(row=0, column=3)
            self.pipe_frame.pack(fill="x", pady=5) # Göster
        elif target == t("target_max_length"):
            self.lbl_target_p.grid(row=0, column=2, padx=(15, 5)); self.ent_target_p.grid(row=0, column=3)
            self.target_p_unit.grid(row=0, column=4, padx=5)
            self.pipe_frame.pack(fill="x", pady=5) # Göster
        elif target == t("target_min_diameter"):
            self.lbl_max_vel.grid(row=0, column=2, padx=(15, 5)); self.ent_max_vel.grid(row=0, column=3)
            
            # Sıkıştırılabilir akış ise Uzunluk da gerekli
            if self.flow_type.get() == t("flow_compressible"):
                self.lbl_len.grid(row=0, column=4, padx=(15, 5)); self.ent_len.grid(row=0, column=5)

    def save_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.report_text.get(1.0, "end"))
            messagebox.showinfo(t("dialog_success"), t("report_saved"))

    def save_project(self):
        try:
            data = self.get_ui_state()
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo(t("dialog_success"), t("project_saved"))
        except Exception as e:
            messagebox.showerror(t("dialog_error"), f"{t('save_error')}: {str(e)}")

    def load_project(self):
        try:
            path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if path:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.set_ui_state(data)
                messagebox.showinfo(t("dialog_success"), t("project_loaded"))
        except Exception as e:
            messagebox.showerror(t("dialog_error"), f"{t('load_error')}: {str(e)}")

    def get_ui_state(self):
        # Gaz Bileşimi
        gas_data = {gas_id: var.get() for gas_id, var in self.gas_components.items()}
        
        # Fittings
        fitting_data = {name: var.get() for name, var in self.fitting_counts.items()}
        
        return {
            "gas_components": gas_data,
            "comp_type": self.comp_type.get(),
            "p_in": self.p_in_var.get(), "p_unit": self.p_unit.get(),
            "t_val": self.t_var.get(), "t_unit": self.t_unit.get(),
            "flow_val": self.flow_var.get(), "flow_unit": self.flow_unit.get(),
            "calc_target": self.calc_target.get(),
            "thermo_model": self.thermo_model.get(),
            "flow_type": self.flow_type.get(),
            "material": self.material_combo.get(),
            "len_val": self.len_var.get(),
            "diam_val": self.diam_var.get(),
            "thick_val": self.thick_var.get(),
            "target_p_val": self.target_p_var.get(), "target_p_unit": self.target_p_unit.get(),
            "max_vel_val": self.max_vel_var.get(),
            "p_design_val": self.p_design_var.get(), "p_design_unit": self.p_design_unit.get(),
            "factor_f": self.factor_f.get(), "factor_e": self.factor_e.get(), "factor_t": self.factor_t.get(),
            "fitting_counts": fitting_data,
            "ball_valve_kv": self.ball_valve_kv.get()
        }

    def set_ui_state(self, data):
        # Önce mevcut gazları temizle
        for widget in self.gas_list_inner.winfo_children():
            widget.destroy()
        self.gas_components.clear()
        
        # Gazları Yükle
        for gas_id, val in data.get("gas_components", {}).items():
            # StringVar kullan (virgül desteği için)
            var = tk.StringVar(value=str(val))
            self.gas_components[gas_id] = var
            
            # İsim bul
            gas_name = next((v for k, v in COOLPROP_GASES.items() if k == gas_id), gas_id)
            
            row_frame = ttk.Frame(self.gas_list_inner)
            row_frame.pack(fill="x", pady=2)
            ttk.Label(row_frame, text=gas_name, width=25).pack(side="left")
            
            entry = ttk.Entry(row_frame, textvariable=var, width=8)
            entry.pack(side="left", padx=5)
            entry.bind("<KeyRelease>", lambda e: self.update_gas_total())
            var.trace_add("write", lambda *args: self.update_gas_total())
            
            ttk.Button(row_frame, text="X", width=3, command=lambda gid=gas_id, w=row_frame: self.remove_gas(gid, w)).pack(side="left")
        
        # Gaz toplamını güncelle
        self.update_gas_total()

        self.comp_type.set(data.get("comp_type", "Mol %"))
        self.p_in_var.set(data.get("p_in", 0))
        self.p_unit.set(data.get("p_unit", "Barg"))
        self.t_var.set(data.get("t_val", 25))
        self.t_unit.set(data.get("t_unit", "°C"))
        self.flow_var.set(data.get("flow_val", 0))
        self.flow_unit.set(data.get("flow_unit", "Sm³/h"))
        self.calc_target.set(data.get("calc_target", "Çıkış Basıncı"))
        self.thermo_model.set(data.get("thermo_model", "CoolProp (High Accuracy EOS)"))
        self.flow_type.set(data.get("flow_type", "Sıkıştırılamaz"))
        self.material_combo.set(data.get("material", "API 5L Grade B"))
        self.len_var.set(data.get("len_val", 100))
        self.diam_var.set(data.get("diam_val", 0))
        self.thick_var.set(data.get("thick_val", 0))
        self.target_p_var.set(data.get("target_p_val", 0))
        self.target_p_unit.set(data.get("target_p_unit", "Barg"))
        self.max_vel_var.set(data.get("max_vel_val", 20))
        self.p_design_var.set(data.get("p_design_val", 0))
        self.p_design_unit.set(data.get("p_design_unit", "Barg"))
        self.factor_f.set(data.get("factor_f", 0.72))
        self.factor_e.set(data.get("factor_e", 1.0))
        self.factor_t.set(data.get("factor_t", 1.0))
        self.ball_valve_kv.set(data.get("ball_valve_kv", 0))

        # Fittings
        fit_data = data.get("fitting_counts", {})
        for name, val in fit_data.items():
            if name in self.fitting_counts:
                self.fitting_counts[name].set(val)
        
        self.update_ui_visibility()

    def validate_inputs(self):
        """Kullanıcı girişlerini doğrular."""
        errors = []
        
        # 1. Gaz Bileşimi
        if not self.gas_components:
            errors.append("Lütfen en az bir gaz bileşeni ekleyin.")
        else:
            total_mole = sum(self.get_float_value(var, 0) for var in self.gas_components.values())
            if total_mole <= 0:
                errors.append("Toplam mol oranı 0'dan büyük olmalıdır.")
        
        # 2. Temel Parametreler
        if self.get_float_value(self.p_in_var, 0) <= 0: errors.append("Giriş basıncı pozitif olmalıdır.")
        if self.get_float_value(self.t_var, 25) <= -273.15: errors.append("Sıcaklık mutlak sıfırdan büyük olmalıdır.")
        if self.get_float_value(self.flow_var, 0) <= 0: errors.append("Akış debisi pozitif olmalıdır.")
        
        target = self.calc_target.get()
        
        # 3. Hedefe Özel Kontroller
        if target == "Çıkış Basıncı":
            if self.get_float_value(self.len_var, 0) <= 0: errors.append("Boru uzunluğu pozitif olmalıdır.")
            if self.get_float_value(self.diam_var, 0) <= 0: errors.append("Boru çapı pozitif olmalıdır.")
            diam = self.get_float_value(self.diam_var, 0)
            thick = self.get_float_value(self.thick_var, 0)
            if thick >= diam / 2: errors.append("Et kalınlığı yarıçaptan küçük olmalıdır.")
            
        elif target == "Maksimum Uzunluk":
            if self.get_float_value(self.target_p_var, 0) <= 0: errors.append("Hedef çıkış basıncı pozitif olmalıdır.")
            if self.get_float_value(self.diam_var, 0) <= 0: errors.append("Boru çapı pozitif olmalıdır.")
            
        elif target == "Minimum Çap":
            if self.get_float_value(self.max_vel_var, 0) <= 0: errors.append("Maksimum hız limiti pozitif olmalıdır.")
            if self.get_float_value(self.p_design_var, 0) <= 0: errors.append("Tasarım basıncı pozitif olmalıdır.")
            if self.flow_type.get() == "Sıkıştırılabilir" and self.get_float_value(self.len_var, 0) <= 0:
                errors.append("Sıkıştırılabilir akış çap hesabı için boru uzunluğu gereklidir.")

        if errors:
            messagebox.showwarning("Giriş Hatası", "\n".join(errors))
            return False
        return True

    # --- HESAPLAMA BAŞLATMA ---
    def start_calculation(self):
        # 0. Temel Validasyon
        if not self.validate_inputs(): return
        
        # 1. Gaz Bileşimi Kontrolü
        is_exact, total, mole_fractions, confirmed, error_msg = self.check_gas_composition()
        
        if error_msg:
            messagebox.showerror("Gaz Bileşimi Hatası", error_msg)
            return
        
        if not confirmed:
            return  # Kullanıcı iptal etti
        
        # Normalize bilgisi
        normalization_info = None
        if not is_exact:
            normalization_info = {
                "original_total": total,
                "message": f"Gaz bileşimi %{total:.2f} idi, %100'e normalize edildi."
            }
            self.log_message(f"⚠️ Gaz bileşimi normalize edildi: %{total:.2f} → %100", level="WARNING")

        # 2. Verileri Topla
        try:
            inputs = self.collect_inputs(mole_fractions_override=mole_fractions)
            inputs["normalization_info"] = normalization_info
        except ValueError as e:
            messagebox.showerror("Girdi Hatası", str(e))
            return

        # 3. Arayüzü Kilitle ve Progress Başlat
        self.is_calculating = True
        self.schematic_state = "calculating"
        self.update_progress(0, "Başlatılıyor...")
        self.progress_canvas.config(cursor="wait")
        self.refresh_schematic()  # Şemayı "hesaplanıyor" durumuna güncelle
        
        self.report_text.delete(1.0, "end")
        
        if normalization_info:
            self.report_text.insert("end", f"⚠️ {normalization_info['message']}\n\n")
        self.report_text.insert("end", "Hesaplama başlatıldı...\n")

        # 4. Thread Başlat
        threading.Thread(target=self.run_calculation_thread, args=(inputs,), daemon=True).start()
        
        # 5. Progress animasyonu başlat
        self._start_progress_animation()
        self.root.after(100, self.check_calc_queue)
    
    def _start_progress_animation(self):
        """Hesaplama süresince simüle edilmiş ilerleme animasyonu."""
        if not self.is_calculating:
            return
        
        # Yavaş yavaş ilerle ama %90'da dur (gerçek bitişi bekle)
        if self.progress_value < 90:
            # Hızlı başla, yavaşla
            increment = max(1, (90 - self.progress_value) / 20)
            self.progress_value = min(90, self.progress_value + increment)
            self.update_progress(self.progress_value)
        
        # Hala hesaplanıyorsa devam et (100ms arayla)
        if self.is_calculating and self.progress_value < 90:
            self.root.after(100, self._start_progress_animation)

    def get_float_value(self, var, default=0.0):
        """DoubleVar veya StringVar'dan normalize edilmiş float değer al."""
        try:
            # Önce doğrudan get() dene (DoubleVar için)
            val = var.get()
            if isinstance(val, (int, float)):
                return float(val)
            # String ise normalize et
            return ValidationHelper.parse_float(str(val), default=default) or default
        except (tk.TclError, ValueError, AttributeError):
            return default
    
    def get_int_value(self, var, default=0):
        """IntVar veya StringVar'dan normalize edilmiş int değer al."""
        try:
            val = var.get()
            if isinstance(val, int):
                return val
            if isinstance(val, float):
                return int(val)
            return ValidationHelper.parse_int(str(val), default=default) or default
        except (tk.TclError, ValueError, AttributeError):
            return default
    
    def collect_inputs(self, mole_fractions_override=None):
        """
        Hesaplama için gerekli tüm girdileri toplar.
        
        Args:
            mole_fractions_override: Önceden hesaplanmış ve normalize edilmiş mol fraksiyonları.
                                     None ise arayüzden hesaplanır.
        """
        # Gaz - Eğer override verilmişse onu kullan
        if mole_fractions_override is not None:
            mole_fractions = mole_fractions_override
        else:
            # Eski davranış - arayüzden hesapla
            if not self.gas_components: raise ValueError("En az bir gaz ekleyin.")
            total_pct = sum(self.get_float_value(v, 0) for v in self.gas_components.values())
            if total_pct <= 0: raise ValueError("Gaz yüzdeleri toplamı 0 olamaz.")
            
            mole_fractions = {k: self.get_float_value(v, 0)/total_pct for k, v in self.gas_components.items() if self.get_float_value(v, 0) > 0}
        
        if self.comp_type.get() == "Kütle %":
            mole_fractions = self.calculator.mass_to_mole_fraction(mole_fractions)

        # Basınç / Sıcaklık
        p_in_val = self.get_float_value(self.p_in_var, 0)
        p_unit = self.p_unit.get()
        # Birim Çevirme (Basitçe burada yapıyorum, normalde calculator'da da olabilir ama UI tarafında hazırlamak daha temiz)
        if p_unit == "Barg": P_in = (p_in_val + 1.01325) * 1e5
        elif p_unit == "Bara": P_in = p_in_val * 1e5
        elif p_unit == "Psig": P_in = (p_in_val + 14.696) * 6894.76
        else: P_in = p_in_val * 6894.76

        t_val = self.get_float_value(self.t_var, 25)
        t_unit = self.t_unit.get()
        if t_unit == "°C": T = t_val + 273.15
        elif t_unit == "°F": T = (t_val - 32) * 5/9 + 273.15
        else: T = t_val

        # Boru
        # Boru (Girdiler mm, hesaplama mm bekliyor)
        D_outer = self.get_float_value(self.diam_var, 0)
        t_wall = self.get_float_value(self.thick_var, 0)
        D_inner = D_outer - 2 * t_wall
        if D_inner <= 0: raise ValueError("Geçersiz boru çapı/kalınlığı.")

        # Fittings K
        total_k = 0
        for name, var in self.fitting_counts.items():
            count = self.get_int_value(var, 0)
            if count > 0:
                k = FITTING_K_FACTORS[name]
                # Vana Kv hesabı eklenebilir (basitlik için atlıyorum, V4'teki gibi eklenebilir)
                total_k += k * count

        flow_rate = self.get_float_value(self.flow_var, 0)
        len_val = self.get_float_value(self.len_var, 100)
        max_vel = self.get_float_value(self.max_vel_var, 20)
        factor_f = self.get_float_value(self.factor_f, 0.72)
        factor_e = self.get_float_value(self.factor_e, 1.0)
        factor_t = self.get_float_value(self.factor_t, 1.0)

        return {
            "P_in": P_in, "T": T, "mole_fractions": mole_fractions,
            "library_choice": self.thermo_model.get(),
            "flow_rate": flow_rate, "flow_unit": self.flow_unit.get(),
            "D_inner": D_inner, "L": len_val,
            "roughness": PIPE_ROUGHNESS.get(self.material_combo.get(), 4.57e-5),
            "total_k": total_k,
            "flow_property": self.flow_type.get(),
            "target": self.calc_target.get(),
            "P_out_target": self.convert_pressure_to_pa(self.get_float_value(self.target_p_var, 0), self.target_p_unit.get(), output_type="absolute") if self.calc_target.get() == "Maksimum Uzunluk" else 0,
            
            # Min Çap İçin Ekler
            "max_velocity": max_vel,
            "P_design": self.convert_pressure_to_pa(self.get_float_value(self.p_design_var, 0), self.p_design_unit.get(), output_type="gauge"), # Barlow için Gauge
            "material": self.material_combo.get(),
            "F": factor_f, "E": factor_e, "T_factor": factor_t
        }

    def convert_pressure_to_pa(self, val, unit, output_type="absolute"):
        # output_type: "absolute" veya "gauge"
        
        # Önce Mutlak (Absolute) Pa'ya çevir
        abs_pa = 0
        if unit == "Barg": abs_pa = (val + 1.01325) * 1e5
        elif unit == "Bara": abs_pa = val * 1e5
        elif unit == "Psig": abs_pa = (val + 14.696) * 6894.76
        elif unit == "Psia": abs_pa = val * 6894.76
        
        if output_type == "absolute":
            return abs_pa
        else: # gauge
            return max(0, abs_pa - 101325)

    def run_calculation_thread(self, inputs):
        try:
            target = inputs['target']
            result = None
            
            if target == "Çıkış Basıncı":
                result = self.calculator.calculate_pressure_drop(inputs)
                report = self.format_pressure_drop_report(inputs, result)
            elif target == "Maksimum Uzunluk":
                result = self.calculator.calculate_max_length(inputs)
                report = self.format_max_length_report(inputs, result)
            elif target == "Minimum Çap":
                result = self.calculator.calculate_min_diameter(inputs)
                report = self.format_min_diameter_report(inputs, result)
            else:
                report = "Bu özellik henüz V5 arayüzüne tam entegre edilmedi."

            self.calc_queue.put(("SUCCESS", {"report": report, "result": result}))
        except Exception as e:
            self.calc_queue.put(("ERROR", str(e)))

    def check_calc_queue(self):
        try:
            status, data = self.calc_queue.get_nowait()
            
            # Hesaplama tamamlandı - progress'i %100 yap
            self.update_progress(100, "Tamamlandı!")
            self.root.after(500, self.reset_progress_button)  # 0.5 sn sonra sıfırla
            
            if status == "SUCCESS":
                self.report_text.delete(1.0, "end")
                self.report_text.insert("end", data['report'])
                self.last_result = data['result'] # Sonucu sakla
                self.btn_show_graphs.config(state="normal")
                
                # Şema durumunu güncelle
                self.schematic_state = "completed"
                self.last_calculation_time = time.strftime("%H:%M:%S")
                self.refresh_schematic()  # Şemayı sonuçlarla güncelle
                
                # Tabloyu Doldur
                self.populate_results_table(data['result'])
                self.res_notebook.select(self.tab_table) # Tabloyu göster
                
                self.log_message("✓ Hesaplama başarıyla tamamlandı.", level="INFO")
            else:
                messagebox.showerror("Hesaplama Hatası", data)
                self.report_text.insert("end", f"\nHATA: {data}")
                self.btn_show_graphs.config(state="disabled")
                
                # Şema durumunu hata olarak güncelle
                self.schematic_state = "error"
                self.refresh_schematic()
                
                self.log_message(f"✗ Hesaplama hatası: {data}", level="ERROR")
        except queue.Empty:
            self.root.after(100, self.check_calc_queue)

    def populate_results_table(self, result):
        # Tabloyu temizle
        for item in self.res_tree.get_children():
            self.res_tree.delete(item)
            
        if not result: return
        
        # Yardımcı fonksiyon
        def add_row(param, value, unit="", tag=""):
            self.res_tree.insert("", "end", values=(param, value, unit), tags=(tag,))

        # Hedefe göre içerik
        target = self.calc_target.get()
        
        if target == "Çıkış Basıncı":
            add_row("Giriş Basıncı", f"{self.p_in_var.get():.2f}", self.p_unit.get())
            add_row("Çıkış Basıncı", f"{result['P_out']/1e5:.4f}", "bara")
            add_row("Toplam Basınç Kaybı", f"{result['delta_p_total']/1e5:.4f}", "bar")
            add_row("Giriş Hızı", f"{result['velocity_in']:.2f}", "m/s")
            add_row("Çıkış Hızı", f"{result['velocity_out']:.2f}", "m/s")
            
        elif target == "Maksimum Uzunluk":
            if "error" in result:
                 add_row("Durum", "HATA", "", "error")
                 add_row("Mesaj", result['error'], "")
            else:
                add_row("Maksimum Uzunluk", f"{result['L_max']:.2f}", "m")
                add_row("Reynolds", f"{result['Re']:.0f}", "")
                
        elif target == "Minimum Çap":
            if result['selected_pipe']:
                p = result['selected_pipe']
                add_row("Seçilen Boru", f"{p['nominal']}\"", f"Sch {p['schedule']}", "success")
                add_row("İç Çap", f"{p['D_inner_mm']:.2f}", "mm")
                add_row("Çıkış Hızı", f"{result['velocity_out']:.2f}", "m/s")
                add_row("Limit Hız", f"{result['max_vel']:.2f}", "m/s")
                
                status_tag = "success" if "Uygun" in result['velocity_status'] else "warning"
                add_row("Durum", result['velocity_status'], "", status_tag)
            else:
                add_row("Durum", "Uygun Boru Yok", "", "error")

        # Ortak Veriler (Debi vb.)
        if 'm_dot' in result:
             add_row("Kütlesel Debi", f"{result['m_dot']:.4f}", "kg/s")

    def format_pressure_drop_report(self, inputs, result):
        # Basit rapor formatı
        res = f"=== HESAPLAMA SONUCU ===\n"
        res += f"Hedef: Çıkış Basıncı\n"
        res += f"Giriş Basıncı: {inputs['P_in']/1e5:.4f} bara\n"
        res += f"Çıkış Basıncı: {result['P_out']/1e5:.4f} bara\n"
        res += f"Toplam Basınç Kaybı: {result['delta_p_total']/1e5:.4f} bar\n"
        res += f"  - Boru Kaybı: {result['delta_p_pipe']/1e5:.4f} bar\n"
        res += f"  - Fitting Kaybı: {result['delta_p_fittings']/1e5:.4f} bar\n\n"
        res += f"Akış Hızı (Giriş): {result['velocity_in']:.2f} m/s\n"
        res += f"Akış Hızı (Çıkış): {result['velocity_out']:.2f} m/s\n"
        res += f"Reynolds: {result['Re']:.0f}\n"
        res += f"Sürtünme Faktörü (f): {result['f']:.5f}\n"
        return res

    def format_max_length_report(self, inputs, result):
        res = f"=== HESAPLAMA SONUCU ===\n"
        res += f"Hedef: Maksimum Uzunluk\n"
        if "error" in result:
            res += f"HATA: {result['error']}\n"
        else:
            res += f"Maksimum Uzunluk: {result['L_max']:.2f} m\n"
            res += f"Reynolds: {result['Re']:.0f}\n"
        return res

    def format_min_diameter_report(self, inputs, result):
        res = f"=== HESAPLAMA SONUCU ===\n"
        res += f"Hedef: Minimum Çap Seçimi\n"
        res += f"Maksimum Hız Limiti: {result['max_vel']:.2f} m/s\n"
        res += f"Gerekli Min. İç Çap (Tahmini): {result['D_min_inner_mm']:.2f} mm\n"
        res += f"Gerçek Akış Hızı (Giriş): {result['flow_rate_actual']:.4f} m³/s\n\n"
        
        if result['selected_pipe']:
            pipe = result['selected_pipe']
            res += f"=== SEÇİLEN BORU (ASME B36.10M) ===\n"
            res += f"Nominal Çap: {pipe['nominal']}\"\n"
            res += f"Schedule: {pipe['schedule']}\n"
            res += f"Dış Çap: {pipe['OD_mm']:.2f} mm\n"
            res += f"Et Kalınlığı: {pipe['t_mm']:.2f} mm\n"
            res += f"İç Çap: {pipe['D_inner_mm']:.2f} mm\n"
            res += f"Gerekli Et Kalınlığı (Mukavemet): {pipe['t_required_mm']:.2f} mm\n\n"
            
            res += f"=== PERFORMANS (SEÇİLEN) ===\n"
            res += f"Giriş Hızı: {result['velocity_in']:.2f} m/s\n"
            res += f"Çıkış Hızı: {result['velocity_out']:.2f} m/s\n"
            res += f"Çıkış Basıncı: {result['P_out']/1e5:.4f} bara\n"
            res += f"Durum: {result['velocity_status']}\n"
            
            # Alternatifler
            if 'alternatives' in result and result['alternatives']:
                res += f"\n=== ALTERNATİF SENARYOLAR ===\n"
                
                # Thinner
                if 'thinner' in result['alternatives']:
                    alt = result['alternatives']['thinner']
                    p = alt['pipe']
                    r = alt['result']
                    res += f"\n[1] {alt['note']}:\n"
                    res += f"   Boru: {p['nominal']}\" {p['schedule']} (ID: {p['D_inner_mm']:.2f} mm)\n"
                    res += f"   Çıkış Hızı: {r['velocity_out']:.2f} m/s\n"
                    res += f"   Çıkış Basıncı: {r['P_out']/1e5:.4f} bara\n"
                
                # Thicker
                if 'thicker' in result['alternatives']:
                    alt = result['alternatives']['thicker']
                    p = alt['pipe']
                    r = alt['result']
                    res += f"\n[2] {alt['note']}:\n"
                    res += f"   Boru: {p['nominal']}\" {p['schedule']} (ID: {p['D_inner_mm']:.2f} mm)\n"
                    res += f"   Çıkış Hızı: {r['velocity_out']:.2f} m/s\n"
                    res += f"   Çıkış Basıncı: {r['P_out']/1e5:.4f} bara\n"

        else:
            res += "UYARI: Kriterlere uygun standart boru bulunamadı!\n"
            
        return res

    def draw_schematic(self, event=None):
        """Hesaplama hedefine ve duruma göre interaktif sistem şeması çizer."""
        canvas = self.schematic_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 100 or h < 100: return
        
        target = self.calc_target.get()
        state = getattr(self, 'schematic_state', 'pending')
        
        # ===== RENK KODLAMASI =====
        colors = {
            'known': "#1976d2",       # Mavi - Bilinen/Girilen değerler
            'unknown': "#d32f2f",     # Kırmızı - Bilinmeyen/Hesaplanacak değerler
            'calculated': "#2e7d32", # Yeşil - Hesaplanmış/Bulunan değerler
            'warning': "#e65100",     # Turuncu - Uyarı gerektiren değerler
            'text': "#37474f",        # Koyu gri - Normal metin
            'pipe_fill': "#e3f2fd",   # Açık mavi - Boru dolgusu
            'pipe_outline': "#1565c0" # Koyu mavi - Boru çerçevesi
        }
        
        # Koordinatlar
        mid_y = h / 2 + 10  # Başlık için biraz aşağı kaydır
        margin_x = 100
        pipe_start_x = margin_x
        pipe_end_x = w - margin_x
        pipe_height = 35

        # ===== DURUM GÖSTERGESİ (Sağ üst köşe) =====
        status_config = {
            'pending': ("📝 " + t("schematic_pending"), "#757575", "#f5f5f5"),
            'calculating': ("⏳ " + t("schematic_calculating"), "#ff9800", "#fff3e0"),
            'completed': ("✅ " + t("schematic_completed"), "#2e7d32", "#e8f5e9"),
            'error': ("❌ " + t("schematic_error"), "#d32f2f", "#ffebee")
        }
        status_text, status_color, status_bg = status_config.get(state, status_config['pending'])
        
        # Durum kutusu
        canvas.create_rectangle(w - 200, 5, w - 5, 35, fill=status_bg, outline=status_color, width=1)
        canvas.create_text(w - 102, 20, text=status_text, font=("Segoe UI", 9), fill=status_color)
        
        # Son hesaplama zamanı (varsa)
        if state == 'completed' and hasattr(self, 'last_calculation_time') and self.last_calculation_time:
            canvas.create_text(w - 102, 48, text=f"🕐 {self.last_calculation_time}", 
                              font=("Segoe UI", 8), fill="#757575")

        # ===== BAŞLIK =====
        title_map = {
            t("target_pressure_drop"): ("🎯 " + t("schematic_target_pressure"), "P_in, T, Q, L, D → P_out"),
            t("target_max_length"): ("📏 " + t("schematic_target_length"), "P_in, P_out, T, Q, D → L_max"),
            t("target_min_diameter"): ("⭕ " + t("schematic_target_diameter"), "P_in, T, Q, V_max → D_min")
        }
        title, subtitle = title_map.get(target, (target, ""))
        
        canvas.create_text(w/2 - 50, 20, text=title, 
                          font=("Segoe UI", 12, "bold"), fill=colors['known'], anchor="e")
        canvas.create_text(w/2 - 45, 20, text=f"  |  {subtitle}", 
                          font=("Segoe UI", 9), fill=colors['text'], anchor="w")

        # ===== BORU ÇİZİMİ =====
        # Durum bazlı boru stili
        if state == 'calculating':
            # Hesaplanıyor - animasyonlu noktalı çerçeve
            canvas.create_rectangle(pipe_start_x, mid_y - pipe_height/2, 
                                   pipe_end_x, mid_y + pipe_height/2, 
                                   fill="#fff8e1", outline="#ffc107", width=3, dash=(8, 4))
        elif state == 'completed':
            # Tamamlandı - yeşil çerçeve
            canvas.create_rectangle(pipe_start_x, mid_y - pipe_height/2, 
                                   pipe_end_x, mid_y + pipe_height/2, 
                                   fill="#e8f5e9", outline=colors['calculated'], width=2)
        elif state == 'error':
            # Hata - kırmızı çerçeve
            canvas.create_rectangle(pipe_start_x, mid_y - pipe_height/2, 
                                   pipe_end_x, mid_y + pipe_height/2, 
                                   fill="#ffebee", outline=colors['unknown'], width=2)
        else:
            # Bekliyor - normal
            if target == t("target_min_diameter"):
                canvas.create_rectangle(pipe_start_x, mid_y - pipe_height/2, 
                                       pipe_end_x, mid_y + pipe_height/2, 
                                       fill="#fff3e0", outline=colors['unknown'], width=2, dash=(5, 3))
            elif target == t("target_max_length"):
                canvas.create_rectangle(pipe_start_x, mid_y - pipe_height/2, 
                                       pipe_end_x - 30, mid_y + pipe_height/2, 
                                       fill=colors['pipe_fill'], outline=colors['pipe_outline'], width=2)
                # Kesik çizgi (belirsiz uzunluk)
                for i in range(5):
                    y_off = -pipe_height/2 + i * (pipe_height/4)
                    canvas.create_line(pipe_end_x - 30, mid_y + y_off, 
                                      pipe_end_x - 10, mid_y + y_off + 3,
                                      fill=colors['pipe_outline'], dash=(2, 2), width=2)
            else:
                canvas.create_rectangle(pipe_start_x, mid_y - pipe_height/2, 
                                       pipe_end_x, mid_y + pipe_height/2, 
                                       fill=colors['pipe_fill'], outline=colors['pipe_outline'], width=2)

        # ===== AKIŞ OKLARI =====
        arrow_color = colors['calculated'] if state == 'completed' else "#4caf50"
        canvas.create_line(25, mid_y, pipe_start_x, mid_y, arrow=tk.LAST, width=4, fill=arrow_color)
        canvas.create_text(45, mid_y - 22, text="➡️ " + t("schematic_inlet"), font=("Segoe UI", 9, "bold"), fill=arrow_color)
        
        canvas.create_line(pipe_end_x, mid_y, w - 25, mid_y, arrow=tk.LAST, width=4, fill=arrow_color)
        canvas.create_text(w - 45, mid_y - 22, text=t("schematic_outlet") + " ➡️", font=("Segoe UI", 9, "bold"), fill=arrow_color)

        # ===== GİRİŞ PARAMETRELERİ (Sol Panel) =====
        try:
            left_x = 15
            left_y = mid_y - 75
            lh = 20  # line height
            
            # Giriş Basıncı (her zaman bilinen)
            p_in_val = self.get_float_value(self.p_in_var, 0)
            canvas.create_text(left_x, left_y, 
                              text=f"🔵 {t('schematic_p_inlet')}: {p_in_val} {self.p_unit.get()}", 
                              anchor="w", font=("Segoe UI", 9, "bold"), fill=colors['known'])
            
            # Sıcaklık
            t_val = self.get_float_value(self.t_var, 25)
            canvas.create_text(left_x, left_y + lh, 
                              text=f"🌡️ {t('schematic_temp')}: {t_val} {self.t_unit.get()}", 
                              anchor="w", font=("Segoe UI", 9), fill=colors['known'])
            
            # Debi
            flow_val = self.get_float_value(self.flow_var, 0)
            canvas.create_text(left_x, left_y + 2*lh, 
                              text=f"💨 {t('schematic_flow')}: {flow_val} {self.flow_unit.get()}", 
                              anchor="w", font=("Segoe UI", 9), fill=colors['known'])

            # ===== HEDEF BAZLI ÖZEL GÖSTERİMLER =====
            result = getattr(self, 'last_result', None) if state == 'completed' else None
            
            if target == t("target_pressure_drop"):
                self._draw_pressure_drop_schematic(canvas, w, h, mid_y, pipe_start_x, pipe_end_x, 
                                                   pipe_height, colors, result, state)
                
            elif target == t("target_max_length"):
                self._draw_max_length_schematic(canvas, w, h, mid_y, pipe_start_x, pipe_end_x, 
                                                pipe_height, colors, result, state)
                
            elif target == t("target_min_diameter"):
                self._draw_min_diameter_schematic(canvas, w, h, mid_y, pipe_start_x, pipe_end_x, 
                                                  pipe_height, colors, result, state)

            # ===== FITTINGS GÖSTERİMİ =====
            total_fit = sum(self.get_int_value(v, 0) for v in self.fitting_counts.values())
            if total_fit > 0:
                fit_x = pipe_start_x + 70
                canvas.create_rectangle(fit_x - 10, mid_y - 14, fit_x + 10, mid_y + 14, 
                                        fill="#ff9800", outline="#e65100", width=2)
                canvas.create_text(fit_x, mid_y, text="⚙️", font=("Segoe UI", 9))
                canvas.create_text(fit_x, mid_y - 30, 
                                  text=f"🔧 {total_fit} Fitting", 
                                  font=("Segoe UI", 8, "bold"), fill=colors['warning'])

        except Exception as e:
            canvas.create_text(w/2, h - 20, text=f"⚠️ Çizim Hatası: {str(e)}", fill="red")
    
    def _draw_pressure_drop_schematic(self, canvas, w, h, mid_y, pipe_start_x, pipe_end_x, pipe_height, colors, result, state):
        """Çıkış Basıncı hesabı için şema detayları."""
        # Boru altı: Uzunluk (bilinen)
        L_val = self.get_float_value(self.len_var, 0)
        canvas.create_line(pipe_start_x, mid_y + 55, pipe_end_x, mid_y + 55, 
                          arrow=tk.BOTH, fill=colors['known'], width=1)
        canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 70, 
                          text=f"📐 {t('schematic_length')}: {L_val} m", 
                          font=("Segoe UI", 9), fill=colors['known'])
        
        # Boru içi: Çap (bilinen)
        D_val = self.get_float_value(self.diam_var, 0)
        t_wall = self.get_float_value(self.thick_var, 0)
        D_inner = D_val - 2 * t_wall if D_val > 0 else 0
        canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y, 
                          text=f"⭕ OD:{D_val} | ID:{D_inner:.1f} mm", 
                          font=("Segoe UI", 8), fill=colors['text'])
        
        # Sağ üst: Çıkış Basıncı (bilinmeyen veya hesaplanmış)
        if result and 'P_out' in result:
            # Hesaplanmış - yeşil kutu
            p_out = result['P_out'] / 1e5
            delta_p = result.get('delta_p_total', 0) / 1e5
            v_out = result.get('velocity_out', 0)
            v_in = result.get('velocity_in', 0)
            
            # Ana sonuç kutusu
            canvas.create_rectangle(w - 165, mid_y - 90, w - 5, mid_y - 30, 
                                    fill="#e8f5e9", outline=colors['calculated'], width=2)
            canvas.create_text(w - 85, mid_y - 75, 
                              text=f"✅ {t('schematic_p_outlet')}: {p_out:.3f} bar", 
                              font=("Segoe UI", 10, "bold"), fill=colors['calculated'])
            canvas.create_text(w - 85, mid_y - 55, 
                              text=f"📉 ΔP_toplam: {delta_p:.3f} bar", 
                              font=("Segoe UI", 8), fill=colors['warning'])
            
            # Hız profili (boru altı)
            v_color = colors['warning'] if v_out > 20 else colors['calculated']
            canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 90, 
                              text=f"💨 {t('schematic_velocity')}: {v_in:.1f} → {v_out:.1f} m/s", 
                              font=("Segoe UI", 9, "bold"), fill=v_color)
            
            # ===== DETAY PANELİ (Alt kısım) =====
            detail_y = h - 60
            canvas.create_line(15, detail_y - 25, w - 15, detail_y - 25, 
                              fill="#e0e0e0", width=1)
            canvas.create_text(w/2, detail_y - 35, 
                              text="📊 " + t("schematic_details"), 
                              font=("Segoe UI", 9, "bold"), fill=colors['known'])
            
            # Reynolds sayısı
            Re = result.get('Re', 0)
            Re_text = f"Re: {Re:.0f}" if Re < 10000 else f"Re: {Re/1000:.1f}k"
            flow_regime = t("detail_laminar") if Re < 2300 else (t("detail_transition") if Re < 4000 else t("detail_turbulent"))
            regime_color = colors['calculated'] if Re >= 4000 else colors['warning']
            canvas.create_text(w/6, detail_y, 
                              text=f"🔄 {Re_text} ({flow_regime})", 
                              font=("Segoe UI", 8), fill=regime_color)
            
            # Sürtünme faktörü
            f = result.get('friction_factor', 0)
            canvas.create_text(2*w/6, detail_y, 
                              text=f"📏 f: {f:.5f}", 
                              font=("Segoe UI", 8), fill=colors['text'])
            
            # Basınç kaybı dağılımı
            dp_pipe = result.get('delta_p_pipe', 0) / 1e5
            dp_fittings = result.get('delta_p_fittings', 0) / 1e5
            total_dp = dp_pipe + dp_fittings if (dp_pipe + dp_fittings) > 0 else 1
            pipe_pct = (dp_pipe / total_dp) * 100 if total_dp > 0 else 0
            
            canvas.create_text(3*w/6, detail_y, 
                              text=f"🔧 {t('detail_pipe_loss')}: {dp_pipe:.3f} bar ({pipe_pct:.0f}%)", 
                              font=("Segoe UI", 8), fill=colors['text'])
            
            canvas.create_text(4*w/6, detail_y, 
                              text=f"⚙️ Fitting: {dp_fittings:.3f} bar ({100-pipe_pct:.0f}%)", 
                              font=("Segoe UI", 8), fill=colors['warning'])
            
            # Yoğunluk bilgisi
            rho = result.get('rho_in', 0)
            canvas.create_text(5*w/6, detail_y, 
                              text=f"⚖️ ρ: {rho:.2f} kg/m³", 
                              font=("Segoe UI", 8), fill=colors['text'])
        else:
            # Bilinmeyen - kırmızı kutu
            canvas.create_rectangle(w - 150, mid_y - 85, w - 5, mid_y - 45, 
                                    fill="#ffebee", outline=colors['unknown'], width=2)
            canvas.create_text(w - 77, mid_y - 65, 
                              text=f"❓ {t('schematic_p_outlet')} = {t('schematic_unknown')}", 
                              font=("Segoe UI", 11, "bold"), fill=colors['unknown'])
    
    def _draw_max_length_schematic(self, canvas, w, h, mid_y, pipe_start_x, pipe_end_x, pipe_height, colors, result, state):
        """Maksimum Uzunluk hesabı için şema detayları."""
        # Sağ üst: Hedef Çıkış Basıncı (bilinen)
        p_out_target = self.get_float_value(self.target_p_var, 0)
        canvas.create_rectangle(w - 170, mid_y - 85, w - 5, mid_y - 50, 
                                fill="#e3f2fd", outline=colors['known'], width=2)
        canvas.create_text(w - 87, mid_y - 67, 
                          text=f"🎯 {t('schematic_p_target')}: {p_out_target} {self.target_p_unit.get()}", 
                          font=("Segoe UI", 9, "bold"), fill=colors['known'])
        
        # Boru içi: Çap (bilinen)
        D_val = self.get_float_value(self.diam_var, 0)
        canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y, 
                          text=f"⭕ {t('schematic_diameter')}: {D_val} mm", 
                          font=("Segoe UI", 9), fill=colors['known'])
        
        # Boru altı: Uzunluk (bilinmeyen veya hesaplanmış)
        if result and 'L_max' in result:
            # Hesaplanmış - yeşil kutu
            L_max = result['L_max']
            canvas.create_rectangle((pipe_start_x + pipe_end_x)/2 - 90, mid_y + 45, 
                                    (pipe_start_x + pipe_end_x)/2 + 90, mid_y + 85, 
                                    fill="#e8f5e9", outline=colors['calculated'], width=2)
            canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 55, 
                              text=f"✅ L_max = {L_max:.2f} m", 
                              font=("Segoe UI", 11, "bold"), fill=colors['calculated'])
            canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 75, 
                              text=f"({L_max/1000:.3f} km)", 
                              font=("Segoe UI", 8), fill=colors['text'])
            
            # ===== DETAY PANELİ (Alt kısım) =====
            detail_y = h - 60
            canvas.create_line(15, detail_y - 25, w - 15, detail_y - 25, 
                              fill="#e0e0e0", width=1)
            canvas.create_text(w/2, detail_y - 35, 
                              text="📊 " + t("schematic_details"), 
                              font=("Segoe UI", 9, "bold"), fill=colors['known'])
            
            # Reynolds ve akış rejimi
            Re = result.get('Re', 0)
            Re_text = f"Re: {Re:.0f}" if Re < 10000 else f"Re: {Re/1000:.1f}k"
            flow_regime = t("detail_laminar") if Re < 2300 else (t("detail_transition") if Re < 4000 else t("detail_turbulent"))
            canvas.create_text(w/5, detail_y, 
                              text=f"🔄 {Re_text} ({flow_regime})", 
                              font=("Segoe UI", 8), fill=colors['calculated'])
            
            # Hız
            v = result.get('velocity_in', 0)
            v_color = colors['warning'] if v > 20 else colors['text']
            canvas.create_text(2*w/5, detail_y, 
                              text=f"💨 {t('schematic_velocity')}: {v:.1f} m/s", 
                              font=("Segoe UI", 8), fill=v_color)
            
            # Basınç farkı
            delta_p = result.get('delta_p_available', 0) / 1e5
            canvas.create_text(3*w/5, detail_y, 
                              text=f"📉 ΔP kullanılan: {delta_p:.3f} bar", 
                              font=("Segoe UI", 8), fill=colors['warning'])
            
            # Sürtünme faktörü
            f = result.get('friction_factor', 0)
            canvas.create_text(4*w/5, detail_y, 
                              text=f"📏 f: {f:.5f}", 
                              font=("Segoe UI", 8), fill=colors['text'])
        else:
            # Bilinmeyen - kırmızı kutu
            canvas.create_line(pipe_start_x, mid_y + 55, pipe_end_x - 30, mid_y + 55, 
                              arrow=tk.BOTH, fill=colors['unknown'], width=2, dash=(5, 3))
            canvas.create_rectangle((pipe_start_x + pipe_end_x)/2 - 70, mid_y + 45, 
                                    (pipe_start_x + pipe_end_x)/2 + 70, mid_y + 80, 
                                    fill="#ffebee", outline=colors['unknown'], width=2)
            canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 62, 
                              text="❓ L_max = ??? m", 
                              font=("Segoe UI", 11, "bold"), fill=colors['unknown'])
    
    def _draw_min_diameter_schematic(self, canvas, w, h, mid_y, pipe_start_x, pipe_end_x, pipe_height, colors, result, state):
        """Minimum Çap hesabı için şema detayları."""
        # Boru içi: Hız limiti (bilinen)
        v_max = self.get_float_value(self.max_vel_var, 20)
        canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y - 5, 
                          text=f"⚡ V_max ≤ {v_max} m/s", 
                          font=("Segoe UI", 9, "bold"), fill=colors['warning'])
        
        # Sıkıştırılabilir ise uzunluk göster
        if self.flow_type.get() == t("flow_compressible"):
            L_val = self.get_float_value(self.len_var, 0)
            canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 60, 
                              text=f"📐 {t('schematic_length')}: {L_val} m", 
                              font=("Segoe UI", 9), fill=colors['known'])
        
        # Sağ taraf: Çap (bilinmeyen veya hesaplanmış)
        if result and result.get('selected_pipe'):
            # Hesaplanmış - yeşil kutu
            pipe = result['selected_pipe']
            v_out = result.get('velocity_out', 0)
            v_color = colors['warning'] if v_out > v_max * 0.9 else colors['calculated']
            
            canvas.create_rectangle(w - 165, mid_y - 55, w - 5, mid_y + 55, 
                                    fill="#e8f5e9", outline=colors['calculated'], width=2)
            canvas.create_text(w - 85, mid_y - 38, 
                              text=f"✅ {pipe['nominal']}\"", 
                              font=("Segoe UI", 13, "bold"), fill=colors['calculated'])
            canvas.create_text(w - 85, mid_y - 18, 
                              text=f"Sch {pipe['schedule']}", 
                              font=("Segoe UI", 9), fill=colors['text'])
            canvas.create_text(w - 85, mid_y + 2, 
                              text=f"ID: {pipe['D_inner_mm']:.1f} mm", 
                              font=("Segoe UI", 9), fill=colors['known'])
            canvas.create_text(w - 85, mid_y + 22, 
                              text=f"OD: {pipe['D_outer_mm']:.1f} mm", 
                              font=("Segoe UI", 8), fill=colors['text'])
            canvas.create_text(w - 85, mid_y + 42, 
                              text=f"💨 V: {v_out:.1f} m/s", 
                              font=("Segoe UI", 9, "bold"), fill=v_color)
            
            # ===== DETAY PANELİ (Alt kısım) =====
            detail_y = h - 60
            canvas.create_line(15, detail_y - 25, w - 15, detail_y - 25, 
                              fill="#e0e0e0", width=1)
            canvas.create_text(w/2, detail_y - 35, 
                              text="📊 " + t("schematic_selection_details"), 
                              font=("Segoe UI", 9, "bold"), fill=colors['known'])
            
            # Minimum teorik çap
            D_min_theo = result.get('D_min_theoretical_mm', 0)
            canvas.create_text(w/5, detail_y, 
                              text=f"📐 {t('detail_min_theoretical')}: {D_min_theo:.1f} mm", 
                              font=("Segoe UI", 8), fill=colors['text'])
            
            # Et kalınlığı
            t_wall = pipe.get('t_mm', 0)
            canvas.create_text(2*w/5, detail_y, 
                              text=f"📏 {t('detail_wall_thickness')}: {t_wall:.2f} mm", 
                              font=("Segoe UI", 8), fill=colors['text'])
            
            # Hız kullanım oranı
            v_usage = (v_out / v_max) * 100 if v_max > 0 else 0
            v_usage_color = colors['calculated'] if v_usage < 80 else colors['warning']
            canvas.create_text(3*w/5, detail_y, 
                              text=f"⚡ {t('detail_velocity_usage')}: %{v_usage:.0f}", 
                              font=("Segoe UI", 8), fill=v_usage_color)
            
            # Alternatif boru sayısı
            alternatives = result.get('alternative_pipes', [])
            canvas.create_text(4*w/5, detail_y, 
                              text=f"🔧 {len(alternatives)} " + t("detail_alternatives"), 
                              font=("Segoe UI", 8), fill=colors['known'])
        else:
            # Bilinmeyen - kırmızı kutu
            canvas.create_line(pipe_end_x + 15, mid_y - pipe_height/2, 
                              pipe_end_x + 15, mid_y + pipe_height/2, 
                              arrow=tk.BOTH, fill=colors['unknown'], width=2)
            canvas.create_rectangle(w - 120, mid_y - 35, w - 10, mid_y + 35, 
                                    fill="#ffebee", outline=colors['unknown'], width=2)
            canvas.create_text(w - 65, mid_y, 
                              text="❓ D = ?", 
                              font=("Segoe UI", 14, "bold"), fill=colors['unknown'])

    def show_graphs(self):
        if not hasattr(self, 'last_result') or not self.last_result: return
        
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Hata", "Grafik çizimi için 'matplotlib' kütüphanesi gerekli.\nLütfen 'pip install matplotlib' komutu ile yükleyin.")
            return

        data = self.last_result.get('profile_data')
        if not data:
            messagebox.showinfo("Bilgi", "Bu hesaplama için grafik verisi mevcut değil.")
            return

        # Yeni Pencere
        graph_win = tk.Toplevel(self.root)
        graph_win.title("Basınç ve Hız Profili")
        graph_win.geometry("1000x600")

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        
        # Mesafe (m) -> km çevrilebilir ama m kalsın
        dist = data['distance']
        press = [p/1e5 for p in data['pressure']] # bar
        vel = data['velocity'] # m/s

        # Basınç Grafiği
        ax1.plot(dist, press, 'b-', linewidth=2)
        ax1.set_ylabel('Basınç (bar)', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.grid(True, linestyle='--', alpha=0.7)
        ax1.set_title('Hat Boyunca Basınç Değişimi')

        # Hız Grafiği
        ax2.plot(dist, vel, 'r-', linewidth=2)
        ax2.set_xlabel('Mesafe (m)')
        ax2.set_ylabel('Hız (m/s)', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        ax2.grid(True, linestyle='--', alpha=0.7)
        ax2.set_title('Hat Boyunca Hız Değişimi')

        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=graph_win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # --- Güncelleme İşlevleri ---
    def silent_update_check(self):
        try:
            update_info = self.updater.check_for_update(current_version=APP_VERSION)
            if update_info and update_info.get("has_update"):
                self.log_message(f"{t('update_new_version')}: {update_info['latest_version']}")
        except Exception as e:
            self.log_message(f"Silent update check failed: {e}", level="WARNING")

    def check_updates(self):
        try:
            self.log_message(t("update_checking"))
            info = self.updater.check_for_update(current_version=APP_VERSION)
            if not info:
                messagebox.showinfo(t("dialog_update"), t("update_config_error"))
                return
            if info["has_update"]:
                body = info.get('body', '')
                preview = (body[:500] + ('...' if len(body) > 500 else '')) if body else 'N/A'
                msg = (
                    f"{t('update_new_version')}: {info['latest_version']}\n\n"
                    f"{t('update_changes')}: {preview}\n\n"
                    f"{t('update_download_ask')}"
                )
                if messagebox.askyesno(t("update_available"), msg):
                    self.download_latest_release()
            else:
                messagebox.showinfo(t("dialog_update"), t("update_up_to_date"))
        except Exception as e:
            messagebox.showerror(t("dialog_error"), str(e))

    def download_latest_release(self):
        try:
            self.log_message(t("update_downloading"))
            asset_path = self.updater.download_latest_asset()
            if asset_path:
                self.last_download_path = asset_path
                if messagebox.askyesno(t("dialog_info"), f"{t('update_downloaded')}: {asset_path}\n\n{t('update_apply_ask')}"):
                    self.apply_update(asset_path)
                else:
                    messagebox.showinfo(t("dialog_info"), t("update_later"))
                try:
                    os.startfile(os.path.dirname(asset_path))
                except Exception:
                    webbrowser.open(os.path.dirname(asset_path))
            else:
                messagebox.showinfo("Bilgi", "İndirilebilir bir varlık bulunamadı.")
        except Exception as e:
            messagebox.showerror("İndirme Hatası", str(e))

    def open_update_config(self):
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(cfg_path):
                os.startfile(cfg_path)
            else:
                messagebox.showinfo("Bilgi", f"Yapılandırma dosyası bulunamadı: {cfg_path}")
        except Exception as e:
            messagebox.showerror("Açma Hatası", str(e))

    def apply_update_from_zip_file(self):
        path = filedialog.askopenfilename(filetypes=[("Zip Files", "*.zip")])
        if not path:
            return
        self.apply_update(path)

    def apply_update(self, zip_path: str):
        try:
            target_dir = os.path.dirname(__file__)
            info = self.updater.apply_update_from_zip(zip_path, target_dir)
            backup = info.get("backup_dir") if info else None
            msg = "Güncelleme uygulandı. Uygulamayı yeniden başlatmanız önerilir."
            if backup:
                msg += f"\nYedek klasör: {backup}"
            messagebox.showinfo("Güncelleme", msg)
        except Exception as e:
            messagebox.showerror("Güncelleme Hatası", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = GasFlowCalculatorApp(root)
    root.mainloop()
