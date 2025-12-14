"""
FireHydra - Ana Uygulama
========================

Ana uygulama penceresi ve tüm modüllerin entegrasyonu.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
from typing import Optional

from models import PipeNetwork, Node, Pipe, NodeType, Coordinates, Fitting, FittingCategory, ProjectSettings
from database import DatabaseManager
from engine import HydraulicEngine
from solver import HydraulicSolver
from pump_tank import PumpAndTankModule, FirePump
from gui_canvas import FireHydraCanvas, DrawingTool
from report import ReportGenerator, ReportSettings
from dialogs import (PumpSelectionDialog, TankCalculationDialog, PipeCatalogDialog, 
                      FittingTableDialog, ProjectSettingsDialog, BatchSprinklerDialog,
                      DiameterOptimizationDialog, ReportTemplateDialog, DXFImportDialog)
from validator import NetworkValidator, ValidationLevel
from dashboard import NetworkDashboard, DashboardPosition, NetworkStats, calculate_network_stats
from pressure_zones import PressureZoneManager, PressureZone, PressureZoneDialog, PressureZonePanel
from material_cost import MaterialDatabase, MaterialCostPanel, MaterialEditDialog, calculate_project_cost
from view_3d import View3DWindow
from advanced_solver import show_solver_comparison
from network_templates import NetworkTemplateDialog
from cad_export import show_cad_export_dialog
from water_hammer import show_water_hammer_analysis


class FireHydraApp(tk.Tk):
    """
    FireHydra Ana Uygulama Sınıfı
    
    Tüm modülleri bir araya getiren ana pencere.
    """
    
    APP_TITLE = "FireHydra - Yangın Hidrolik Hesaplama v1.0"
    
    def __init__(self):
        super().__init__()
        
        # Pencere ayarları
        self.title(self.APP_TITLE)
        self.geometry("1400x900")
        self.minsize(1000, 700)
        
        # Veri modelleri
        self.network = PipeNetwork("Yeni Proje")
        self.db = DatabaseManager("firehydra.db")
        self.pump_module = PumpAndTankModule()
        self.project_settings = ProjectSettings()  # Proje ayarları
        self.zone_manager = PressureZoneManager()  # Basınç bölgeleri
        self.material_db = MaterialDatabase("materials.db")  # Malzeme veritabanı
        
        # Proje durumu
        self.current_file: Optional[str] = None
        self.is_modified = False
        
        # Dashboard
        self.dashboard: Optional[NetworkDashboard] = None
        self.dashboard_visible = True
        
        # Hesaplama sonuçları (CAD export için)
        self.last_calc_results: Optional[str] = None
        
        # GUI oluştur
        self._create_menu()
        self._create_toolbar()
        self._create_main_layout()
        self._create_statusbar()
        
        # Olay bağlantıları
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-n>", lambda e: self._new_project())
        self.bind("<Control-o>", lambda e: self._open_project())
        self.bind("<Control-s>", lambda e: self._save_project())
        self.bind("<Control-Shift-s>", lambda e: self._save_project_as())
        self.bind("<Control-r>", lambda e: self._show_report_dialog())
        self.bind("<Control-e>", lambda e: self._show_cad_export())
        self.bind("<F11>", lambda e: self._show_3d_view())
        self.bind("<F12>", lambda e: self._toggle_dashboard())
        
        # Durum güncelle
        self._update_status("Hazır")
    
    def _create_menu(self):
        """Menü çubuğu oluştur"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # Dosya menüsü
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Dosya", menu=file_menu)
        file_menu.add_command(label="Yeni Proje", command=self._new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Aç...", command=self._open_project, accelerator="Ctrl+O")
        file_menu.add_command(label="Kaydet", command=self._save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Farklı Kaydet...", command=self._save_project_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="CAD Export (DXF/PDF)...", command=self._show_cad_export, accelerator="Ctrl+E")
        file_menu.add_command(label="Rapor Ayarları ve Dışa Aktar...", command=self._show_report_dialog, accelerator="Ctrl+R")
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self._on_close)
        
        # Düzen menüsü
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Düzen", menu=edit_menu)
        edit_menu.add_command(label="Geri Al", command=self._undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Yinele", command=self._redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Seçimi Sil", command=self._delete_selection, accelerator="Delete")
        edit_menu.add_separator()
        edit_menu.add_command(label="Tümünü Seç", command=self._select_all)
        edit_menu.add_command(label="Seçimi Temizle", command=self._clear_selection, accelerator="Esc")
        
        # Görünüm menüsü
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Görünüm", menu=view_menu)
        view_menu.add_command(label="Sığdır", command=self._fit_to_view)
        view_menu.add_command(label="Zoom 100%", command=self._zoom_100)
        view_menu.add_separator()
        view_menu.add_command(label="Grid Göster/Gizle", command=self._toggle_grid)
        view_menu.add_separator()
        view_menu.add_command(label="3D Görünüm...", command=self._show_3d_view, accelerator="F11")
        view_menu.add_separator()
        view_menu.add_command(label="Dashboard Göster/Gizle", command=self._toggle_dashboard, accelerator="F12")
        
        # Hesaplama menüsü
        calc_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Hesaplama", menu=calc_menu)
        calc_menu.add_command(label="Hidrolik Hesapla", command=self._run_calculation, accelerator="F5")
        calc_menu.add_separator()
        calc_menu.add_command(label="Solver Karşılaştırma...", command=self._show_solver_comparison)
        calc_menu.add_separator()
        calc_menu.add_command(label="Tasarım Parametreleri...", command=self._show_design_params)
        calc_menu.add_command(label="Pompa Seçimi...", command=self._show_pump_selection)
        calc_menu.add_command(label="Su Deposu Hesabı...", command=self._show_tank_calculation)
        calc_menu.add_separator()
        calc_menu.add_command(label="Su Darbesi Analizi...", command=self._show_water_hammer_analysis)
        
        # Ekle menüsü
        add_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ekle", menu=add_menu)
        add_menu.add_command(label="Toplu Sprinkler...", command=self._add_batch_sprinklers)
        add_menu.add_command(label="Network Şablonu...", command=self._add_network_template)
        add_menu.add_separator()
        add_menu.add_command(label="DXF İçe Aktar...", command=self._import_dxf)
        
        # Araçlar menüsü
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Araçlar", menu=tools_menu)
        tools_menu.add_command(label="Proje Ayarları...", command=self._show_project_settings)
        tools_menu.add_separator()
        tools_menu.add_command(label="Pompa Seçimi...", command=self._show_pump_selection)
        tools_menu.add_command(label="Su Deposu Hesabı...", command=self._show_tank_calculation)
        tools_menu.add_command(label="Boru Çapı Optimizasyonu...", command=self._show_diameter_optimization)
        tools_menu.add_separator()
        tools_menu.add_command(label="Basınç Bölgeleri...", command=self._show_pressure_zones)
        tools_menu.add_command(label="Malzeme ve Maliyet...", command=self._show_material_cost)
        tools_menu.add_separator()
        tools_menu.add_command(label="DXF/DWG İçe Aktar...", command=self._import_dxf)
        tools_menu.add_separator()
        tools_menu.add_command(label="Veritabanı Yöneticisi...", command=self._show_db_manager)
        tools_menu.add_command(label="Boru Çapları...", command=self._show_pipe_catalog)
        tools_menu.add_command(label="Fitting Tablosu...", command=self._show_fitting_table)
        
        # Yardım menüsü
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Yardım", menu=help_menu)
        help_menu.add_command(label="Kullanım Kılavuzu", command=self._show_help)
        help_menu.add_command(label="Formüller", command=self._show_formulas)
        help_menu.add_separator()
        help_menu.add_command(label="Hakkında...", command=self._show_about)
        
        # Klavye kısayolu
        self.bind("<F5>", lambda e: self._run_calculation())
    
    def _create_toolbar(self):
        """Araç çubuğu oluştur"""
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        # Dosya butonları
        ttk.Button(toolbar, text="Yeni", command=self._new_project, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Aç", command=self._open_project, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Kaydet", command=self._save_project, width=6).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Çizim araçları
        self.tool_var = tk.StringVar(value=DrawingTool.SELECT)
        
        ttk.Label(toolbar, text="Araç:").pack(side=tk.LEFT, padx=5)
        
        tools = [
            ("Seç", DrawingTool.SELECT),
            ("Kaydır", DrawingTool.PAN),
            ("Boru", DrawingTool.PIPE),
            ("Sprinkler", DrawingTool.SPRINKLER),
            ("Kaynak", DrawingTool.SOURCE),
        ]
        
        for label, tool in tools:
            rb = ttk.Radiobutton(
                toolbar, text=label, value=tool,
                variable=self.tool_var,
                command=self._on_tool_change
            )
            rb.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Boru çapı seçimi
        ttk.Label(toolbar, text="Çap:").pack(side=tk.LEFT, padx=5)
        
        self.diameter_var = tk.StringVar(value="50")
        diameter_combo = ttk.Combobox(
            toolbar, textvariable=self.diameter_var,
            values=["25", "32", "40", "50", "65", "80", "100", "125", "150"],
            width=5
        )
        diameter_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="mm").pack(side=tk.LEFT)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Hesapla butonu
        calc_btn = ttk.Button(toolbar, text="⚡ HESAPLA", command=self._run_calculation, width=12)
        calc_btn.pack(side=tk.LEFT, padx=10)
    
    def _create_main_layout(self):
        """Ana düzen oluştur"""
        # Ana panel (PanedWindow)
        self.main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Sol panel - Canvas
        canvas_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(canvas_frame, weight=3)
        
        self.canvas = FireHydraCanvas(canvas_frame, self.network, bg='#2B2B2B')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Orta panel - Özellikler ve sonuçlar
        right_paned = ttk.PanedWindow(self.main_paned, orient=tk.VERTICAL)
        self.main_paned.add(right_paned, weight=1)
        
        # Proje bilgileri
        project_frame = ttk.LabelFrame(right_paned, text="Proje Bilgileri", padding=5)
        right_paned.add(project_frame, weight=1)
        
        self._create_project_panel(project_frame)
        
        # Hesaplama sonuçları
        results_frame = ttk.LabelFrame(right_paned, text="Hesaplama Sonuçları", padding=5)
        right_paned.add(results_frame, weight=2)
        
        self._create_results_panel(results_frame)
        
        # Dashboard (sağ panel)
        self.dashboard = NetworkDashboard(self.main_paned, DashboardPosition.RIGHT)
        self.dashboard.bind('<<DashboardRefresh>>', lambda e: self._refresh_dashboard())
        self.main_paned.add(self.dashboard, weight=1)
    
    def _create_project_panel(self, parent):
        """Proje bilgileri paneli"""
        # Proje adı
        ttk.Label(parent, text="Proje Adı:").grid(row=0, column=0, sticky="w", pady=2)
        self.project_name_var = tk.StringVar(value=self.network.name)
        ttk.Entry(parent, textvariable=self.project_name_var, width=25).grid(row=0, column=1, pady=2)
        
        # Tehlike sınıfı
        ttk.Label(parent, text="Tehlike Sınıfı:").grid(row=1, column=0, sticky="w", pady=2)
        self.hazard_var = tk.StringVar(value="OH2")
        hazard_combo = ttk.Combobox(
            parent, textvariable=self.hazard_var,
            values=["LH", "OH1", "OH2", "HHP", "HHS", "BYKHY_KONUT", "BYKHY_OFIS", "BYKHY_TICARI", "BYKHY_ENDUSTRI"],
            width=15
        )
        hazard_combo.grid(row=1, column=1, sticky="w", pady=2)
        
        # Tasarım yoğunluğu
        ttk.Label(parent, text="Yoğunluk (mm/dk):").grid(row=2, column=0, sticky="w", pady=2)
        self.density_var = tk.DoubleVar(value=5.0)
        ttk.Entry(parent, textvariable=self.density_var, width=10).grid(row=2, column=1, sticky="w", pady=2)
        
        # Tasarım alanı
        ttk.Label(parent, text="Alan (m²):").grid(row=3, column=0, sticky="w", pady=2)
        self.area_var = tk.DoubleVar(value=150.0)
        ttk.Entry(parent, textvariable=self.area_var, width=10).grid(row=3, column=1, sticky="w", pady=2)
        
        # İstatistikler
        ttk.Separator(parent, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Label(parent, text="Düğüm Sayısı:").grid(row=5, column=0, sticky="w", pady=2)
        self.node_count_var = tk.StringVar(value="0")
        ttk.Label(parent, textvariable=self.node_count_var).grid(row=5, column=1, sticky="w", pady=2)
        
        ttk.Label(parent, text="Boru Sayısı:").grid(row=6, column=0, sticky="w", pady=2)
        self.pipe_count_var = tk.StringVar(value="0")
        ttk.Label(parent, textvariable=self.pipe_count_var).grid(row=6, column=1, sticky="w", pady=2)
        
        ttk.Label(parent, text="Sprinkler Sayısı:").grid(row=7, column=0, sticky="w", pady=2)
        self.sprinkler_count_var = tk.StringVar(value="0")
        ttk.Label(parent, textvariable=self.sprinkler_count_var).grid(row=7, column=1, sticky="w", pady=2)
    
    def _create_results_panel(self, parent):
        """Hesaplama sonuçları paneli (Notebook ile)"""
        # Notebook oluştur
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Sonuçlar
        results_tab = ttk.Frame(notebook, padding=5)
        notebook.add(results_tab, text="Sonuçlar")
        self._create_results_tab(results_tab)
        
        # Tab 2: Doğrulama
        validation_tab = ttk.Frame(notebook, padding=5)
        notebook.add(validation_tab, text="Doğrulama")
        self._create_validation_tab(validation_tab)
    
    def _create_results_tab(self, parent):
        """Sonuçlar sekmesi"""
        # Sistem sonuçları
        ttk.Label(parent, text="Toplam Debi:").grid(row=0, column=0, sticky="w", pady=2)
        self.total_flow_var = tk.StringVar(value="- L/dk")
        ttk.Label(parent, textvariable=self.total_flow_var, font=("Arial", 11, "bold")).grid(row=0, column=1, sticky="w", pady=2)
        
        ttk.Label(parent, text="Toplam Basınç:").grid(row=1, column=0, sticky="w", pady=2)
        self.total_pressure_var = tk.StringVar(value="- Bar")
        ttk.Label(parent, textvariable=self.total_pressure_var, font=("Arial", 11, "bold")).grid(row=1, column=1, sticky="w", pady=2)
        
        ttk.Label(parent, text="Maks. Hız:").grid(row=2, column=0, sticky="w", pady=2)
        self.max_velocity_var = tk.StringVar(value="- m/s")
        ttk.Label(parent, textvariable=self.max_velocity_var).grid(row=2, column=1, sticky="w", pady=2)
        
        # Sonuç tablosu
        ttk.Separator(parent, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        
        # Treeview
        columns = ("node", "type", "pressure", "flow")
        self.results_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        
        self.results_tree.heading("node", text="Düğüm")
        self.results_tree.heading("type", text="Tip")
        self.results_tree.heading("pressure", text="Basınç (bar)")
        self.results_tree.heading("flow", text="Debi (L/dk)")
        
        self.results_tree.column("node", width=80)
        self.results_tree.column("type", width=80)
        self.results_tree.column("pressure", width=80)
        self.results_tree.column("flow", width=80)
        
        self.results_tree.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=4, column=2, sticky="ns")
        
        parent.rowconfigure(4, weight=1)
        parent.columnconfigure(1, weight=1)
    
    def _create_validation_tab(self, parent):
        """Doğrulama sekmesi"""
        # Özet bilgisi
        summary_frame = ttk.Frame(parent)
        summary_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.validation_summary_var = tk.StringVar(value="Doğrulama yapılmadı")
        ttk.Label(summary_frame, textvariable=self.validation_summary_var, 
                 font=("Arial", 9, "bold")).pack(anchor="w")
        
        # Doğrulama butonu
        ttk.Button(summary_frame, text="Doğrula", 
                  command=self._run_validation).pack(anchor="w", pady=5)
        
        # Sorunlar listesi
        ttk.Label(parent, text="Sorunlar:").pack(anchor="w", pady=(5,2))
        
        # Treeview
        columns = ("level", "category", "message")
        self.validation_tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)
        
        self.validation_tree.heading("level", text="Seviye")
        self.validation_tree.heading("category", text="Kategori")
        self.validation_tree.heading("message", text="Mesaj")
        
        self.validation_tree.column("level", width=80)
        self.validation_tree.column("category", width=90)
        self.validation_tree.column("message", width=250)
        
        self.validation_tree.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.validation_tree.yview)
        self.validation_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Renk etiketleri
        self.validation_tree.tag_configure("critical", foreground="red", font=("Arial", 9, "bold"))
        self.validation_tree.tag_configure("error", foreground="red")
        self.validation_tree.tag_configure("warning", foreground="orange")
        self.validation_tree.tag_configure("info", foreground="blue")
        
        # Detay gösterme
        self.validation_tree.bind("<Double-1>", self._on_validation_double_click)
    
    def _create_statusbar(self):
        """Durum çubuğu oluştur"""
        self.statusbar = ttk.Frame(self)
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(self.statusbar, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)
        
        self.coords_var = tk.StringVar(value="X: 0  Y: 0  Z: 0")
        ttk.Label(self.statusbar, textvariable=self.coords_var).pack(side=tk.RIGHT, padx=10)
    
    def _update_status(self, message: str):
        """Durum çubuğunu güncelle"""
        self.status_var.set(message)
    
    def _update_statistics(self):
        """İstatistikleri güncelle"""
        stats = self.network.get_statistics()
        self.node_count_var.set(str(stats['total_nodes']))
        self.pipe_count_var.set(str(stats['total_pipes']))
        self.sprinkler_count_var.set(str(stats['total_sprinklers']))
    
    def _on_tool_change(self):
        """Araç değişikliği"""
        tool = self.tool_var.get()
        self.canvas.set_tool(tool)
    
    def _on_close(self):
        """Pencere kapatma"""
        if self.is_modified:
            result = messagebox.askyesnocancel(
                "Kaydet?",
                "Değişiklikler kaydedilmedi. Kaydetmek ister misiniz?"
            )
            if result is True:
                self._save_project()
            elif result is None:
                return
        
        self.db.close()
        self.destroy()
    
    # ==================== Dosya İşlemleri ====================
    
    def _new_project(self):
        """Yeni proje"""
        if self.is_modified:
            result = messagebox.askyesnocancel(
                "Kaydet?",
                "Değişiklikler kaydedilmedi. Kaydetmek ister misiniz?"
            )
            if result is True:
                self._save_project()
            elif result is None:
                return
        
        self.network = PipeNetwork("Yeni Proje")
        self.canvas.network = self.network
        self.current_file = None
        self.is_modified = False
        
        self.project_name_var.set("Yeni Proje")
        self._update_statistics()
        self._clear_results()
        self.canvas.redraw()
        
        self.title(self.APP_TITLE)
        self._update_status("Yeni proje oluşturuldu")
    
    def _open_project(self):
        """Proje aç"""
        filepath = filedialog.askopenfilename(
            title="Proje Aç",
            filetypes=[("FireHydra Projesi", "*.fhp"), ("JSON", "*.json"), ("Tümü", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Proje yükle
            self._load_project_data(data)
            
            self.current_file = filepath
            self.is_modified = False
            
            self.title(f"{self.APP_TITLE} - {os.path.basename(filepath)}")
            self._update_status(f"Proje yüklendi: {filepath}")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Proje yüklenemedi:\n{e}")
    
    def _save_project(self):
        """Projeyi kaydet"""
        if not self.current_file:
            self._save_project_as()
            return
        
        self._save_to_file(self.current_file)
    
    def _save_project_as(self):
        """Projeyi farklı kaydet"""
        filepath = filedialog.asksaveasfilename(
            title="Projeyi Kaydet",
            defaultextension=".fhp",
            filetypes=[("FireHydra Projesi", "*.fhp"), ("JSON", "*.json")]
        )
        
        if filepath:
            self._save_to_file(filepath)
            self.current_file = filepath
            self.title(f"{self.APP_TITLE} - {os.path.basename(filepath)}")
    
    def _save_to_file(self, filepath: str):
        """Dosyaya kaydet"""
        try:
            data = self._get_project_data()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.is_modified = False
            self._update_status(f"Proje kaydedildi: {filepath}")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydetme hatası:\n{e}")
    
    def _get_project_data(self) -> dict:
        """Proje verilerini sözlük olarak al"""
        nodes_data = []
        for node in self.network.nodes.values():
            nodes_data.append({
                "id": node.id,
                "type": node.node_type.value,
                "x": node.coordinates.x,
                "y": node.coordinates.y,
                "z": node.coordinates.z,
                "k_factor": node.k_factor,
                "min_pressure": node.min_pressure_required,
                "coverage_area": node.coverage_area,
            })
        
        pipes_data = []
        for pipe in self.network.pipes.values():
            fittings = [{"category": f.category.value, "eq_length": f.equivalent_length} 
                       for f in pipe.fittings]
            
            pipes_data.append({
                "id": pipe.id,
                "start_node": pipe.start_node_id,
                "end_node": pipe.end_node_id,
                "length": pipe.length,
                "diameter": pipe.internal_diameter,
                "nominal": pipe.nominal_diameter,
                "c_factor": pipe.c_factor,
                "material": pipe.material,
                "fittings": fittings,
            })
        
        return {
            "version": "1.0",
            "project_name": self.project_name_var.get(),
            "hazard_class": self.hazard_var.get(),
            "density": self.density_var.get(),
            "area": self.area_var.get(),
            "nodes": nodes_data,
            "pipes": pipes_data,
        }
    
    def _load_project_data(self, data: dict):
        """Proje verilerini yükle"""
        self.network = PipeNetwork(data.get("project_name", "Yüklenen Proje"))
        
        # Düğümleri yükle
        for node_data in data.get("nodes", []):
            node = Node(
                id=node_data["id"],
                node_type=NodeType(node_data["type"]),
                coordinates=Coordinates(
                    node_data["x"],
                    node_data["y"],
                    node_data.get("z", 0)
                ),
                k_factor=node_data.get("k_factor", 80),
                min_pressure_required=node_data.get("min_pressure", 0.5),
                coverage_area=node_data.get("coverage_area", 12),
            )
            self.network.add_node(node)
        
        # Boruları yükle
        for pipe_data in data.get("pipes", []):
            pipe = Pipe(
                id=pipe_data["id"],
                start_node_id=pipe_data["start_node"],
                end_node_id=pipe_data["end_node"],
                length=pipe_data["length"],
                internal_diameter=pipe_data["diameter"],
                nominal_diameter=pipe_data.get("nominal", pipe_data["diameter"]),
                c_factor=pipe_data.get("c_factor", 120),
                material=pipe_data.get("material", "Steel"),
            )
            
            for fitting_data in pipe_data.get("fittings", []):
                fitting = Fitting(
                    category=FittingCategory(fitting_data["category"]),
                    equivalent_length=fitting_data["eq_length"]
                )
                pipe.add_fitting(fitting)
            
            self.network.add_pipe(pipe)
        
        # Parametreleri yükle
        self.project_name_var.set(data.get("project_name", ""))
        self.hazard_var.set(data.get("hazard_class", "OH2"))
        self.density_var.set(data.get("density", 5.0))
        self.area_var.set(data.get("area", 150.0))
        
        self.canvas.network = self.network
        self._update_statistics()
        self.canvas.redraw()
    
    # ==================== Hesaplama ====================
    
    def _run_calculation(self):
        """Hidrolik hesaplama çalıştır"""
        self._update_status("Hesaplama yapılıyor...")
        self.update()
        
        try:
            solver = HydraulicSolver(self.network, self.db)
            solver.set_design_parameters(
                density=self.density_var.get(),
                operating_area=self.area_var.get()
            )
            
            result = solver.solve()
            
            if result.success:
                # Sonuçları sakla (CAD export için)
                self.last_calc_results = self._format_results_text(result)
                
                # Sonuçları göster
                self.total_flow_var.set(f"{result.total_flow:.1f} L/dk")
                self.total_pressure_var.set(f"{result.total_pressure:.2f} Bar")
                self.max_velocity_var.set(f"{result.max_velocity:.2f} m/s")
                
                # Tablo güncelle
                self._update_results_table()
                
                # Canvas güncelle
                self.canvas.redraw()
                
                # Otomatik doğrulama yap
                self._run_validation()
                
                # Dashboard'u güncelle
                self._refresh_dashboard()
                
                self._update_status("Hesaplama tamamlandı")
                
                # Uyarılar
                if result.warnings:
                    warning_text = "\n".join(result.warnings)
                    messagebox.showwarning("Uyarılar", warning_text)
            else:
                messagebox.showerror("Hesaplama Hatası", result.error_message)
                self._update_status("Hesaplama başarısız")
                
        except Exception as e:
            messagebox.showerror("Hata", f"Hesaplama hatası:\n{e}")
            self._update_status("Hata oluştu")
    
    def _update_results_table(self):
        """Sonuç tablosunu güncelle"""
        # Eski verileri temizle
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Yeni verileri ekle
        for node in self.network.nodes.values():
            if node.is_calculated:
                self.results_tree.insert("", "end", values=(
                    node.id,
                    node.node_type.value,
                    f"{node.pressure:.3f}" if node.pressure else "-",
                    f"{node.total_flow:.1f}" if node.total_flow else "-"
                ))
    
    def _clear_results(self):
        """Sonuçları temizle"""
        self.total_flow_var.set("- L/dk")
        self.total_pressure_var.set("- Bar")
        self.max_velocity_var.set("- m/s")
        
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
    
    # ==================== Doğrulama ====================
    
    def _run_validation(self):
        """Ağ doğrulaması yap"""
        self._update_status("Doğrulama yapılıyor...")
        self.update()
        
        try:
            validator = NetworkValidator(self.network, self.project_settings)
            issues = validator.validate_all()
            
            # Özet güncelle
            summary = validator.get_summary()
            summary_text = f"Toplam: {summary['total']} sorun | "
            summary_text += f"Kritik: {summary['critical']} | "
            summary_text += f"Hata: {summary['error']} | "
            summary_text += f"Uyarı: {summary['warning']} | "
            summary_text += f"Bilgi: {summary['info']}"
            self.validation_summary_var.set(summary_text)
            
            # Tabloyu temizle
            for item in self.validation_tree.get_children():
                self.validation_tree.delete(item)
            
            # Sorunları ekle
            for issue in issues:
                level_str = issue.level.value.upper()
                tag = issue.level.value
                
                self.validation_tree.insert("", "end", 
                    values=(level_str, issue.category, issue.message),
                    tags=(tag,))
            
            self._update_status(f"Doğrulama tamamlandı - {summary['total']} sorun bulundu")
            
            # Kritik sorun varsa uyar
            if validator.has_critical_issues():
                messagebox.showwarning("Kritik Sorunlar", 
                    f"{summary['critical']} kritik sorun bulundu!\nDetaylar için Doğrulama sekmesine bakın.")
        
        except Exception as e:
            messagebox.showerror("Hata", f"Doğrulama hatası:\n{e}")
            self._update_status("Doğrulama başarısız")
    
    def _on_validation_double_click(self, event):
        """Doğrulama sorununa çift tıklama"""
        selection = self.validation_tree.selection()
        if not selection:
            return
        
        item = self.validation_tree.item(selection[0])
        values = item['values']
        
        if len(values) >= 3:
            category = values[1]
            message = values[2]
            
            # Detay göster
            messagebox.showinfo(f"{category} Sorunu", message)
    
    # ==================== Rapor ====================
    
    def _format_results_text(self, result) -> str:
        """Hesaplama sonuçlarını metin formatına çevir"""
        lines = []
        lines.append("=" * 60)
        lines.append("HİDROLİK HESAPLAMA SONUÇLARI")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Toplam Debi: {result.total_flow:.1f} L/dk")
        lines.append(f"Toplam Basınç: {result.total_pressure:.2f} Bar")
        lines.append(f"Maksimum Hız: {result.max_velocity:.2f} m/s")
        lines.append("")
        
        if hasattr(result, 'warnings') and result.warnings:
            lines.append("UYARILAR:")
            for warning in result.warnings:
                lines.append(f"- {warning}")
            lines.append("")
        
        lines.append("BORU SONUÇLARI:")
        lines.append("-" * 60)
        for pipe in self.network.pipes:
            if hasattr(pipe, 'flow') and pipe.flow:
                lines.append(f"{pipe.id}: Debi={pipe.flow:.1f} L/dk, Hız={pipe.velocity:.2f} m/s")
        
        return "\n".join(lines)
    
    def _show_report_dialog(self):
        """Rapor ayarları dialogunu göster ve rapor oluştur"""
        if not self.solver or not self.solver.is_calculated:
            messagebox.showwarning("Uyarı", "Önce hidrolik hesaplama yapmalısınız!")
            return
        
        # Mevcut rapor ayarlarını al (varsa)
        if not hasattr(self, 'report_settings'):
            self.report_settings = ReportSettings(
                project_name=self.network.project_name,
                project_number="",
                client_name="",
                engineer_name=""
            )
        
        # Dialog aç
        dialog = ReportTemplateDialog(self, self.report_settings)
        self.wait_window(dialog)
        
        # Dialog sonucunu kontrol et
        if dialog.result:
            self.report_settings = dialog.result
            
            # Format tipine göre dosya kaydetme dialogunu aç
            if hasattr(self.report_settings, 'format_type'):
                if self.report_settings.format_type == "pdf":
                    self._export_pdf_with_settings(self.report_settings)
                elif self.report_settings.format_type == "excel":
                    self._export_excel_with_settings(self.report_settings)
    
    def _export_pdf_with_settings(self, settings: ReportSettings):
        """Ayarlarla PDF rapor oluştur"""
        filepath = filedialog.asksaveasfilename(
            title="PDF Rapor Kaydet",
            defaultextension=".pdf",
            filetypes=[("PDF Dosyaları", "*.pdf"), ("Tüm Dosyalar", "*.*")]
        )
        
        if filepath:
            generator = ReportGenerator(self.network, self.solver.get_result(), settings)
            
            if generator.generate_pdf(filepath):
                messagebox.showinfo("Başarılı", f"PDF rapor oluşturuldu:\n{filepath}")
                
                # Dosyayı aç
                if messagebox.askyesno("Aç", "Raporu açmak ister misiniz?"):
                    os.startfile(filepath)
            else:
                messagebox.showerror("Hata", "PDF oluşturulurken hata oluştu!")
    
    def _export_excel_with_settings(self, settings: ReportSettings):
        """Ayarlarla Excel rapor oluştur"""
        filepath = filedialog.asksaveasfilename(
            title="Excel Rapor Kaydet",
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyaları", "*.xlsx"), ("Tüm Dosyalar", "*.*")]
        )
        
        if filepath:
            generator = ReportGenerator(self.network, self.solver.get_result(), settings)
            
            if generator.generate_excel(filepath):
                messagebox.showinfo("Başarılı", f"Excel rapor oluşturuldu:\n{filepath}")
                
                # Dosyayı aç
                if messagebox.askyesno("Aç", "Raporu açmak ister misiniz?"):
                    os.startfile(filepath)
            else:
                messagebox.showerror("Hata", "Excel oluşturulurken hata oluştu!")

    def _export_pdf(self):
        """PDF rapor oluştur"""
        if not self.network.is_calculated:
            messagebox.showwarning("Uyarı", "Önce hesaplama yapın!")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="PDF Rapor Kaydet",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        
        if filepath:
            settings = ReportSettings(
                project_name=self.project_name_var.get(),
                standard="NFPA 13 / TS EN 12845"
            )
            
            # Sonuç objesi oluştur
            from .solver import SolverResult
            result = SolverResult(
                success=True,
                total_flow=self.network.total_system_flow,
                total_pressure=self.network.total_system_pressure,
                sprinkler_count=len(self.network.get_sprinklers()),
                density_mmpm=self.density_var.get(),
                operating_area_m2=self.area_var.get(),
            )
            
            generator = ReportGenerator(self.network, result, settings)
            
            if generator.generate_pdf(filepath):
                messagebox.showinfo("Başarılı", f"PDF rapor oluşturuldu:\n{filepath}")
            else:
                messagebox.showerror("Hata", "PDF oluşturulamadı!")
    
    def _export_excel(self):
        """Excel rapor oluştur"""
        if not self.network.is_calculated:
            messagebox.showwarning("Uyarı", "Önce hesaplama yapın!")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Excel Rapor Kaydet",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")]
        )
        
        if filepath:
            settings = ReportSettings(project_name=self.project_name_var.get())
            
            from .solver import SolverResult
            result = SolverResult(
                success=True,
                total_flow=self.network.total_system_flow,
                total_pressure=self.network.total_system_pressure,
                sprinkler_count=len(self.network.get_sprinklers()),
                density_mmpm=self.density_var.get(),
                operating_area_m2=self.area_var.get(),
            )
            
            generator = ReportGenerator(self.network, result, settings)
            
            if generator.generate_excel(filepath):
                messagebox.showinfo("Başarılı", f"Excel rapor oluşturuldu:\n{filepath}")
            else:
                messagebox.showerror("Hata", "Excel oluşturulamadı!")
    
    # ==================== Diğer Fonksiyonlar ====================
    
    def _undo(self):
        """Geri al"""
        self.canvas._on_undo(None)
        self._update_statistics()
    
    def _redo(self):
        """Yinele"""
        self.canvas._on_redo(None)
        self._update_statistics()
    
    def _delete_selection(self):
        """Seçimi sil"""
        self.canvas._on_delete(None)
        self._update_statistics()
    
    def _select_all(self):
        """Tümünü seç"""
        self.canvas.selected_items = list(self.network.nodes.keys()) + list(self.network.pipes.keys())
        self.canvas.redraw()
    
    def _clear_selection(self):
        """Seçimi temizle"""
        self.canvas.selected_items.clear()
        self.canvas.redraw()
    
    def _fit_to_view(self):
        """Görünüme sığdır"""
        self.canvas.fit_to_view()
    
    def _zoom_100(self):
        """%100 zoom"""
        self.canvas.scale = 1.0
        self.canvas.redraw()
    
    def _toggle_grid(self):
        """Grid göster/gizle"""
        self.canvas.toggle_grid()
    
    def _show_3d_view(self):
        """3D görünüm aç"""
        if not self.network.nodes:
            messagebox.showinfo("Bilgi", "3D görünüm için önce network oluşturun.")
            return
        
        view_window = View3DWindow(self, self.network)
        # Modal değil, arka planda çalışabilsin
    
    def _toggle_dashboard(self):
        """Dashboard göster/gizle"""
        self.dashboard_visible = not self.dashboard_visible
        
        if self.dashboard_visible:
            # Dashboard'u göster
            if not self.dashboard:
                self.dashboard = NetworkDashboard(self.main_paned, DashboardPosition.RIGHT)
                self.dashboard.bind('<<DashboardRefresh>>', lambda e: self._refresh_dashboard())
            
            # Panele ekle
            try:
                self.main_paned.add(self.dashboard, weight=1)
            except:
                pass  # Zaten ekliyse
            
            # İlk güncelleme
            self._refresh_dashboard()
        else:
            # Dashboard'u gizle
            if self.dashboard:
                try:
                    self.main_paned.forget(self.dashboard)
                except:
                    pass
    
    def _refresh_dashboard(self):
        """Dashboard'u güncelle"""
        if not self.dashboard or not self.dashboard_visible:
            return
        
        # Network'ten veri al
        network_data = {
            'pipes': [],
            'sprinklers': [],
            'pump': None,
            'validation': {}
        }
        
        # Pipe verilerini topla
        for pipe in self.network.pipes:
            pipe_data = {
                'length': pipe.length,
                'velocity': getattr(pipe, 'velocity', 0),
                'pressure': getattr(pipe, 'pressure', 0),
            }
            network_data['pipes'].append(pipe_data)
        
        # Sprinkler verilerini topla
        for node in self.network.nodes.values():
            if node.node_type == NodeType.SPRINKLER:
                sprinkler_data = {
                    'flow_rate': getattr(node, 'flow_rate', 80.0),
                }
                network_data['sprinklers'].append(sprinkler_data)
        
        # Pompa bilgisi
        if self.network.pump:
            network_data['pump'] = {
                'power': getattr(self.network.pump, 'power', 0),
            }
        
        # Validation sonuçları
        validator = NetworkValidator(self.network)
        validation_results = validator.validate_all()
        
        error_count = sum(1 for r in validation_results if r.level == ValidationLevel.ERROR)
        warning_count = sum(1 for r in validation_results if r.level == ValidationLevel.WARNING)
        info_count = sum(1 for r in validation_results if r.level == ValidationLevel.INFO)
        
        network_data['validation'] = {
            'error_count': error_count,
            'warning_count': warning_count,
            'info_count': info_count,
        }
        
        # İstatistikleri hesapla ve güncelle
        stats = calculate_network_stats(network_data)
        self.dashboard.update_stats(stats)
    
    def _show_project_settings(self):
        """Proje ayarları dialogu"""
        dialog = ProjectSettingsDialog(self, self.project_settings)
        self.wait_window(dialog)
        
        if dialog.result:
            self.project_settings = dialog.result
            self.is_modified = True
            
            # Canvas'ı güncelle
            if hasattr(self.canvas, 'GRID_SPACING'):
                self.canvas.GRID_SPACING = self.project_settings.grid_spacing
            
            # Proje adını güncelle
            self.network.name = self.project_settings.project_name
            self._update_title()
            
            messagebox.showinfo("Başarılı", "Proje ayarları güncellendi.")
    
    def _show_design_params(self):
        """Tasarım parametreleri dialogu"""
        # Proje ayarlarını aç (tasarım parametreleri sekmesinde)
        self._show_project_settings()
    
    def _show_pump_selection(self):
        """Pompa seçim dialogu"""
        # Sistem değerlerini al
        system_flow = self.network.total_system_flow
        system_pressure = self.network.total_system_pressure
        
        if system_flow <= 0 or system_pressure <= 0:
            # Hesaplama yapılmamışsa varsayılan değerler
            result = messagebox.askyesno(
                "Uyarı",
                "Henüz hidrolik hesaplama yapılmamış.\n"
                "Sistem değerlerini manuel girmek ister misiniz?"
            )
            if not result:
                return
        
        dialog = PumpSelectionDialog(
            self, 
            self.pump_module,
            system_flow=system_flow,
            system_pressure=system_pressure
        )
        self.wait_window(dialog)
        
        # Seçilen pompayı al
        selected = dialog.get_selected_pump()
        if selected:
            messagebox.showinfo(
                "Pompa Seçildi",
                f"Seçilen pompa: {selected.brand} {selected.model}\n"
                f"Kapasite: {selected.rated_flow_lpm:.0f} L/dk @ {selected.rated_pressure_bar:.1f} Bar"
            )
    
    def _show_tank_calculation(self):
        """Su deposu hesabı"""
        system_flow = self.network.total_system_flow
        hazard_class = self.hazard_var.get()
        
        dialog = TankCalculationDialog(
            self,
            self.pump_module,
            system_flow=system_flow if system_flow > 0 else 1000,
            hazard_class=hazard_class
        )
        self.wait_window(dialog)
    
    def _show_db_manager(self):
        """Veritabanı yöneticisi"""
        messagebox.showinfo("Veritabanı", "Bu özellik geliştirilme aşamasında.")
    
    def _show_pipe_catalog(self):
        """Boru çapları kataloğu"""
        dialog = PipeCatalogDialog(self, self.db)
        self.wait_window(dialog)
    
    def _show_fitting_table(self):
        """Fitting tablosu"""
        dialog = FittingTableDialog(self, self.db)
        self.wait_window(dialog)
    
    def _add_batch_sprinklers(self):
        """Toplu sprinkler ekleme dialogu"""
        # Canvas ortasını başlangıç noktası olarak kullan
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            # Ekran merkezini dünya koordinatlarına çevir
            center_x, center_y = self.canvas.screen_to_world(canvas_width / 2, canvas_height / 2)
        else:
            center_x, center_y = 0, 0
        
        dialog = BatchSprinklerDialog(self, self.network, center_x, center_y)
        self.wait_window(dialog)
        
        if dialog.result:
            nodes, pipes = dialog.result
            
            # Node'ları ekle
            for node in nodes:
                self.network.add_node(node)
            
            # Boruları ekle
            for pipe in pipes:
                self.network.add_pipe(pipe)
            
            # Ekranı sığdır
            self.canvas.fit_to_view()
            self.canvas.redraw()
            self._update_statistics()
            self.is_modified = True
            
            messagebox.showinfo("Başarılı", 
                              f"{len(nodes)} sprinkler ve {len(pipes)} boru eklendi.")
    
    def _show_diameter_optimization(self):
        """Boru çapı optimizasyonu dialogu"""
        if not self.network.pipes:
            messagebox.showwarning("Uyarı", "Optimize edilecek boru bulunamadı!")
            return
        
        dialog = DiameterOptimizationDialog(self, self.network, self.db)
        self.wait_window(dialog)
        
        if dialog.result:
            self.canvas.redraw()
            self.is_modified = True
            messagebox.showinfo("Başarılı", "Boru çapları optimize edildi.")
    
    def _show_pressure_zones(self):
        """Basınç bölgeleri dialogu"""
        # Basit zone management penceresi
        zone_window = tk.Toplevel(self)
        zone_window.title("Basınç Bölgeleri Yönetimi")
        zone_window.geometry("600x500")
        
        # Zone panel ekle
        zone_panel = PressureZonePanel(zone_window, self.zone_manager)
        zone_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Callback ayarla
        zone_panel.on_zone_changed = lambda: self.canvas.redraw()
        
        # Modal yap
        zone_window.transient(self)
        zone_window.grab_set()
    
    def _show_material_cost(self):
        """Malzeme ve maliyet yönetimi"""
        # Malzeme veritabanı penceresi
        material_window = tk.Toplevel(self)
        material_window.title("Malzeme ve Maliyet Yönetimi")
        material_window.geometry("900x600")
        
        # Notebook (sekmeler)
        notebook = ttk.Notebook(material_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Sekme 1: Malzeme Veritabanı
        material_frame = ttk.Frame(notebook)
        notebook.add(material_frame, text="📦 Malzeme Veritabanı")
        
        material_panel = MaterialCostPanel(material_frame, self.material_db)
        material_panel.pack(fill=tk.BOTH, expand=True)
        
        # Sekme 2: Proje Maliyeti
        cost_frame = ttk.Frame(notebook, padding=20)
        notebook.add(cost_frame, text="💰 Proje Maliyeti")
        
        # Maliyet hesaplama butonu
        ttk.Button(cost_frame, text="📊 Proje Maliyetini Hesapla",
                  command=lambda: self._calculate_project_cost(cost_frame),
                  width=30).pack(pady=10)
        
        # Sonuç alanı
        result_text = tk.Text(cost_frame, height=20, width=70, state=tk.DISABLED)
        result_text.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Sonuç alanını sakla
        cost_frame.result_text = result_text
        
        # Modal yap
        material_window.transient(self)
        material_window.grab_set()
    
    def _calculate_project_cost(self, parent_frame):
        """Proje maliyetini hesapla ve göster"""
        if not self.network.pipes and not self.network.nodes:
            messagebox.showwarning("Uyarı", "Projeye henüz eleman eklenmemiş!")
            return
        
        # Maliyet hesapla
        estimate = calculate_project_cost(self.network, self.material_db)
        
        # Sonuçları formatla
        breakdown = estimate.get_breakdown()
        
        result_lines = []
        result_lines.append("=" * 60)
        result_lines.append("PROJE MALİYET TAHMİNİ")
        result_lines.append("=" * 60)
        result_lines.append("")
        
        result_lines.append("MALZEMELER:")
        result_lines.append("-" * 60)
        for item, qty in estimate.items:
            total = item.unit_price * qty
            result_lines.append(f"{item.name:40s} {qty:8.2f} {item.unit:6s} {total:12.2f} TL")
        
        result_lines.append("")
        result_lines.append("MALİYET DÖKÜMÜ:")
        result_lines.append("-" * 60)
        result_lines.append(f"{'Malzeme Toplamı:':40s} {breakdown['material_cost']:20.2f} TL")
        result_lines.append(f"{'İşçilik:':40s} {breakdown['labor_cost']:20.2f} TL")
        result_lines.append(f"{'Ara Toplam:':40s} {breakdown['subtotal']:20.2f} TL")
        result_lines.append(f"{'Genel Giderler (%{estimate.overhead_percent:.0f}):':40s} {breakdown['overhead_cost']:20.2f} TL")
        result_lines.append(f"{'Kâr Marjı (%{estimate.profit_percent:.0f}):':40s} {breakdown['profit']:20.2f} TL")
        result_lines.append("=" * 60)
        result_lines.append(f"{'TOPLAM MALİYET:':40s} {breakdown['total_cost']:20.2f} TL")
        result_lines.append("=" * 60)
        
        # Sonuçları göster
        result_text = parent_frame.result_text
        result_text.config(state=tk.NORMAL)
        result_text.delete('1.0', tk.END)
        result_text.insert('1.0', '\n'.join(result_lines))
        result_text.config(state=tk.DISABLED)
    
    def _show_solver_comparison(self):
        """Solver karşılaştırma dialogunu göster"""
        if not self.network.nodes or not self.network.pipes:
            messagebox.showwarning("Uyarı", "Karşılaştırma için önce bir network oluşturun!")
            return
        
        show_solver_comparison(self, self.network, self.db)
    
    def _show_water_hammer_analysis(self):
        """Su darbesi analiz dialogunu göster"""
        if not self.network.pipes:
            messagebox.showwarning("Uyarı", "Analiz için önce bir network oluşturun!")
            return
        
        # Son hesaplama sonuçları (solver_results için)
        solver_results = getattr(self, 'solver', None)
        show_water_hammer_analysis(self, self.network, solver_results)
    
    def _add_network_template(self):
        """Network şablonu dialog"""
        dialog = NetworkTemplateDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            nodes, pipes = dialog.result
            
            # Node'ları ekle
            for node in nodes:
                self.network.add_node(node)
            
            # Boruları ekle
            for pipe in pipes:
                self.network.add_pipe(pipe)
            
            # Ekranı sığdır
            self.canvas.fit_to_view()
            self.canvas.redraw()
            self._update_statistics()
            self.is_modified = True
            
            messagebox.showinfo("Başarılı", 
                              f"{len(nodes)} node ve {len(pipes)} boru eklendi.")
    
    def _show_cad_export(self):
        """CAD export (DXF/PDF) dialogunu göster"""
        if not self.network.nodes:
            messagebox.showwarning("Uyarı", "Export edilecek network bulunamadı!")
            return
        
        # Son hesaplama sonuçlarını al (varsa)
        results = None
        if hasattr(self, 'last_calc_results') and self.last_calc_results:
            results = self.last_calc_results
        
        show_cad_export_dialog(self, self.network, results)
    
    def _import_dxf(self):
        """DXF/DWG dosyasını içe aktar"""
        dialog = DXFImportDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            # DXF verilerini al
            importer = dialog.result['importer']
            geometries = dialog.result['geometries']
            scale = dialog.result['scale']
            opacity = dialog.result['opacity']
            color = dialog.result['color']
            as_background = dialog.result['as_background']
    
            # Canvas'a ekle (canvas'ta DXF background layer'ı yoksa ekle)
            if hasattr(self.canvas, 'set_dxf_background'):
                # Canvas boyutlarını al
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
        
                # Geometrileri dönüştür
                transformed_geoms = []
                for geom in geometries:
                    transformed = importer.transform_to_canvas(
                        geom, canvas_width, canvas_height, scale
                    )
                    transformed_geoms.append(transformed)
        
                # Canvas'a gönder
                self.canvas.set_dxf_background(transformed_geoms, color, opacity)
                self._update_status(f"DXF içe aktarıldı: {len(geometries)} geometri")
            else:
                # Basit mesaj - canvas DXF desteği yok
                messagebox.showinfo("Bilgi", 
                    f"{len(geometries)} geometri içe aktarıldı.\n"
                    "DXF görüntüleme desteği henüz eklenmedi.")
    
    def _show_help(self):
        """Yardım"""
        help_text = """
FireHydra - Yangın Hidrolik Hesaplama Yazılımı

KULLANIM:
1. Araç çubuğundan "Kaynak" seçin ve bir pompa noktası ekleyin
2. "Sprinkler" seçin ve sprinkler noktaları ekleyin
3. "Boru" seçin ve noktaları birbirine bağlayın
4. Tasarım parametrelerini sağ panelden ayarlayın
5. "HESAPLA" butonuna basın

KLAVYE KISAYOLLARI:
- Ctrl+N: Yeni proje
- Ctrl+O: Proje aç
- Ctrl+S: Kaydet
- F5: Hesapla
- Delete: Seçimi sil
- Escape: İptal
- Mouse tekerleği: Zoom
- Orta tıklama + sürükleme: Pan

STANDARTLAR:
- NFPA 13 / NFPA 20
- TS EN 12845
- BYKHY
        """
        messagebox.showinfo("Yardım", help_text)
    
    def _show_formulas(self):
        """Formüller"""
        formulas_text = """
HİDROLİK FORMÜLLER

1. Hazen-Williams Basınç Kaybı:
   ΔP = 6.05×10⁵ × L × Q^1.85 / (C^1.85 × d^4.87)
   
   Burada:
   ΔP: Basınç kaybı (bar)
   L: Boru uzunluğu (m)
   Q: Debi (L/dk)
   C: Hazen-Williams katsayısı
   d: İç çap (mm)

2. Kot Farkı Basıncı:
   ΔP = ΔZ / 10.2
   
   Burada:
   ΔP: Basınç farkı (bar)
   ΔZ: Kot farkı (m)

3. Sprinkler Debisi:
   Q = K × √P
   
   Burada:
   Q: Debi (L/dk)
   K: K-faktör (metrik)
   P: Basınç (bar)

4. Junction Dengeleme:
   Q_new = Q_old × √(P_target / P_current)
        """
        messagebox.showinfo("Formüller", formulas_text)
    
    def _show_about(self):
        """Hakkında"""
        about_text = """
FireHydra v1.0

Yangın Hidrolik Hesaplama ve Tasarım Yazılımı

Standartlar:
• NFPA 13 - Sprinkler Sistemleri
• NFPA 20 - Yangın Pompaları
• TS EN 12845 - Otomatik Sprinkler Sistemleri
• BYKHY - Binaların Yangından Korunması Hakkında Yönetmelik

© 2024 FireHydra Team
        """
        messagebox.showinfo("Hakkında", about_text)


def main():
    """Ana fonksiyon"""
    app = FireHydraApp()
    app.mainloop()


if __name__ == "__main__":
    main()
