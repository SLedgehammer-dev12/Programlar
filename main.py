import tkinter as tk
import json
from tkinter import ttk, messagebox, filedialog, Menu
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import time
import math

# Modüler importlar
from data import COOLPROP_GASES, PIPE_MATERIALS, PIPE_ROUGHNESS, FITTING_K_FACTORS
from calculations import GasFlowCalculator

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

class GasFlowCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Doğal Gaz Hesaplayıcı V5 (Modüler & Ergonomik)")
        self.root.geometry("1450x950")
        self.root.minsize(1100, 800)

        # Hesaplama Motoru
        self.calculator = GasFlowCalculator()
        self.calculator.set_log_callback(self.log_message)

        # Değişkenler
        self.gas_components = {}
        self.fitting_counts = {}
        self.ball_valve_kv = tk.DoubleVar(value=0.0)
        self.ball_valve_cv = tk.DoubleVar(value=0.0)
        self.log_queue = queue.Queue()
        self.calc_queue = queue.Queue()

        # Stil
        self.setup_styles()
        
        # Arayüz Kurulumu
        self.create_menu()
        self.create_main_layout()
        
        self.log_message("PROGRAM BAŞLATILDI: Versiyon 5 (Refactored)")

    def create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Dosya", menu=file_menu)
        file_menu.add_command(label="Projeyi Kaydet (JSON)", command=self.save_project)
        file_menu.add_command(label="Proje Aç (JSON)", command=self.load_project)
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.root.quit)

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
        widget = event.widget
        try:
            val = float(widget.get())
            if val < 0: raise ValueError
            widget.config(bg="white")
        except ValueError:
            widget.config(bg="#ffe6e6") # Hata durumunda hafif kırmızı

    def create_main_layout(self):
        # Ana Notebook (Sekmeler)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        # 1. Hesaplama Sekmesi
        calc_tab = ttk.Frame(self.notebook)
        self.notebook.add(calc_tab, text="  Hesaplama & Tasarım  ")
        self.create_calc_tab_content(calc_tab)

        # 2. Log Sekmesi
        log_tab = ttk.Frame(self.notebook)
        self.notebook.add(log_tab, text="  Sistem Logları  ")
        self.create_log_tab_content(log_tab)

        # Alt Bilgi / Butonlar
        self.create_footer()
        
        # Validasyon Bağlamaları
        self.root.bind_class("TEntry", "<FocusOut>", self.validate_float)

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
        ttk.Label(right_panel, text="Hesaplama Sonuçları", style="Header.TLabel").pack(anchor="w", pady=(0, 5))
        
        # Sonuç Sekmeleri
        self.res_notebook = ttk.Notebook(right_panel)
        self.res_notebook.pack(fill="both", expand=True)
        
        # 1. Tablo Sekmesi
        self.tab_table = ttk.Frame(self.res_notebook)
        self.res_notebook.add(self.tab_table, text="Özet Tablo")
        
        # Treeview
        cols = ("param", "value", "unit")
        self.res_tree = ttk.Treeview(self.tab_table, columns=cols, show="headings", height=20)
        self.res_tree.heading("param", text="Parametre")
        self.res_tree.heading("value", text="Değer")
        self.res_tree.heading("unit", text="Birim")
        
        self.res_tree.column("param", width=180)
        self.res_tree.column("value", width=100, anchor="e")
        self.res_tree.column("unit", width=80, anchor="w")
        
        self.res_tree.tag_configure("success", foreground="green")
        self.res_tree.tag_configure("warning", foreground="orange")
        self.res_tree.tag_configure("error", foreground="red")
        
        self.res_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 2. Şematik Görünüm
        self.tab_schematic = ttk.Frame(self.res_notebook)
        self.res_notebook.add(self.tab_schematic, text="Sistem Şeması")
        
        self.schematic_canvas = tk.Canvas(self.tab_schematic, bg="white")
        self.schematic_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.schematic_canvas.bind("<Configure>", self.draw_schematic)

        # 3. Metin Sekmesi
        self.tab_text = ttk.Frame(self.res_notebook)
        self.res_notebook.add(self.tab_text, text="Detaylı Rapor")
        
        self.report_text = ScrolledText(self.tab_text, width=50, height=40, font=("Consolas", 10))
        self.report_text.pack(fill="both", expand=True)
        
        btn_frame = ttk.Frame(right_panel)
        btn_frame.pack(fill="x", pady=10)
        
        self.calc_button = tk.Button(btn_frame, text="HESAPLA", bg="#28a745", fg="white", font=("Segoe UI", 11, "bold"), height=2, command=self.start_calculation)
        self.calc_button.pack(fill="x")
        
        self.btn_show_graphs = ttk.Button(btn_frame, text="Grafikleri Göster", command=self.show_graphs, state="disabled")
        self.btn_show_graphs.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="Raporu Kaydet", command=self.save_report).pack(fill="x", pady=5)

    def create_gas_section(self, parent):
        frame = ttk.LabelFrame(parent, text="1. Gaz Karışımı", style="Bold.TLabelframe", padding=10)
        frame.pack(fill="x", pady=5)
        
        # Üst kısım: Arama ve Ekleme
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill="x")
        
        ttk.Label(top_frame, text="Gaz Ara:").pack(side="left")
        self.gas_search_var = tk.StringVar()
        self.gas_search_var.trace("w", self.filter_gas_list)
        entry = ttk.Entry(top_frame, textvariable=self.gas_search_var, width=20)
        entry.pack(side="left", padx=5)
        
        self.gas_combo = ttk.Combobox(top_frame, values=list(COOLPROP_GASES.values()), width=25, state="readonly")
        self.gas_combo.pack(side="left", padx=5)
        self.gas_combo.set("Gaz Seçin")
        
        ttk.Button(top_frame, text="+ Ekle", command=self.add_gas_component).pack(side="left")
        
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
        
        # Bileşim Türü
        type_frame = ttk.Frame(frame)
        type_frame.pack(fill="x", pady=(5,0))
        ttk.Label(type_frame, text="Bileşim Türü:").pack(side="left")
        self.comp_type = ttk.Combobox(type_frame, values=["Mol %", "Kütle %"], width=10, state="readonly")
        self.comp_type.set("Mol %")
        self.comp_type.pack(side="left", padx=5)

    def create_process_section(self, parent):
        frame = ttk.LabelFrame(parent, text="2. Proses Şartları", style="Bold.TLabelframe", padding=10)
        frame.pack(fill="x", pady=5)
        
        grid = ttk.Frame(frame)
        grid.pack(fill="x")
        
        # Satır 1: Basınç & Sıcaklık
        ttk.Label(grid, text="Giriş Basıncı:").grid(row=0, column=0, sticky="w", pady=5)
        self.p_in_var = tk.DoubleVar()
        ttk.Entry(grid, textvariable=self.p_in_var, width=10).grid(row=0, column=1, padx=5)
        self.p_unit = ttk.Combobox(grid, values=["Barg", "Bara", "Psig", "Psia"], width=8, state="readonly")
        self.p_unit.set("Barg")
        self.p_unit.grid(row=0, column=2)
        
        ttk.Label(grid, text="Sıcaklık:").grid(row=0, column=3, sticky="w", padx=(20, 5))
        self.t_var = tk.DoubleVar(value=25)
        ttk.Entry(grid, textvariable=self.t_var, width=10).grid(row=0, column=4, padx=5)
        self.t_unit = ttk.Combobox(grid, values=["°C", "°F", "K"], width=8, state="readonly")
        self.t_unit.set("°C")
        self.t_unit.grid(row=0, column=5)

        # Satır 2: Akış & Hedef
        ttk.Label(grid, text="Akış Miktarı:").grid(row=1, column=0, sticky="w", pady=5)
        self.flow_var = tk.DoubleVar()
        ttk.Entry(grid, textvariable=self.flow_var, width=10).grid(row=1, column=1, padx=5)
        self.flow_unit = ttk.Combobox(grid, values=["Sm³/h", "kg/s"], width=8, state="readonly")
        self.flow_unit.set("Sm³/h")
        self.flow_unit.grid(row=1, column=2)
        
        ttk.Label(grid, text="Hesaplama Hedefi:").grid(row=1, column=3, sticky="w", padx=(20, 5))
        self.calc_target = ttk.Combobox(grid, values=["Çıkış Basıncı", "Maksimum Uzunluk", "Minimum Çap"], width=18, state="readonly")
        self.calc_target.set("Çıkış Basıncı")
        self.calc_target.grid(row=1, column=4, columnspan=2, sticky="ew")
        self.calc_target.bind("<<ComboboxSelected>>", self.update_ui_visibility)

        # Satır 3: Termodinamik Model
        ttk.Label(grid, text="Model:").grid(row=2, column=0, sticky="w", pady=5)
        self.thermo_model = ttk.Combobox(grid, values=[
            "CoolProp (High Accuracy EOS)", "Peng-Robinson (PR EOS)", 
            "Soave-Redlich-Kwong (SRK EOS)", "Pseudo-Critical (Kay's Rule)"
        ], width=30, state="readonly")
        self.thermo_model.set("CoolProp (High Accuracy EOS)")
        self.thermo_model.grid(row=2, column=1, columnspan=3, sticky="w", padx=5)
        
        ttk.Label(grid, text="Akış Tipi:").grid(row=2, column=4, sticky="w")
        self.flow_type = ttk.Combobox(grid, values=["Sıkıştırılamaz", "Sıkıştırılabilir"], width=15, state="readonly")
        self.flow_type.set("Sıkıştırılamaz")
        self.flow_type.grid(row=2, column=5)
        self.flow_type.bind("<<ComboboxSelected>>", self.update_ui_visibility)

    def create_pipe_section(self, parent):
        self.pipe_frame = ttk.LabelFrame(parent, text="3. Boru ve Hat Özellikleri", style="Bold.TLabelframe", padding=10)
        self.pipe_frame.pack(fill="x", pady=5)
        
        # Boru Geometrisi
        geo_frame = ttk.Frame(self.pipe_frame)
        geo_frame.pack(fill="x", pady=5)
        
        ttk.Label(geo_frame, text="Malzeme:").grid(row=0, column=0, sticky="w")
        self.material_combo = ttk.Combobox(geo_frame, values=list(PIPE_MATERIALS.keys()), width=25, state="readonly")
        self.material_combo.set("API 5L Grade B")
        self.material_combo.grid(row=0, column=1, padx=5)
        
        self.lbl_len = ttk.Label(geo_frame, text="Uzunluk (m):")
        self.lbl_len.grid(row=0, column=2, padx=(15, 5))
        self.len_var = tk.DoubleVar(value=100)
        self.ent_len = ttk.Entry(geo_frame, textvariable=self.len_var, width=10)
        self.ent_len.grid(row=0, column=3)
        
        self.lbl_diam = ttk.Label(geo_frame, text="Dış Çap (mm):")
        self.lbl_diam.grid(row=1, column=0, sticky="w", pady=5)
        self.diam_var = tk.DoubleVar()
        self.ent_diam = ttk.Entry(geo_frame, textvariable=self.diam_var, width=10)
        self.ent_diam.grid(row=1, column=1, padx=5)
        
        self.lbl_thick = ttk.Label(geo_frame, text="Et Kalınlığı (mm):")
        self.lbl_thick.grid(row=1, column=2, padx=(15, 5))
        self.thick_var = tk.DoubleVar()
        self.ent_thick = ttk.Entry(geo_frame, textvariable=self.thick_var, width=10)
        self.ent_thick.grid(row=1, column=3)

        # Ekstra Hedef Girdileri (Dinamik)
        self.lbl_target_p = ttk.Label(geo_frame, text="Hedef Çıkış Basıncı:")
        self.target_p_var = tk.DoubleVar()
        self.ent_target_p = ttk.Entry(geo_frame, textvariable=self.target_p_var, width=10)
        self.target_p_unit = ttk.Combobox(geo_frame, values=["Barg", "Bara", "Psig", "Psia"], width=8, state="readonly")
        self.target_p_unit.set("Barg")
        
        self.lbl_max_vel = ttk.Label(geo_frame, text="Maks. Hız (m/s):")
        self.max_vel_var = tk.DoubleVar(value=20)
        self.ent_max_vel = ttk.Entry(geo_frame, textvariable=self.max_vel_var, width=10)

        # Tasarım Faktörleri (Min Çap için)
        design_frame = ttk.LabelFrame(self.pipe_frame, text="Tasarım Kriterleri (Min. Çap Hesabı)", padding=5)
        design_frame.pack(fill="x", pady=5)

        ttk.Label(design_frame, text="Tasarım Basıncı:").grid(row=0, column=0, sticky="w")
        self.p_design_var = tk.DoubleVar()
        ttk.Entry(design_frame, textvariable=self.p_design_var, width=10).grid(row=0, column=1, padx=5)
        self.p_design_unit = ttk.Combobox(design_frame, values=["Barg", "Bara", "Psig", "Psia"], width=8, state="readonly")
        self.p_design_unit.set("Barg")
        self.p_design_unit.grid(row=0, column=2)

        ttk.Label(design_frame, text="Faktör F:").grid(row=0, column=3, padx=(15, 5))
        self.factor_f = tk.DoubleVar(value=0.72)
        ent_f = ttk.Entry(design_frame, textvariable=self.factor_f, width=6)
        ent_f.grid(row=0, column=4)
        ToolTip(ent_f, "Dizayn Faktörü (F)\nASME B31.8'e göre:\n0.72 (Class 1)\n0.60 (Class 2)\n0.50 (Class 3)\n0.40 (Class 4)")

        ttk.Label(design_frame, text="Faktör E:").grid(row=0, column=5, padx=(15, 5))
        self.factor_e = tk.DoubleVar(value=1.0)
        ent_e = ttk.Entry(design_frame, textvariable=self.factor_e, width=6)
        ent_e.grid(row=0, column=6)
        ToolTip(ent_e, "Boyuna Ek Yeri Faktörü (E)\n1.00 (Dikişsiz/ERW)\n0.80 (Spiral Kaynaklı bazı tipler)")

        ttk.Label(design_frame, text="Faktör T:").grid(row=0, column=7, padx=(15, 5))
        self.factor_t = tk.DoubleVar(value=1.0)
        ent_t = ttk.Entry(design_frame, textvariable=self.factor_t, width=6)
        ent_t.grid(row=0, column=8)
        ToolTip(ent_t, "Sıcaklık Derating Faktörü (T)\n1.00 (<= 121°C)\n0.967 (135°C)\n0.933 (149°C)")

        # Boru Elemanları (Fittings)
        fit_frame = ttk.LabelFrame(self.pipe_frame, text="Boru Elemanları (Adet)", padding=5)
        fit_frame.pack(fill="x", pady=10)
        
        # 2 Kolonlu Fittings Düzeni
        items = list(FITTING_K_FACTORS.keys())
        half = (len(items) + 1) // 2
        
        for i, item in enumerate(items):
            col = 0 if i < half else 3
            row = i if i < half else i - half
            
            ttk.Label(fit_frame, text=item).grid(row=row, column=col, sticky="w", padx=5, pady=2)
            var = tk.IntVar(value=0)
            self.fitting_counts[item] = var
            ttk.Entry(fit_frame, textvariable=var, width=5).grid(row=row, column=col+1, padx=5)
            
            if item == "Küresel Vana (Tam Açık)":
                ttk.Label(fit_frame, text="Kv:").grid(row=row, column=col+2)
                ttk.Entry(fit_frame, textvariable=self.ball_valve_kv, width=5).grid(row=row, column=col+3)

    def create_log_tab_content(self, parent):
        self.log_text = ScrolledText(parent, state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        ttk.Button(parent, text="Logları Temizle", command=self.clear_logs).pack(anchor="e", padx=5, pady=5)

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
        
        var = tk.DoubleVar(value=0)
        self.gas_components[gas_id] = var
        
        row_frame = ttk.Frame(self.gas_list_inner)
        row_frame.pack(fill="x", pady=2)
        ttk.Label(row_frame, text=gas_name, width=25).pack(side="left")
        ttk.Entry(row_frame, textvariable=var, width=8).pack(side="left", padx=5)
        ttk.Button(row_frame, text="X", width=3, command=lambda: self.remove_gas(gas_id, row_frame)).pack(side="left")

    def remove_gas(self, gas_id, widget):
        del self.gas_components[gas_id]
        widget.destroy()

    def update_ui_visibility(self, event=None):
        target = self.calc_target.get()
        
        # Temizle
        self.lbl_len.grid_remove(); self.ent_len.grid_remove()
        self.lbl_target_p.grid_remove(); self.ent_target_p.grid_remove(); self.target_p_unit.grid_remove()
        self.lbl_max_vel.grid_remove(); self.ent_max_vel.grid_remove()
        
        if target == "Çıkış Basıncı":
            self.lbl_len.grid(row=0, column=2, padx=(15, 5)); self.ent_len.grid(row=0, column=3)
            self.pipe_frame.pack(fill="x", pady=5) # Göster
        elif target == "Maksimum Uzunluk":
            self.lbl_target_p.grid(row=0, column=2, padx=(15, 5)); self.ent_target_p.grid(row=0, column=3)
            self.target_p_unit.grid(row=0, column=4, padx=5)
            self.pipe_frame.pack(fill="x", pady=5) # Göster
        elif target == "Minimum Çap":
            self.lbl_max_vel.grid(row=0, column=2, padx=(15, 5)); self.ent_max_vel.grid(row=0, column=3)
            
            # Sıkıştırılabilir akış ise Uzunluk da gerekli (Basınç düşümü ve hız artışı hesabı için)
            if self.flow_type.get() == "Sıkıştırılabilir":
                self.lbl_len.grid(row=0, column=4, padx=(15, 5)); self.ent_len.grid(row=0, column=5)

    def log_message(self, message, level="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] [{level}] {message}\n")
        self.root.after(100, self.process_log_queue)

    def process_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg)
            self.log_text.see("end")
            self.log_text.config(state="disabled")

    def clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")

    def save_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.report_text.get(1.0, "end"))
            messagebox.showinfo("Başarılı", "Rapor kaydedildi.")

    def save_project(self):
        try:
            data = self.get_ui_state()
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo("Başarılı", "Proje kaydedildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydetme hatası: {str(e)}")

    def load_project(self):
        try:
            path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if path:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.set_ui_state(data)
                messagebox.showinfo("Başarılı", "Proje yüklendi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Yükleme hatası: {str(e)}")

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
            # UI oluşturma mantığını tekrar etmemek için add_gas_component benzeri bir işlem lazım
            # Ama burada manuel ekleyelim
            var = tk.DoubleVar(value=val)
            self.gas_components[gas_id] = var
            
            # İsim bul
            gas_name = next((v for k, v in COOLPROP_GASES.items() if k == gas_id), gas_id)
            
            row_frame = ttk.Frame(self.gas_list_inner)
            row_frame.pack(fill="x", pady=2)
            ttk.Label(row_frame, text=gas_name, width=25).pack(side="left")
            ttk.Entry(row_frame, textvariable=var, width=8).pack(side="left", padx=5)
            ttk.Button(row_frame, text="X", width=3, command=lambda gid=gas_id, w=row_frame: self.remove_gas(gid, w)).pack(side="left")

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

    # --- HESAPLAMA BAŞLATMA ---
    def start_calculation(self):
        # 1. Verileri Topla
        try:
            inputs = self.collect_inputs()
        except ValueError as e:
            messagebox.showerror("Girdi Hatası", str(e))
            return

        # 2. Arayüzü Kilitle
        self.calc_button.config(state="disabled", text="Hesaplanıyor...")
        self.report_text.delete(1.0, "end")
        self.report_text.insert("end", "Hesaplama başlatıldı...\n")

        # 3. Thread Başlat
        threading.Thread(target=self.run_calculation_thread, args=(inputs,), daemon=True).start()
        self.root.after(100, self.check_calc_queue)

    def collect_inputs(self):
        # Gaz
        if not self.gas_components: raise ValueError("En az bir gaz ekleyin.")
        total_pct = sum(v.get() for v in self.gas_components.values())
        if total_pct <= 0: raise ValueError("Gaz yüzdeleri toplamı 0 olamaz.")
        
        mole_fractions = {k: v.get()/total_pct for k, v in self.gas_components.items() if v.get() > 0}
        if self.comp_type.get() == "Kütle %":
            mole_fractions = self.calculator.mass_to_mole_fraction(mole_fractions)

        # Basınç / Sıcaklık
        p_in_val = self.p_in_var.get()
        p_unit = self.p_unit.get()
        # Birim Çevirme (Basitçe burada yapıyorum, normalde calculator'da da olabilir ama UI tarafında hazırlamak daha temiz)
        if p_unit == "Barg": P_in = (p_in_val + 1.01325) * 1e5
        elif p_unit == "Bara": P_in = p_in_val * 1e5
        elif p_unit == "Psig": P_in = (p_in_val + 14.696) * 6894.76
        else: P_in = p_in_val * 6894.76

        t_val = self.t_var.get()
        t_unit = self.t_unit.get()
        if t_unit == "°C": T = t_val + 273.15
        elif t_unit == "°F": T = (t_val - 32) * 5/9 + 273.15
        else: T = t_val

        # Boru
        # Boru (Girdiler mm, hesaplama mm bekliyor)
        D_outer = self.diam_var.get()
        t_wall = self.thick_var.get()
        D_inner = D_outer - 2 * t_wall
        if D_inner <= 0: raise ValueError("Geçersiz boru çapı/kalınlığı.")

        # Fittings K
        total_k = 0
        for name, var in self.fitting_counts.items():
            count = var.get()
            if count > 0:
                k = FITTING_K_FACTORS[name]
                # Vana Kv hesabı eklenebilir (basitlik için atlıyorum, V4'teki gibi eklenebilir)
                total_k += k * count

        return {
            "P_in": P_in, "T": T, "mole_fractions": mole_fractions,
            "library_choice": self.thermo_model.get(),
            "flow_rate": self.flow_var.get(), "flow_unit": self.flow_unit.get(),
            "D_inner": D_inner, "L": self.len_var.get(),
            "roughness": PIPE_ROUGHNESS.get(self.material_combo.get(), 4.57e-5),
            "total_k": total_k,
            "flow_property": self.flow_type.get(),
            "target": self.calc_target.get(),
            "P_out_target": self.convert_pressure_to_pa(self.target_p_var.get(), self.target_p_unit.get()) if self.calc_target.get() == "Maksimum Uzunluk" else 0,
            
            # Min Çap İçin Ekler
            "max_velocity": self.max_vel_var.get(),
            "P_design": self.convert_pressure_to_pa(self.p_design_var.get(), self.p_design_unit.get()), # Gauge Pa'ya çevrilmeli
            "material": self.material_combo.get(),
            "F": self.factor_f.get(), "E": self.factor_e.get(), "T_factor": self.factor_t.get()
        }

    def convert_pressure_to_pa(self, val, unit):
        # Basit çevirici (Gauge Pa döndürür - Tasarım basıncı genelde Gauge verilir)
        # Eğer Bara/Psia gelirse atm çıkarılır.
        if unit == "Barg": return val * 1e5
        elif unit == "Bara": return max(0, val * 1e5 - 101325)
        elif unit == "Psig": return val * 6894.76
        elif unit == "Psia": return max(0, val * 6894.76 - 101325)
        return val

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
            self.calc_button.config(state="normal", text="HESAPLA")
            
            if status == "SUCCESS":
                self.report_text.delete(1.0, "end")
                self.report_text.insert("end", data['report'])
                self.last_result = data['result'] # Sonucu sakla
                self.btn_show_graphs.config(state="normal")
                
                # Tabloyu Doldur
                self.populate_results_table(data['result'])
                self.res_notebook.select(self.tab_table) # Tabloyu göster
            else:
                messagebox.showerror("Hesaplama Hatası", data)
                self.report_text.insert("end", f"\nHATA: {data}")
                self.btn_show_graphs.config(state="disabled")
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
        canvas = self.schematic_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 100 or h < 100: return
        
        target = self.calc_target.get()
        
        # Koordinatlar
        mid_y = h / 2
        margin_x = 80
        pipe_start_x = margin_x
        pipe_end_x = w - margin_x
        pipe_width = pipe_end_x - pipe_start_x
        
        # Renkler
        pipe_fill = "#e3f2fd" # Açık mavi
        pipe_outline = "#1565c0" # Koyu mavi
        text_color = "#37474f"
        highlight_color = "#d32f2f" # Kırmızı (Bilinmeyenler için)
        
        # --- BORU ÇİZİMİ ---
        # Max Uzunluk ise borunun sonu "kesik" veya "belirsiz" görünsün
        if target == "Maksimum Uzunluk":
            # Boru gövdesi (Sağ taraf açık gibi)
            canvas.create_rectangle(pipe_start_x, mid_y - 20, pipe_end_x - 20, mid_y + 20, fill=pipe_fill, outline=pipe_outline)
            # Kesik çizgi efekti
            canvas.create_line(pipe_end_x - 20, mid_y - 20, pipe_end_x, mid_y, fill=pipe_outline, dash=(4, 2))
            canvas.create_line(pipe_end_x - 20, mid_y + 20, pipe_end_x, mid_y, fill=pipe_outline, dash=(4, 2))
        else:
            # Standart Boru
            canvas.create_rectangle(pipe_start_x, mid_y - 20, pipe_end_x, mid_y + 20, fill=pipe_fill, outline=pipe_outline)

        # --- AKIŞ OKLARI ---
        # Giriş
        canvas.create_line(20, mid_y, pipe_start_x, mid_y, arrow=tk.LAST, width=3, fill="#4caf50")
        canvas.create_text(40, mid_y - 15, text="GİRİŞ", font=("Segoe UI", 8, "bold"), fill="#2e7d32")
        
        # Çıkış
        canvas.create_line(pipe_end_x, mid_y, w - 20, mid_y, arrow=tk.LAST, width=3, fill="#4caf50")
        canvas.create_text(w - 40, mid_y - 15, text="ÇIKIŞ", font=("Segoe UI", 8, "bold"), fill="#2e7d32")

        # --- BİLGİ ETİKETLERİ ---
        try:
            # Giriş Bilgileri (Sol Üst/Alt)
            p_in_txt = f"P_in: {self.p_in_var.get()} {self.p_unit.get()}"
            t_txt = f"T: {self.t_var.get()} {self.t_unit.get()}"
            flow_txt = f"Q: {self.flow_var.get()} {self.flow_unit.get()}"
            
            canvas.create_text(pipe_start_x, mid_y - 40, text=p_in_txt, anchor="sw", font=("Consolas", 9), fill=text_color)
            canvas.create_text(pipe_start_x, mid_y + 35, text=t_txt, anchor="nw", font=("Consolas", 9), fill=text_color)
            canvas.create_text(pipe_start_x, mid_y + 50, text=flow_txt, anchor="nw", font=("Consolas", 9), fill=text_color)

            # --- HEDEFE GÖRE GÖSTERİM ---
            
            # 1. UZUNLUK (L)
            if target == "Maksimum Uzunluk":
                # L = ?
                canvas.create_line(pipe_start_x, mid_y + 80, pipe_end_x, mid_y + 80, arrow=tk.BOTH, fill=highlight_color, width=2)
                canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 75, text="L = ???", font=("Segoe UI", 10, "bold"), fill=highlight_color, anchor="s")
                
                # P_out Hedef
                p_out_txt = f"P_out (Hedef): {self.target_p_var.get()} {self.target_p_unit.get()}"
                canvas.create_text(pipe_end_x, mid_y - 40, text=p_out_txt, anchor="se", font=("Consolas", 9, "bold"), fill="#1976d2")
                
            else:
                # L Biliniyor
                L_val = self.len_var.get()
                canvas.create_line(pipe_start_x, mid_y + 80, pipe_end_x, mid_y + 80, arrow=tk.BOTH, fill=text_color)
                canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y + 75, text=f"L = {L_val} m", font=("Segoe UI", 9), fill=text_color, anchor="s")

            # 2. ÇAP (D)
            if target == "Minimum Çap":
                # D = ?
                canvas.create_line(pipe_end_x + 10, mid_y - 20, pipe_end_x + 10, mid_y + 20, arrow=tk.BOTH, fill=highlight_color, width=2)
                canvas.create_text(pipe_end_x + 15, mid_y, text="D = ?", font=("Segoe UI", 10, "bold"), fill=highlight_color, anchor="w")
                
                # Hız Limiti
                v_txt = f"V_max: {self.max_vel_var.get()} m/s"
                canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y, text=v_txt, font=("Segoe UI", 9, "bold"), fill="#d32f2f")
            else:
                # D Biliniyor
                D_val = self.diam_var.get()
                canvas.create_text((pipe_start_x + pipe_end_x)/2, mid_y, text=f"D = {D_val} mm", font=("Segoe UI", 9), fill=text_color)

            # 3. ÇIKIŞ BASINCI (P_out)
            if target == "Çıkış Basıncı":
                # P_out = ?
                canvas.create_text(pipe_end_x, mid_y - 40, text="P_out = ???", anchor="se", font=("Segoe UI", 10, "bold"), fill=highlight_color)
            elif target != "Maksimum Uzunluk": # Min Çap veya diğerleri
                # P_out hesabı sonucunda çıkacak ama hedef değil
                 pass

            # Fittings Sayısı
            total_fit = sum(v.get() for v in self.fitting_counts.values())
            if total_fit > 0:
                canvas.create_oval(pipe_start_x + 40, mid_y - 15, pipe_start_x + 50, mid_y - 5, fill="orange", outline="orange")
                canvas.create_text(pipe_start_x + 55, mid_y - 10, text=f"{total_fit} Fittings", anchor="w", font=("Segoe UI", 7), fill="orange")

        except Exception as e:
            canvas.create_text(w/2, h/2, text=f"Çizim Hatası: {str(e)}", fill="red")

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

if __name__ == "__main__":
    root = tk.Tk()
    app = GasFlowCalculatorApp(root)
    root.mainloop()
