"""
FireHydra - Dialog Modülleri
============================

Uygulama içi dialog pencereleri:
- PumpSelectionDialog: Pompa seçimi ve NFPA 20 kontrolü
- TankCalculationDialog: Su deposu hesabı
- ProjectSettingsDialog: Proje ayarları ve tasarım parametreleri
- PipeCatalogDialog: Boru kataloğu görüntüleme
- FittingTableDialog: Fitting tablosu
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List, Tuple, Dict
import math

from pump_tank import PumpAndTankModule, FirePump, PumpType, WaterTankResult
from models import ProjectSettings, DesignStandard, HazardClass, Node, NodeType, Coordinates, Pipe
from optimizer import PipeOptimizer
from report import ReportSettings, ReportTemplate
from dxf_import import DXFImporter, DXFLayer, DXFGeometry


class PumpSelectionDialog(tk.Toplevel):
    """
    Pompa Seçim Dialogu
    
    Özellikler:
    - Sistem noktası girişi (debi, basınç)
    - Uygun pompa listesi
    - Pompa eğrisi karşılaştırma
    - NFPA 20 uyumluluk kontrolü
    - Jockey pompa gereksinimleri
    """
    
    def __init__(self, parent, pump_module: PumpAndTankModule, 
                 system_flow: float = 0, system_pressure: float = 0):
        super().__init__(parent)
        
        self.pump_module = pump_module
        self.system_flow = system_flow
        self.system_pressure = system_pressure
        self.selected_pump: Optional[FirePump] = None
        
        # Pencere ayarları
        self.title("Pompa Seçimi - NFPA 20")
        self.geometry("900x700")
        self.minsize(800, 600)
        self.resizable(True, True)
        
        # GUI oluştur
        self._create_widgets()
        
        # Modal yap
        self.transient(parent)
        self.grab_set()
        
        # İlk yükleme
        if system_flow > 0 and system_pressure > 0:
            self._find_suitable_pumps()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Üst panel - Sistem gereksinimleri
        self._create_system_panel(main_frame)
        
        # Orta panel - Pompa listesi ve detaylar
        self._create_pump_panel(main_frame)
        
        # Alt panel - Butonlar
        self._create_button_panel(main_frame)
    
    def _create_system_panel(self, parent):
        """Sistem gereksinimleri paneli"""
        frame = ttk.LabelFrame(parent, text="Sistem Gereksinimleri", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        # Sol - Giriş alanları
        input_frame = ttk.Frame(frame)
        input_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Debi
        ttk.Label(input_frame, text="Sistem Debisi:").grid(row=0, column=0, sticky="w", pady=5)
        self.flow_var = tk.DoubleVar(value=self.system_flow)
        flow_entry = ttk.Entry(input_frame, textvariable=self.flow_var, width=12)
        flow_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(input_frame, text="L/dk").grid(row=0, column=2, sticky="w")
        
        # Basınç
        ttk.Label(input_frame, text="Sistem Basıncı:").grid(row=1, column=0, sticky="w", pady=5)
        self.pressure_var = tk.DoubleVar(value=self.system_pressure)
        pressure_entry = ttk.Entry(input_frame, textvariable=self.pressure_var, width=12)
        pressure_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(input_frame, text="Bar").grid(row=1, column=2, sticky="w")
        
        # Güvenlik marjı
        ttk.Label(input_frame, text="Güvenlik Marjı:").grid(row=2, column=0, sticky="w", pady=5)
        self.margin_var = tk.DoubleVar(value=10.0)
        margin_combo = ttk.Combobox(input_frame, textvariable=self.margin_var, 
                                    values=["5", "10", "15", "20"], width=10)
        margin_combo.grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(input_frame, text="%").grid(row=2, column=2, sticky="w")
        
        # Sağ - Buton ve özet
        right_frame = ttk.Frame(frame)
        right_frame.pack(side=tk.RIGHT, padx=20)
        
        search_btn = ttk.Button(right_frame, text="🔍 Uygun Pompaları Bul", 
                               command=self._find_suitable_pumps, width=25)
        search_btn.pack(pady=5)
        
        # Özet etiketleri
        self.summary_label = ttk.Label(right_frame, text="", font=("Arial", 9))
        self.summary_label.pack(pady=5)
    
    def _create_pump_panel(self, parent):
        """Pompa listesi ve detaylar paneli"""
        # PanedWindow ile sol-sağ bölme
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Sol - Pompa listesi
        left_frame = ttk.LabelFrame(paned, text="Uygun Pompalar", padding=5)
        paned.add(left_frame, weight=1)
        
        # Treeview
        columns = ("id", "model", "flow", "pressure", "margin", "power")
        self.pump_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=12)
        
        self.pump_tree.heading("id", text="ID")
        self.pump_tree.heading("model", text="Model")
        self.pump_tree.heading("flow", text="Q (L/dk)")
        self.pump_tree.heading("pressure", text="P (Bar)")
        self.pump_tree.heading("margin", text="Marj %")
        self.pump_tree.heading("power", text="Güç (kW)")
        
        self.pump_tree.column("id", width=60)
        self.pump_tree.column("model", width=120)
        self.pump_tree.column("flow", width=80)
        self.pump_tree.column("pressure", width=70)
        self.pump_tree.column("margin", width=70)
        self.pump_tree.column("power", width=70)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.pump_tree.yview)
        self.pump_tree.configure(yscrollcommand=scrollbar.set)
        
        self.pump_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Seçim olayı
        self.pump_tree.bind("<<TreeviewSelect>>", self._on_pump_select)
        
        # Sağ - Pompa detayları
        right_frame = ttk.LabelFrame(paned, text="Pompa Detayları", padding=10)
        paned.add(right_frame, weight=1)
        
        self._create_pump_details(right_frame)
    
    def _create_pump_details(self, parent):
        """Pompa detayları paneli"""
        # Pompa bilgileri
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, pady=5)
        
        # Satır satır bilgiler
        self.detail_labels = {}
        
        details = [
            ("brand", "Marka:"),
            ("model", "Model:"),
            ("type", "Tip:"),
            ("rated", "Nominal:"),
            ("churn", "Churn (Q=0):"),
            ("overload", "Overload (150%):"),
            ("power", "Motor Gücü:"),
        ]
        
        for i, (key, label) in enumerate(details):
            ttk.Label(info_frame, text=label, font=("Arial", 9, "bold")).grid(
                row=i, column=0, sticky="w", pady=2)
            self.detail_labels[key] = ttk.Label(info_frame, text="-", font=("Arial", 9))
            self.detail_labels[key].grid(row=i, column=1, sticky="w", padx=10, pady=2)
        
        # NFPA 20 kontrolü
        ttk.Separator(parent, orient="horizontal").pack(fill=tk.X, pady=10)
        
        nfpa_frame = ttk.LabelFrame(parent, text="NFPA 20 Uyumluluk", padding=5)
        nfpa_frame.pack(fill=tk.X, pady=5)
        
        self.nfpa_text = tk.Text(nfpa_frame, height=4, width=40, font=("Consolas", 9))
        self.nfpa_text.pack(fill=tk.X)
        self.nfpa_text.config(state=tk.DISABLED)
        
        # Sistem noktası kontrolü
        system_frame = ttk.LabelFrame(parent, text="Sistem Noktası Kontrolü", padding=5)
        system_frame.pack(fill=tk.X, pady=5)
        
        self.system_check_label = ttk.Label(system_frame, text="-", font=("Arial", 10))
        self.system_check_label.pack(anchor="w")
        
        # Jockey pompa
        jockey_frame = ttk.LabelFrame(parent, text="Jockey Pompa Gereksinimi", padding=5)
        jockey_frame.pack(fill=tk.X, pady=5)
        
        self.jockey_label = ttk.Label(jockey_frame, text="-", font=("Arial", 9))
        self.jockey_label.pack(anchor="w")
        
        # Pompa eğrisi göster butonu
        ttk.Button(parent, text="📊 Pompa Eğrisini Göster", 
                  command=self._show_pump_curve).pack(pady=10)
    
    def _create_button_panel(self, parent):
        """Alt butonlar"""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="✅ Seç", command=self._select_pump, width=15).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ İptal", command=self.destroy, width=15).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="📋 Karşılaştır", command=self._compare_pumps, width=15).pack(side=tk.LEFT, padx=5)
    
    def _find_suitable_pumps(self):
        """Uygun pompaları bul ve listele"""
        flow = self.flow_var.get()
        pressure = self.pressure_var.get()
        margin = self.margin_var.get()
        
        if flow <= 0 or pressure <= 0:
            messagebox.showwarning("Uyarı", "Lütfen geçerli debi ve basınç değerleri girin!")
            return
        
        # Mevcut listeyi temizle
        for item in self.pump_tree.get_children():
            self.pump_tree.delete(item)
        
        # Uygun pompaları bul
        suitable = self.pump_module.find_suitable_pumps(flow, pressure, margin)
        
        if not suitable:
            self.summary_label.config(text="❌ Uygun pompa bulunamadı!")
            messagebox.showinfo("Sonuç", "Verilen kriterlere uygun pompa bulunamadı.\n"
                              "Daha yüksek kapasiteli pompalar ekleyin veya marjı düşürün.")
            return
        
        # Listeye ekle
        for pump, margin_val in suitable:
            self.pump_tree.insert("", "end", values=(
                pump.id,
                f"{pump.brand} {pump.model}",
                f"{pump.rated_flow_lpm:.0f}",
                f"{pump.rated_pressure_bar:.1f}",
                f"{margin_val:.1f}",
                f"{pump.power_kw:.1f}"
            ))
        
        self.summary_label.config(text=f"✅ {len(suitable)} uygun pompa bulundu")
        
        # İlk pompayı seç
        if suitable:
            first_item = self.pump_tree.get_children()[0]
            self.pump_tree.selection_set(first_item)
            self.pump_tree.focus(first_item)
    
    def _on_pump_select(self, event):
        """Pompa seçildiğinde detayları göster"""
        selection = self.pump_tree.selection()
        if not selection:
            return
        
        # Seçilen pompanın ID'sini al
        item = self.pump_tree.item(selection[0])
        pump_id = item['values'][0]
        
        # Pompayı bul
        pump = self.pump_module.get_pump_by_id(pump_id)
        if not pump:
            return
        
        self.selected_pump = pump
        
        # Detayları güncelle
        self.detail_labels["brand"].config(text=pump.brand)
        self.detail_labels["model"].config(text=pump.model)
        self.detail_labels["type"].config(text=pump.pump_type.value)
        self.detail_labels["rated"].config(text=f"{pump.rated_flow_lpm:.0f} L/dk @ {pump.rated_pressure_bar:.1f} Bar")
        self.detail_labels["churn"].config(text=f"{pump.churn_pressure_bar:.2f} Bar")
        self.detail_labels["overload"].config(text=f"{pump.overload_flow_lpm:.0f} L/dk @ {pump.overload_pressure_bar:.2f} Bar")
        self.detail_labels["power"].config(text=f"{pump.power_kw:.1f} kW")
        
        # NFPA 20 kontrolü
        is_compliant, issues = pump.check_nfpa20_compliance()
        self.nfpa_text.config(state=tk.NORMAL)
        self.nfpa_text.delete("1.0", tk.END)
        for issue in issues:
            self.nfpa_text.insert(tk.END, f"• {issue}\n")
        self.nfpa_text.config(state=tk.DISABLED)
        
        # Sistem noktası kontrolü
        flow = self.flow_var.get()
        pressure = self.pressure_var.get()
        is_suitable, message = pump.check_system_point(flow, pressure)
        
        color = "green" if is_suitable else "red"
        self.system_check_label.config(text=message, foreground=color)
        
        # Jockey pompa gereksinimi
        jockey = self.pump_module.get_jockey_pump_requirements(pump)
        self.jockey_label.config(
            text=f"Debi: {jockey['flow_lpm']:.1f} L/dk, Basınç: {jockey['pressure_bar']:.2f} Bar"
        )
    
    def _show_pump_curve(self):
        """Pompa eğrisini göster (metin tabanlı)"""
        if not self.selected_pump:
            messagebox.showwarning("Uyarı", "Lütfen önce bir pompa seçin!")
            return
        
        pump = self.selected_pump
        
        # Eğri noktalarını oluştur
        if not pump.curve_points:
            pump.generate_curve()
        
        # Dialog penceresi
        curve_dialog = tk.Toplevel(self)
        curve_dialog.title(f"Pompa Eğrisi - {pump.brand} {pump.model}")
        curve_dialog.geometry("500x450")
        curve_dialog.transient(self)
        
        # Text widget ile ASCII grafik
        text = tk.Text(curve_dialog, font=("Consolas", 10), width=60, height=25)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ASCII grafik oluştur
        curve_text = self._generate_ascii_curve(pump)
        text.insert("1.0", curve_text)
        text.config(state=tk.DISABLED)
    
    def _generate_ascii_curve(self, pump: FirePump) -> str:
        """ASCII pompa eğrisi oluştur"""
        lines = []
        lines.append(f"{'='*50}")
        lines.append(f"  POMPA EĞRİSİ: {pump.brand} {pump.model}")
        lines.append(f"{'='*50}")
        lines.append("")
        
        # Basınç ekseni (Y)
        max_p = pump.churn_pressure_bar * 1.1
        min_p = 0
        
        # Debi ekseni (X)
        max_q = pump.overload_flow_lpm * 1.1
        
        # Grid boyutları
        width = 45
        height = 15
        
        # Grid oluştur
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        
        # Eksenleri çiz
        for i in range(height):
            grid[i][0] = '│'
        for j in range(width):
            grid[height-1][j] = '─'
        grid[height-1][0] = '└'
        
        # Eğri noktalarını çiz
        for point in pump.curve_points:
            x = int((point.flow_lpm / max_q) * (width - 2)) + 1
            y = height - 2 - int((point.pressure_bar / max_p) * (height - 2))
            
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = '●'
        
        # Sistem noktasını işaretle
        flow = self.flow_var.get()
        pressure = self.pressure_var.get()
        if flow > 0 and pressure > 0:
            x = int((flow / max_q) * (width - 2)) + 1
            y = height - 2 - int((pressure / max_p) * (height - 2))
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = '★'
        
        # Grid'i string'e çevir
        lines.append(f"P(bar)")
        lines.append(f" {max_p:.1f}┐")
        for row in grid:
            lines.append('     ' + ''.join(row))
        lines.append(f"      0{'─'*20} Q(L/dk) ─→ {max_q:.0f}")
        lines.append("")
        lines.append("  ● : Pompa Eğrisi")
        lines.append("  ★ : Sistem Noktası")
        lines.append("")
        lines.append(f"{'─'*50}")
        lines.append("  KONTROL NOKTALARI:")
        lines.append(f"  • Churn (Q=0):     {pump.churn_pressure_bar:.2f} Bar")
        lines.append(f"  • Nominal:         {pump.rated_flow_lpm:.0f} L/dk @ {pump.rated_pressure_bar:.2f} Bar")
        lines.append(f"  • Overload (150%): {pump.overload_flow_lpm:.0f} L/dk @ {pump.overload_pressure_bar:.2f} Bar")
        
        if flow > 0:
            pump_p = pump.get_pressure_at_flow(flow)
            lines.append(f"  • Sistem noktası:  {flow:.0f} L/dk @ {pump_p:.2f} Bar (talep: {pressure:.2f} Bar)")
        
        return '\n'.join(lines)
    
    def _compare_pumps(self):
        """Seçili pompaları karşılaştır"""
        selections = self.pump_tree.selection()
        if len(selections) < 2:
            messagebox.showinfo("Bilgi", "Karşılaştırma için en az 2 pompa seçin.\n"
                              "(Ctrl + tıklama ile çoklu seçim yapabilirsiniz)")
            return
        
        # Karşılaştırma dialogu
        compare_dialog = tk.Toplevel(self)
        compare_dialog.title("Pompa Karşılaştırma")
        compare_dialog.geometry("700x400")
        compare_dialog.transient(self)
        
        # Treeview
        columns = ("property", ) + tuple(f"pump{i}" for i in range(len(selections)))
        tree = ttk.Treeview(compare_dialog, columns=columns, show="headings", height=15)
        
        tree.heading("property", text="Özellik")
        tree.column("property", width=150)
        
        pumps = []
        for i, sel in enumerate(selections):
            pump_id = self.pump_tree.item(sel)['values'][0]
            pump = self.pump_module.get_pump_by_id(pump_id)
            if pump:
                pumps.append(pump)
                tree.heading(f"pump{i}", text=f"{pump.brand} {pump.model}")
                tree.column(f"pump{i}", width=130)
        
        # Karşılaştırma satırları
        properties = [
            ("Tip", lambda p: p.pump_type.value),
            ("Nominal Debi (L/dk)", lambda p: f"{p.rated_flow_lpm:.0f}"),
            ("Nominal Basınç (Bar)", lambda p: f"{p.rated_pressure_bar:.2f}"),
            ("Churn Basıncı (Bar)", lambda p: f"{p.churn_pressure_bar:.2f}"),
            ("Overload Debi (L/dk)", lambda p: f"{p.overload_flow_lpm:.0f}"),
            ("Overload Basınç (Bar)", lambda p: f"{p.overload_pressure_bar:.2f}"),
            ("Motor Gücü (kW)", lambda p: f"{p.power_kw:.1f}"),
            ("NFPA 20 Uyumu", lambda p: "✅" if p.check_nfpa20_compliance()[0] else "❌"),
        ]
        
        # Sistem noktası için kontrol
        flow = self.flow_var.get()
        pressure = self.pressure_var.get()
        if flow > 0 and pressure > 0:
            properties.append(("Sistem Noktası", 
                             lambda p: "✅" if p.check_system_point(flow, pressure)[0] else "❌"))
            properties.append(("Basınç @ Sistem Q (Bar)", 
                             lambda p: f"{p.get_pressure_at_flow(flow):.2f}"))
        
        for prop_name, prop_func in properties:
            values = [prop_name] + [prop_func(p) for p in pumps]
            tree.insert("", "end", values=values)
        
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def _select_pump(self):
        """Seçili pompayı onayla"""
        if not self.selected_pump:
            messagebox.showwarning("Uyarı", "Lütfen bir pompa seçin!")
            return
        
        self.destroy()
    
    def get_selected_pump(self) -> Optional[FirePump]:
        """Seçilen pompayı döndür"""
        return self.selected_pump


class TankCalculationDialog(tk.Toplevel):
    """
    Su Deposu Hesaplama Dialogu
    
    Özellikler:
    - Tehlike sınıfı seçimi
    - Sprinkler debisi girişi
    - Hidrant debisi otomatik/manuel
    - Süre hesabı
    - Tank boyutları
    """
    
    def __init__(self, parent, pump_module: PumpAndTankModule,
                 system_flow: float = 0, hazard_class: str = "OH2"):
        super().__init__(parent)
        
        self.pump_module = pump_module
        self.system_flow = system_flow
        self.hazard_class = hazard_class
        self.result: Optional[WaterTankResult] = None
        
        # Pencere ayarları
        self.title("Su Deposu Hesabı - TS EN 12845 / BYKHY")
        self.geometry("600x550")
        self.resizable(False, False)
        
        # GUI oluştur
        self._create_widgets()
        
        # Modal
        self.transient(parent)
        self.grab_set()
        
        # İlk hesaplama
        self._calculate()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Giriş parametreleri
        input_frame = ttk.LabelFrame(main_frame, text="Giriş Parametreleri", padding=10)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Standart seçimi
        ttk.Label(input_frame, text="Standart:").grid(row=0, column=0, sticky="w", pady=5)
        self.standard_var = tk.StringVar(value="NFPA")
        standard_combo = ttk.Combobox(input_frame, textvariable=self.standard_var,
                                      values=["NFPA", "EN 12845", "BYKHY"], width=15)
        standard_combo.grid(row=0, column=1, pady=5)
        standard_combo.bind("<<ComboboxSelected>>", lambda e: self._update_hazard_options())
        
        # Tehlike sınıfı
        ttk.Label(input_frame, text="Tehlike Sınıfı:").grid(row=1, column=0, sticky="w", pady=5)
        self.hazard_var = tk.StringVar(value=self.hazard_class)
        self.hazard_combo = ttk.Combobox(input_frame, textvariable=self.hazard_var, width=20)
        self.hazard_combo.grid(row=1, column=1, pady=5)
        self.hazard_combo.bind("<<ComboboxSelected>>", lambda e: self._calculate())
        self._update_hazard_options()
        
        # Sprinkler debisi
        ttk.Label(input_frame, text="Sprinkler Debisi:").grid(row=2, column=0, sticky="w", pady=5)
        self.sprinkler_flow_var = tk.DoubleVar(value=self.system_flow)
        ttk.Entry(input_frame, textvariable=self.sprinkler_flow_var, width=12).grid(row=2, column=1, sticky="w", pady=5)
        ttk.Label(input_frame, text="L/dk").grid(row=2, column=2, sticky="w")
        
        # Hidrant debisi
        ttk.Label(input_frame, text="Hidrant Debisi:").grid(row=3, column=0, sticky="w", pady=5)
        self.hose_auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(input_frame, text="Otomatik", variable=self.hose_auto_var,
                       command=self._toggle_hose_entry).grid(row=3, column=1, sticky="w", pady=5)
        
        self.hose_flow_var = tk.DoubleVar(value=500)
        self.hose_entry = ttk.Entry(input_frame, textvariable=self.hose_flow_var, width=12, state="disabled")
        self.hose_entry.grid(row=4, column=1, sticky="w", pady=2)
        ttk.Label(input_frame, text="L/dk").grid(row=4, column=2, sticky="w")
        
        # Hesapla butonu
        ttk.Button(input_frame, text="🔄 Hesapla", command=self._calculate, width=15).grid(
            row=5, column=0, columnspan=2, pady=15)
        
        # Sonuçlar
        result_frame = ttk.LabelFrame(main_frame, text="Hesaplama Sonuçları", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Sonuç etiketleri
        self.result_labels = {}
        
        results = [
            ("sprinkler", "Sprinkler Debisi:"),
            ("hose", "Hidrant Debisi:"),
            ("total_flow", "Toplam Debi:"),
            ("duration", "Su Süresi:"),
            ("volume", "Gerekli Hacim:"),
        ]
        
        for i, (key, label) in enumerate(results):
            ttk.Label(result_frame, text=label, font=("Arial", 10)).grid(
                row=i, column=0, sticky="w", pady=5)
            self.result_labels[key] = ttk.Label(result_frame, text="-", font=("Arial", 10, "bold"))
            self.result_labels[key].grid(row=i, column=1, sticky="w", padx=20, pady=5)
        
        # Ayırıcı
        ttk.Separator(result_frame, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        
        # Tank boyutları
        ttk.Label(result_frame, text="Önerilen Tank Boyutları:", font=("Arial", 10, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=5)
        
        dims = [
            ("length", "Uzunluk:"),
            ("width", "Genişlik:"),
            ("height", "Yükseklik:"),
        ]
        
        for i, (key, label) in enumerate(dims):
            ttk.Label(result_frame, text=label).grid(row=7+i, column=0, sticky="w", pady=2, padx=20)
            self.result_labels[key] = ttk.Label(result_frame, text="-")
            self.result_labels[key].grid(row=7+i, column=1, sticky="w", pady=2)
        
        # Butonlar
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="✅ Tamam", command=self.destroy, width=15).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="📋 Kopyala", command=self._copy_results, width=15).pack(side=tk.RIGHT, padx=5)
    
    def _update_hazard_options(self):
        """Tehlike sınıfı seçeneklerini standarda göre güncelle"""
        standard = self.standard_var.get()
        
        if standard == "BYKHY":
            options = ["BYKHY_KONUT", "BYKHY_OFIS", "BYKHY_TICARI", "BYKHY_ENDUSTRI"]
        else:
            options = ["LIGHT_HAZARD", "ORDINARY_HAZARD_1", "ORDINARY_HAZARD_2", 
                      "HIGH_HAZARD_PROCESS", "HIGH_HAZARD_STORAGE"]
        
        self.hazard_combo['values'] = options
        if self.hazard_var.get() not in options:
            self.hazard_var.set(options[0])
    
    def _toggle_hose_entry(self):
        """Hidrant giriş alanını aktif/pasif yap"""
        if self.hose_auto_var.get():
            self.hose_entry.config(state="disabled")
        else:
            self.hose_entry.config(state="normal")
        self._calculate()
    
    def _calculate(self):
        """Su deposu hesabı yap"""
        sprinkler_flow = self.sprinkler_flow_var.get()
        hazard = self.hazard_var.get()
        standard = self.standard_var.get()
        
        # Hesapla
        self.result = self.pump_module.calculate_water_tank(sprinkler_flow, hazard, standard)
        
        # Hidrant debisi manuel mi?
        if not self.hose_auto_var.get():
            self.result.hose_stream_lpm = self.hose_flow_var.get()
            self.result.total_flow_lpm = sprinkler_flow + self.result.hose_stream_lpm
            self.result.required_volume_m3 = (self.result.total_flow_lpm * self.result.duration_min) / 1000
        else:
            self.hose_flow_var.set(self.result.hose_stream_lpm)
        
        # Sonuçları göster
        self.result_labels["sprinkler"].config(text=f"{sprinkler_flow:.0f} L/dk")
        self.result_labels["hose"].config(text=f"{self.result.hose_stream_lpm:.0f} L/dk")
        self.result_labels["total_flow"].config(text=f"{self.result.total_flow_lpm:.0f} L/dk")
        self.result_labels["duration"].config(text=f"{self.result.duration_min} dakika")
        self.result_labels["volume"].config(text=f"{self.result.required_volume_m3:.1f} m³")
        
        # Tank boyutları
        dims = self.pump_module.calculate_tank_dimensions(self.result.required_volume_m3)
        self.result_labels["length"].config(text=f"{dims['length_m']:.2f} m")
        self.result_labels["width"].config(text=f"{dims['width_m']:.2f} m")
        self.result_labels["height"].config(text=f"{dims['height_m']:.2f} m")
    
    def _copy_results(self):
        """Sonuçları panoya kopyala"""
        if not self.result:
            return
        
        text = f"""SU DEPOSU HESABI
================
Standart: {self.standard_var.get()}
Tehlike Sınıfı: {self.result.hazard_class}

Sprinkler Debisi: {self.result.system_flow_lpm:.0f} L/dk
Hidrant Debisi: {self.result.hose_stream_lpm:.0f} L/dk
Toplam Debi: {self.result.total_flow_lpm:.0f} L/dk
Su Süresi: {self.result.duration_min} dakika
Gerekli Hacim: {self.result.required_volume_m3:.1f} m³
"""
        
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Bilgi", "Sonuçlar panoya kopyalandı!")
    
    def get_result(self) -> Optional[WaterTankResult]:
        """Hesaplama sonucunu döndür"""
        return self.result


class PipeCatalogDialog(tk.Toplevel):
    """Boru Kataloğu Dialogu"""
    
    def __init__(self, parent, db):
        super().__init__(parent)
        
        self.db = db
        
        self.title("Boru Kataloğu")
        self.geometry("600x450")
        self.resizable(True, True)
        
        self._create_widgets()
        self._load_data()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Filtre
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Malzeme:").pack(side=tk.LEFT)
        self.material_var = tk.StringVar(value="Tümü")
        material_combo = ttk.Combobox(filter_frame, textvariable=self.material_var,
                                      values=["Tümü", "Steel", "CPVC", "Galvanized"], width=15)
        material_combo.pack(side=tk.LEFT, padx=5)
        material_combo.bind("<<ComboboxSelected>>", lambda e: self._load_data())
        
        # Treeview
        columns = ("nominal", "internal", "wall", "material", "c_factor")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)
        
        self.tree.heading("nominal", text="Nominal (mm)")
        self.tree.heading("internal", text="İç Çap (mm)")
        self.tree.heading("wall", text="Et Kalınlığı (mm)")
        self.tree.heading("material", text="Malzeme")
        self.tree.heading("c_factor", text="C Faktörü")
        
        for col in columns:
            self.tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Kapat butonu
        ttk.Button(main_frame, text="Kapat", command=self.destroy).pack(pady=10)
    
    def _load_data(self):
        """Verileri yükle"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        pipes = self.db.get_all_pipe_types()
        material_filter = self.material_var.get()
        
        for pipe in pipes:
            if material_filter != "Tümü" and pipe.material != material_filter:
                continue
            
            self.tree.insert("", "end", values=(
                pipe.nominal_diameter,
                f"{pipe.internal_diameter:.1f}",
                f"{pipe.wall_thickness:.2f}",
                pipe.material,
                pipe.c_factor
            ))


class FittingTableDialog(tk.Toplevel):
    """Fitting Tablosu Dialogu"""
    
    def __init__(self, parent, db):
        super().__init__(parent)
        
        self.db = db
        
        self.title("Fitting Eşdeğer Uzunluk Tablosu")
        self.geometry("700x500")
        self.resizable(True, True)
        
        self._create_widgets()
        self._load_data()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Filtre
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Çap (mm):").pack(side=tk.LEFT)
        self.diameter_var = tk.StringVar(value="50")
        diameter_combo = ttk.Combobox(filter_frame, textvariable=self.diameter_var,
                                      values=["25", "32", "40", "50", "65", "80", "100", "125", "150"], width=10)
        diameter_combo.pack(side=tk.LEFT, padx=5)
        diameter_combo.bind("<<ComboboxSelected>>", lambda e: self._load_data())
        
        # Treeview
        columns = ("type", "eq_length", "description")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=18)
        
        self.tree.heading("type", text="Fitting Tipi")
        self.tree.heading("eq_length", text="Eşdeğer Uzunluk (m)")
        self.tree.heading("description", text="Açıklama")
        
        self.tree.column("type", width=200)
        self.tree.column("eq_length", width=150)
        self.tree.column("description", width=250)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Not
        note_label = ttk.Label(main_frame, text="Not: Eşdeğer uzunluklar C=120 için verilmiştir.", 
                              font=("Arial", 9, "italic"))
        note_label.pack(pady=5)
        
        # Kapat butonu
        ttk.Button(main_frame, text="Kapat", command=self.destroy).pack(pady=5)
    
    def _load_data(self):
        """Verileri yükle"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        diameter = int(self.diameter_var.get())
        fittings = self.db.get_fittings_by_diameter(diameter)
        
        for fitting in fittings:
            self.tree.insert("", "end", values=(
                fitting.fitting_type,
                f"{fitting.equivalent_length:.2f}",
                fitting.description or ""
            ))


class ProjectSettingsDialog(tk.Toplevel):
    """
    Proje Ayarları Dialogu
    
    Proje bilgileri, tasarım parametreleri ve varsayılan değerleri ayarlamak için.
    
    Özellikler:
    - Proje bilgileri (ad, numara, lokasyon, müşteri, mühendis)
    - Tasarım standardı seçimi
    - Tehlike sınıfı seçimi
    - Varsayılan değerler (C-faktör, K-faktör, kaplama alanı)
    - Otomatik tasarım parametreleri (yoğunluk, alan)
    """
    
    def __init__(self, parent, settings: ProjectSettings):
        super().__init__(parent)
        self.settings = settings
        self.result = None  # Dialog sonucu
        
        self.title("Proje Ayarları")
        self.geometry("700x650")
        self.resizable(False, False)
        
        self._create_widgets()
        self._load_values()
        
        # Modal yap
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        # Ana notebook (sekmeler)
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Sekme 1: Proje Bilgileri
        info_frame = ttk.Frame(notebook, padding=15)
        notebook.add(info_frame, text="Proje Bilgileri")
        self._create_project_info_tab(info_frame)
        
        # Sekme 2: Tasarım Parametreleri
        design_frame = ttk.Frame(notebook, padding=15)
        notebook.add(design_frame, text="Tasarım Parametreleri")
        self._create_design_params_tab(design_frame)
        
        # Sekme 3: Varsayılan Değerler
        defaults_frame = ttk.Frame(notebook, padding=15)
        notebook.add(defaults_frame, text="Varsayılan Değerler")
        self._create_defaults_tab(defaults_frame)
        
        # Sekme 4: Grid Ayarları
        grid_frame = ttk.Frame(notebook, padding=15)
        notebook.add(grid_frame, text="Grid Ayarları")
        self._create_grid_tab(grid_frame)
        
        # Alt butonlar
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(button_frame, text="Tamam", command=self._on_ok, width=15).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="İptal", command=self._on_cancel, width=15).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Varsayılanlara Dön", command=self._reset_defaults).pack(side=tk.LEFT)
    
    def _create_project_info_tab(self, parent):
        """Proje bilgileri sekmesi"""
        # Proje Adı
        ttk.Label(parent, text="Proje Adı:").grid(row=0, column=0, sticky="w", pady=5)
        self.project_name_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.project_name_var, width=50).grid(row=0, column=1, pady=5, sticky="ew")
        
        # Proje Numarası
        ttk.Label(parent, text="Proje Numarası:").grid(row=1, column=0, sticky="w", pady=5)
        self.project_number_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.project_number_var, width=50).grid(row=1, column=1, pady=5, sticky="ew")
        
        # Lokasyon
        ttk.Label(parent, text="Lokasyon:").grid(row=2, column=0, sticky="w", pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.location_var, width=50).grid(row=2, column=1, pady=5, sticky="ew")
        
        # Müşteri
        ttk.Label(parent, text="Müşteri:").grid(row=3, column=0, sticky="w", pady=5)
        self.client_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.client_var, width=50).grid(row=3, column=1, pady=5, sticky="ew")
        
        # Mühendis
        ttk.Label(parent, text="Mühendis:").grid(row=4, column=0, sticky="w", pady=5)
        self.engineer_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.engineer_var, width=50).grid(row=4, column=1, pady=5, sticky="ew")
        
        # Tarih (read-only)
        ttk.Label(parent, text="Tarih:").grid(row=5, column=0, sticky="w", pady=5)
        self.date_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.date_var, width=50, state="readonly").grid(row=5, column=1, pady=5, sticky="ew")
        
        parent.columnconfigure(1, weight=1)
    
    def _create_design_params_tab(self, parent):
        """Tasarım parametreleri sekmesi"""
        # Tasarım Standardı
        ttk.Label(parent, text="Tasarım Standardı:").grid(row=0, column=0, sticky="w", pady=5)
        self.standard_var = tk.StringVar()
        standard_combo = ttk.Combobox(parent, textvariable=self.standard_var, width=30, state="readonly")
        standard_combo['values'] = [s.value for s in DesignStandard]
        standard_combo.grid(row=0, column=1, pady=5, sticky="w")
        
        # Tehlike Sınıfı
        ttk.Label(parent, text="Tehlike Sınıfı:").grid(row=1, column=0, sticky="w", pady=5)
        self.hazard_var = tk.StringVar()
        hazard_combo = ttk.Combobox(parent, textvariable=self.hazard_var, width=40, state="readonly")
        hazard_combo['values'] = [h.value for h in HazardClass]
        hazard_combo.grid(row=1, column=1, pady=5, sticky="w", columnspan=2)
        hazard_combo.bind("<<ComboboxSelected>>", self._on_hazard_changed)
        
        # Tasarım Yoğunluğu
        ttk.Label(parent, text="Tasarım Yoğunluğu:").grid(row=2, column=0, sticky="w", pady=5)
        self.density_var = tk.DoubleVar()
        density_spin = ttk.Spinbox(parent, textvariable=self.density_var, from_=1.0, to=25.0, 
                                   increment=0.5, width=15)
        density_spin.grid(row=2, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="mm/dk").grid(row=2, column=2, sticky="w", padx=(5,0))
        
        # Tasarım Alanı
        ttk.Label(parent, text="Tasarım Alanı:").grid(row=3, column=0, sticky="w", pady=5)
        self.area_var = tk.DoubleVar()
        area_spin = ttk.Spinbox(parent, textvariable=self.area_var, from_=50, to=500, 
                               increment=10, width=15)
        area_spin.grid(row=3, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="m²").grid(row=3, column=2, sticky="w", padx=(5,0))
        
        # Minimum Artık Basınç
        ttk.Label(parent, text="Min. Artık Basınç:").grid(row=4, column=0, sticky="w", pady=5)
        self.residual_var = tk.DoubleVar()
        residual_spin = ttk.Spinbox(parent, textvariable=self.residual_var, from_=0.3, to=2.0, 
                                    increment=0.1, width=15)
        residual_spin.grid(row=4, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="bar").grid(row=4, column=2, sticky="w", padx=(5,0))
        
        # Bilgi notu
        info_text = """
Tasarım parametreleri seçilen tehlike sınıfına göre otomatik olarak ayarlanır.
Gerekirse manuel olarak değiştirilebilir.

NFPA 13 Referans Değerleri:
• Light Hazard: 2.5 mm/dk, 84 m²
• Ordinary Hazard Group 1: 5.0 mm/dk, 140 m²
• Ordinary Hazard Group 2: 6.5 mm/dk, 140 m²
• Extra Hazard Group 1: 12.0 mm/dk, 232 m²
"""
        info_label = ttk.Label(parent, text=info_text, font=("Arial", 8), 
                              justify=tk.LEFT, foreground="gray")
        info_label.grid(row=5, column=0, columnspan=3, sticky="w", pady=10)
        
        parent.columnconfigure(1, weight=1)
    
    def _create_defaults_tab(self, parent):
        """Varsayılan değerler sekmesi"""
        # C-Faktör
        ttk.Label(parent, text="Boru C-Faktörü (Hazen-Williams):").grid(row=0, column=0, sticky="w", pady=5)
        self.c_factor_var = tk.DoubleVar()
        c_spin = ttk.Spinbox(parent, textvariable=self.c_factor_var, from_=80, to=150, 
                            increment=5, width=15)
        c_spin.grid(row=0, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="(120 = yeni çelik boru)").grid(row=0, column=2, sticky="w", padx=(5,0))
        
        # K-Faktör
        ttk.Label(parent, text="Sprinkler K-Faktörü:").grid(row=1, column=0, sticky="w", pady=5)
        self.k_factor_var = tk.DoubleVar()
        k_spin = ttk.Spinbox(parent, textvariable=self.k_factor_var, from_=50, to=200, 
                            increment=5, width=15)
        k_spin.grid(row=1, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="(Metrik)").grid(row=1, column=2, sticky="w", padx=(5,0))
        
        # Kaplama Alanı
        ttk.Label(parent, text="Sprinkler Kaplama Alanı:").grid(row=2, column=0, sticky="w", pady=5)
        self.coverage_var = tk.DoubleVar()
        coverage_spin = ttk.Spinbox(parent, textvariable=self.coverage_var, from_=6, to=20, 
                                   increment=1, width=15)
        coverage_spin.grid(row=2, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="m²").grid(row=2, column=2, sticky="w", padx=(5,0))
        
        # Minimum Basınç
        ttk.Label(parent, text="Min. Sprinkler Basıncı:").grid(row=3, column=0, sticky="w", pady=5)
        self.min_pressure_var = tk.DoubleVar()
        pressure_spin = ttk.Spinbox(parent, textvariable=self.min_pressure_var, from_=0.3, to=2.0, 
                                   increment=0.1, width=15)
        pressure_spin.grid(row=3, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="bar").grid(row=3, column=2, sticky="w", padx=(5,0))
        
        # Bilgi
        info_text = """
Bu değerler yeni eklenen sprinkler ve borular için varsayılan değerler olarak kullanılır.
Mevcut elemanlar etkilenmez.

Yaygın K-Faktör Değerleri:
• 80: Standart orifis (1/2")
• 115: Büyük orifis (17/32")
• 160: Ekstra büyük orifis (Special)
"""
        ttk.Label(parent, text=info_text, font=("Arial", 8), 
                 justify=tk.LEFT, foreground="gray").grid(row=4, column=0, columnspan=3, sticky="w", pady=10)
        
        parent.columnconfigure(1, weight=1)
    
    def _create_grid_tab(self, parent):
        """Grid ayarları sekmesi"""
        # Grid Aralığı
        ttk.Label(parent, text="Grid Aralığı:").grid(row=0, column=0, sticky="w", pady=5)
        self.grid_spacing_var = tk.IntVar()
        spacing_spin = ttk.Spinbox(parent, textvariable=self.grid_spacing_var, from_=100, to=5000, 
                                  increment=100, width=15)
        spacing_spin.grid(row=0, column=1, pady=5, sticky="w")
        ttk.Label(parent, text="mm").grid(row=0, column=2, sticky="w", padx=(5,0))
        
        # Snap to Grid
        self.snap_grid_var = tk.BooleanVar()
        ttk.Checkbutton(parent, text="Grid'e hizala (Snap to Grid)", 
                       variable=self.snap_grid_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        
        # Birim Ayarları
        ttk.Label(parent, text="Birim Ayarları", font=("Arial", 10, "bold")).grid(row=2, column=0, 
                                                                                  columnspan=3, sticky="w", pady=(15,5))
        
        # Uzunluk birimi
        ttk.Label(parent, text="Uzunluk Birimi:").grid(row=3, column=0, sticky="w", pady=5)
        self.length_unit_var = tk.StringVar()
        ttk.Combobox(parent, textvariable=self.length_unit_var, values=["mm", "m", "ft"], 
                    width=12, state="readonly").grid(row=3, column=1, pady=5, sticky="w")
        
        # Basınç birimi
        ttk.Label(parent, text="Basınç Birimi:").grid(row=4, column=0, sticky="w", pady=5)
        self.pressure_unit_var = tk.StringVar()
        ttk.Combobox(parent, textvariable=self.pressure_unit_var, values=["bar", "psi", "kPa"], 
                    width=12, state="readonly").grid(row=4, column=1, pady=5, sticky="w")
        
        # Debi birimi
        ttk.Label(parent, text="Debi Birimi:").grid(row=5, column=0, sticky="w", pady=5)
        self.flow_unit_var = tk.StringVar()
        ttk.Combobox(parent, textvariable=self.flow_unit_var, values=["L/dk", "L/min", "gpm"], 
                    width=12, state="readonly").grid(row=5, column=1, pady=5, sticky="w")
        
        parent.columnconfigure(1, weight=1)
    
    def _load_values(self):
        """Mevcut ayarları yükle"""
        # Proje bilgileri
        self.project_name_var.set(self.settings.project_name)
        self.project_number_var.set(self.settings.project_number)
        self.location_var.set(self.settings.location)
        self.client_var.set(self.settings.client)
        self.engineer_var.set(self.settings.engineer)
        self.date_var.set(self.settings.date_created)
        
        # Tasarım parametreleri
        self.standard_var.set(self.settings.design_standard.value)
        self.hazard_var.set(self.settings.hazard_class.value)
        self.density_var.set(self.settings.design_density)
        self.area_var.set(self.settings.design_area)
        self.residual_var.set(self.settings.min_residual_pressure)
        
        # Varsayılanlar
        self.c_factor_var.set(self.settings.default_pipe_c_factor)
        self.k_factor_var.set(self.settings.default_sprinkler_k_factor)
        self.coverage_var.set(self.settings.default_coverage_area)
        self.min_pressure_var.set(self.settings.default_min_pressure)
        
        # Grid
        self.grid_spacing_var.set(self.settings.grid_spacing)
        self.snap_grid_var.set(self.settings.snap_to_grid)
        self.length_unit_var.set(self.settings.length_unit)
        self.pressure_unit_var.set(self.settings.pressure_unit)
        self.flow_unit_var.set(self.settings.flow_unit)
    
    def _on_hazard_changed(self, event=None):
        """Tehlike sınıfı değiştiğinde otomatik ayarla"""
        hazard_value = self.hazard_var.get()
        
        # String'den enum'a çevir
        for h in HazardClass:
            if h.value == hazard_value:
                # Geçici settings oluştur
                temp_settings = ProjectSettings(hazard_class=h)
                
                # Otomatik değerleri al
                density = temp_settings.get_design_density_for_hazard()
                area = temp_settings.get_design_area_for_hazard()
                
                # Güncelle
                self.density_var.set(density)
                self.area_var.set(area)
                break
    
    def _reset_defaults(self):
        """Varsayılan değerlere dön"""
        if messagebox.askyesno("Varsayılanlara Dön", 
                              "Tüm ayarları varsayılan değerlere döndürmek istiyor musunuz?"):
            default_settings = ProjectSettings()
            self.settings = default_settings
            self._load_values()
    
    def _on_ok(self):
        """Tamam butonuna basıldı"""
        # Değerleri kaydet
        self.settings.project_name = self.project_name_var.get()
        self.settings.project_number = self.project_number_var.get()
        self.settings.location = self.location_var.get()
        self.settings.client = self.client_var.get()
        self.settings.engineer = self.engineer_var.get()
        
        # Standard ve hazard class'ı ayarla
        for s in DesignStandard:
            if s.value == self.standard_var.get():
                self.settings.design_standard = s
                break
        
        for h in HazardClass:
            if h.value == self.hazard_var.get():
                self.settings.hazard_class = h
                break
        
        self.settings.design_density = self.density_var.get()
        self.settings.design_area = self.area_var.get()
        self.settings.min_residual_pressure = self.residual_var.get()
        
        self.settings.default_pipe_c_factor = self.c_factor_var.get()
        self.settings.default_sprinkler_k_factor = self.k_factor_var.get()
        self.settings.default_coverage_area = self.coverage_var.get()
        self.settings.default_min_pressure = self.min_pressure_var.get()
        
        self.settings.grid_spacing = self.grid_spacing_var.get()
        self.settings.snap_to_grid = self.snap_grid_var.get()
        self.settings.length_unit = self.length_unit_var.get()
        self.settings.pressure_unit = self.pressure_unit_var.get()
        self.settings.flow_unit = self.flow_unit_var.get()
        
        self.result = self.settings
        self.destroy()
    
    def _on_cancel(self):
        """İptal butonuna basıldı"""
        self.result = None
        self.destroy()


class BatchSprinklerDialog(tk.Toplevel):
    """
    Toplu Sprinkler Ekleme Dialogu
    
    Grid pattern ile çoklu sprinkler yerleştirme.
    
    Özellikler:
    - Başlangıç noktası seçimi
    - Satır ve sütun sayısı
    - X ve Y aralıkları
    - Sprinkler özellikleri
    - Otomatik boru bağlantıları
    """
    
    def __init__(self, parent, network, start_x=0, start_y=0):
        super().__init__(parent)
        self.network = network
        self.result = None  # (nodes, pipes) tuple
        
        self.title("Toplu Sprinkler Ekleme")
        self.geometry("500x550")
        self.resizable(False, False)
        
        # Başlangıç koordinatları
        self.start_x = start_x
        self.start_y = start_y
        
        self._create_widgets()
        
        # Modal yap
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        ttk.Label(main_frame, text="Grid Pattern ile Sprinkler Yerleştirme", 
                 font=("Arial", 11, "bold")).pack(pady=(0, 15))
        
        # Grid Ayarları
        grid_frame = ttk.LabelFrame(main_frame, text="Grid Ayarları", padding=10)
        grid_frame.pack(fill=tk.X, pady=5)
        
        # Başlangıç noktası
        ttk.Label(grid_frame, text="Başlangıç X:").grid(row=0, column=0, sticky="w", pady=3)
        self.start_x_var = tk.DoubleVar(value=self.start_x)
        ttk.Entry(grid_frame, textvariable=self.start_x_var, width=12).grid(row=0, column=1, pady=3)
        ttk.Label(grid_frame, text="mm").grid(row=0, column=2, sticky="w", padx=(3,0))
        
        ttk.Label(grid_frame, text="Başlangıç Y:").grid(row=1, column=0, sticky="w", pady=3)
        self.start_y_var = tk.DoubleVar(value=self.start_y)
        ttk.Entry(grid_frame, textvariable=self.start_y_var, width=12).grid(row=1, column=1, pady=3)
        ttk.Label(grid_frame, text="mm").grid(row=1, column=2, sticky="w", padx=(3,0))
        
        # Satır ve sütun
        ttk.Label(grid_frame, text="Satır Sayısı:").grid(row=0, column=3, sticky="w", pady=3, padx=(20,0))
        self.rows_var = tk.IntVar(value=3)
        ttk.Spinbox(grid_frame, textvariable=self.rows_var, from_=1, to=20, width=8).grid(row=0, column=4, pady=3)
        
        ttk.Label(grid_frame, text="Sütun Sayısı:").grid(row=1, column=3, sticky="w", pady=3, padx=(20,0))
        self.cols_var = tk.IntVar(value=4)
        ttk.Spinbox(grid_frame, textvariable=self.cols_var, from_=1, to=20, width=8).grid(row=1, column=4, pady=3)
        
        # Aralıklar
        ttk.Label(grid_frame, text="X Aralığı:").grid(row=2, column=0, sticky="w", pady=3)
        self.spacing_x_var = tk.DoubleVar(value=3000)
        ttk.Entry(grid_frame, textvariable=self.spacing_x_var, width=12).grid(row=2, column=1, pady=3)
        ttk.Label(grid_frame, text="mm").grid(row=2, column=2, sticky="w", padx=(3,0))
        
        ttk.Label(grid_frame, text="Y Aralığı:").grid(row=3, column=0, sticky="w", pady=3)
        self.spacing_y_var = tk.DoubleVar(value=3000)
        ttk.Entry(grid_frame, textvariable=self.spacing_y_var, width=12).grid(row=3, column=1, pady=3)
        ttk.Label(grid_frame, text="mm").grid(row=3, column=2, sticky="w", padx=(3,0))
        
        # Sprinkler Özellikleri
        sprinkler_frame = ttk.LabelFrame(main_frame, text="Sprinkler Özellikleri", padding=10)
        sprinkler_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(sprinkler_frame, text="K-Faktör:").grid(row=0, column=0, sticky="w", pady=3)
        self.k_factor_var = tk.DoubleVar(value=80.0)
        ttk.Spinbox(sprinkler_frame, textvariable=self.k_factor_var, from_=50, to=200, 
                   increment=5, width=12).grid(row=0, column=1, pady=3, sticky="w")
        ttk.Label(sprinkler_frame, text="(Metrik)").grid(row=0, column=2, sticky="w", padx=(3,0))
        
        ttk.Label(sprinkler_frame, text="Min. Basınç:").grid(row=1, column=0, sticky="w", pady=3)
        self.min_pressure_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(sprinkler_frame, textvariable=self.min_pressure_var, from_=0.3, to=2.0, 
                   increment=0.1, width=12).grid(row=1, column=1, pady=3, sticky="w")
        ttk.Label(sprinkler_frame, text="bar").grid(row=1, column=2, sticky="w", padx=(3,0))
        
        ttk.Label(sprinkler_frame, text="Kaplama Alanı:").grid(row=2, column=0, sticky="w", pady=3)
        self.coverage_var = tk.DoubleVar(value=12.0)
        ttk.Spinbox(sprinkler_frame, textvariable=self.coverage_var, from_=6, to=20, 
                   increment=1, width=12).grid(row=2, column=1, pady=3, sticky="w")
        ttk.Label(sprinkler_frame, text="m²").grid(row=2, column=2, sticky="w", padx=(3,0))
        
        # Bağlantı Seçenekleri
        connection_frame = ttk.LabelFrame(main_frame, text="Bağlantı Seçenekleri", padding=10)
        connection_frame.pack(fill=tk.X, pady=5)
        
        self.create_pipes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(connection_frame, text="Otomatik boru bağlantıları oluştur", 
                       variable=self.create_pipes_var, 
                       command=self._toggle_pipe_options).pack(anchor="w")
        
        self.pipe_options_frame = ttk.Frame(connection_frame)
        self.pipe_options_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(self.pipe_options_frame, text="Boru Tipi:").grid(row=0, column=0, sticky="w", pady=3)
        self.pipe_type_var = tk.StringVar(value="Yatay")
        ttk.Combobox(self.pipe_options_frame, textvariable=self.pipe_type_var, 
                    values=["Yatay", "Dikey", "Her İkisi"], width=15, 
                    state="readonly").grid(row=0, column=1, pady=3, sticky="w")
        
        ttk.Label(self.pipe_options_frame, text="Boru Çapı:").grid(row=1, column=0, sticky="w", pady=3)
        self.pipe_diameter_var = tk.DoubleVar(value=32.0)
        ttk.Spinbox(self.pipe_options_frame, textvariable=self.pipe_diameter_var, 
                   from_=25, to=150, increment=5, width=12).grid(row=1, column=1, pady=3, sticky="w")
        ttk.Label(self.pipe_options_frame, text="mm").grid(row=1, column=2, sticky="w", padx=(3,0))
        
        # Önizleme bilgisi
        self.preview_label = ttk.Label(main_frame, text="", font=("Arial", 9), 
                                      foreground="blue")
        self.preview_label.pack(pady=10)
        self._update_preview()
        
        # Değişiklik dinleyicileri
        self.rows_var.trace_add("write", lambda *args: self._update_preview())
        self.cols_var.trace_add("write", lambda *args: self._update_preview())
        
        # Butonlar
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Oluştur", command=self._on_create, 
                  width=15).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="İptal", command=self._on_cancel, 
                  width=15).pack(side=tk.RIGHT)
    
    def _toggle_pipe_options(self):
        """Boru seçeneklerini aç/kapat"""
        if self.create_pipes_var.get():
            for child in self.pipe_options_frame.winfo_children():
                child.configure(state="normal")
        else:
            for child in self.pipe_options_frame.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Spinbox, ttk.Combobox)):
                    child.configure(state="disabled")
    
    def _update_preview(self):
        """Önizleme bilgisini güncelle"""
        rows = self.rows_var.get()
        cols = self.cols_var.get()
        total = rows * cols
        
        self.preview_label.config(
            text=f"Toplam {total} sprinkler oluşturulacak ({rows} satır × {cols} sütun)"
        )
    
    def _on_create(self):
        """Oluştur butonuna basıldı"""
        try:
            # Parametreleri al
            start_x = self.start_x_var.get()
            start_y = self.start_y_var.get()
            rows = self.rows_var.get()
            cols = self.cols_var.get()
            spacing_x = self.spacing_x_var.get()
            spacing_y = self.spacing_y_var.get()
            k_factor = self.k_factor_var.get()
            min_pressure = self.min_pressure_var.get()
            coverage = self.coverage_var.get()
            create_pipes = self.create_pipes_var.get()
            
            # Doğrulama
            if rows < 1 or cols < 1:
                messagebox.showerror("Hata", "Satır ve sütun sayısı en az 1 olmalıdır.")
                return
            
            if spacing_x <= 0 or spacing_y <= 0:
                messagebox.showerror("Hata", "Aralıklar pozitif olmalıdır.")
                return
            
            # Sprinkler'ları oluştur
            nodes = []
            for row in range(rows):
                for col in range(cols):
                    x = start_x + col * spacing_x
                    y = start_y + row * spacing_y
                    
                    node = Node(
                        node_type=NodeType.SPRINKLER,
                        coordinates=Coordinates(x, y, 0),
                        k_factor=k_factor,
                        min_pressure_required=min_pressure,
                        coverage_area=coverage
                    )
                    nodes.append(node)
            
            # Boru bağlantıları
            pipes = []
            if create_pipes:
                pipe_type = self.pipe_type_var.get()
                diameter = self.pipe_diameter_var.get()
                
                # Node indeks matrisini oluştur
                node_matrix = [[nodes[row * cols + col] for col in range(cols)] for row in range(rows)]
                
                # Yatay bağlantılar
                if pipe_type in ["Yatay", "Her İkisi"]:
                    for row in range(rows):
                        for col in range(cols - 1):
                            start_node = node_matrix[row][col]
                            end_node = node_matrix[row][col + 1]
                            
                            length = spacing_x / 1000  # mm -> m
                            
                            pipe = Pipe(
                                start_node_id=start_node.id,
                                end_node_id=end_node.id,
                                length=length,
                                internal_diameter=diameter,
                                nominal_diameter=int(diameter),
                                c_factor=120
                            )
                            pipes.append(pipe)
                
                # Dikey bağlantılar
                if pipe_type in ["Dikey", "Her İkisi"]:
                    for row in range(rows - 1):
                        for col in range(cols):
                            start_node = node_matrix[row][col]
                            end_node = node_matrix[row + 1][col]
                            
                            length = spacing_y / 1000  # mm -> m
                            
                            pipe = Pipe(
                                start_node_id=start_node.id,
                                end_node_id=end_node.id,
                                length=length,
                                internal_diameter=diameter,
                                nominal_diameter=int(diameter),
                                c_factor=120
                            )
                            pipes.append(pipe)
            
            # Sonuç
            self.result = (nodes, pipes)
            
            # Onay
            msg = f"{len(nodes)} sprinkler"
            if pipes:
                msg += f" ve {len(pipes)} boru"
            msg += " oluşturuldu."
            
            messagebox.showinfo("Başarılı", msg)
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Sprinkler oluşturulurken hata oluştu:\n{str(e)}")
    
    def _on_cancel(self):
        """İptal butonuna basıldı"""
        self.result = None
        self.destroy()


class DiameterOptimizationDialog(tk.Toplevel):
    """
    Boru Çapı Optimizasyon Dialogu
    
    Tüm boruları analiz eder ve optimal çapları önerir.
    
    Özellikler:
    - Hız bazlı optimizasyon
    - Maliyet bazlı optimizasyon
    - Seçmeli uygulama
    - Maliyet analizi
    """
    
    def __init__(self, parent, network, db):
        super().__init__(parent)
        self.network = network
        self.db = db
        self.optimizer = PipeOptimizer(network, db)
        self.results = []
        
        self.title("Boru Çapı Optimizasyonu")
        self.geometry("900x650")
        self.resizable(True, True)
        
        self._create_widgets()
        
        # Modal yap
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        ttk.Label(main_frame, text="Boru Çapı Optimizasyonu", 
                 font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Kontrol paneli
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(control_frame, text="Optimizasyon Tipi:").pack(side=tk.LEFT, padx=5)
        
        self.optimize_type_var = tk.StringVar(value="velocity")
        ttk.Radiobutton(control_frame, text="Hız Bazlı (NFPA 13)", 
                       variable=self.optimize_type_var, value="velocity").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(control_frame, text="Maliyet Bazlı", 
                       variable=self.optimize_type_var, value="cost").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Analiz Et", 
                  command=self._run_optimization).pack(side=tk.LEFT, padx=20)
        
        # Özet bilgisi
        self.summary_var = tk.StringVar(value="Analiz yapılmadı")
        ttk.Label(main_frame, textvariable=self.summary_var, 
                 font=("Arial", 9, "bold"), foreground="blue").pack(anchor="w", pady=5)
        
        # Sonuçlar tablosu
        ttk.Label(main_frame, text="Optimizasyon Önerileri:").pack(anchor="w", pady=(10,5))
        
        # Treeview
        columns = ("pipe", "current", "recommended", "velocity_before", "velocity_after", "cost", "reason")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="tree headings", height=15)
        
        self.tree.heading("#0", text="Seç")
        self.tree.heading("pipe", text="Boru ID")
        self.tree.heading("current", text="Mevcut Çap")
        self.tree.heading("recommended", text="Önerilen Çap")
        self.tree.heading("velocity_before", text="Hız (mevcut)")
        self.tree.heading("velocity_after", text="Hız (önerilen)")
        self.tree.heading("cost", text="Maliyet Farkı")
        self.tree.heading("reason", text="Neden")
        
        self.tree.column("#0", width=50)
        self.tree.column("pipe", width=80)
        self.tree.column("current", width=90)
        self.tree.column("recommended", width=100)
        self.tree.column("velocity_before", width=100)
        self.tree.column("velocity_after", width=100)
        self.tree.column("cost", width=100)
        self.tree.column("reason", width=250)
        
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Renk kodları
        self.tree.tag_configure("critical", background="#ffcccc")
        self.tree.tag_configure("increase", background="#ffffcc")
        self.tree.tag_configure("decrease", background="#ccffcc")
        
        # Maliyet özeti
        cost_frame = ttk.LabelFrame(main_frame, text="Maliyet Analizi", padding=10)
        cost_frame.pack(fill=tk.X, pady=10)
        
        self.cost_increase_var = tk.StringVar(value="₺0")
        self.cost_decrease_var = tk.StringVar(value="₺0")
        self.cost_net_var = tk.StringVar(value="₺0")
        
        ttk.Label(cost_frame, text="Artış:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(cost_frame, textvariable=self.cost_increase_var, foreground="red").grid(row=0, column=1, sticky="w")
        
        ttk.Label(cost_frame, text="Azalış:").grid(row=0, column=2, sticky="w", padx=(20,5))
        ttk.Label(cost_frame, textvariable=self.cost_decrease_var, foreground="green").grid(row=0, column=3, sticky="w")
        
        ttk.Label(cost_frame, text="Net:").grid(row=0, column=4, sticky="w", padx=(20,5))
        ttk.Label(cost_frame, textvariable=self.cost_net_var, font=("Arial", 10, "bold")).grid(row=0, column=5, sticky="w")
        
        # Alt butonlar
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Tümünü Seç", 
                  command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçimi Temizle", 
                  command=self._deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Sadece Kritik", 
                  command=self._select_critical).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Uygula", 
                  command=self._apply_selected, width=15).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Kapat", 
                  command=self.destroy, width=15).pack(side=tk.RIGHT)
        
        # Checkbox için items dictionary
        self.checkboxes = {}
    
    def _run_optimization(self):
        """Optimizasyon analizi yap"""
        optimize_type = self.optimize_type_var.get()
        
        try:
            # Önce hesaplama yapılmış mı kontrol et
            has_flow = any(p.flow_rate and p.flow_rate > 0 for p in self.network.pipes.values())
            
            if not has_flow:
                messagebox.showwarning("Uyarı", 
                    "Önce hidrolik hesaplama yapılmalıdır!\n"
                    "Hesaplama -> Hidrolik Hesapla menüsünden hesaplama yapın.")
                return
            
            # Optimizasyon yap
            self.results = self.optimizer.optimize_all_pipes(optimize_for=optimize_type)
            
            # Özet güncelle
            summary = self.optimizer.get_summary()
            summary_text = f"Toplam: {summary['total']} öneri | "
            summary_text += f"Çap artırma: {summary['increase_diameter']} | "
            summary_text += f"Çap azaltma: {summary['decrease_diameter']} | "
            summary_text += f"Kritik: {summary['critical']}"
            self.summary_var.set(summary_text)
            
            # Tabloyu doldur
            self._populate_table()
            
            # Maliyet güncelle
            self._update_cost_summary()
            
            if len(self.results) == 0:
                messagebox.showinfo("Bilgi", "Tüm borular optimal çaplarda!")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Optimizasyon hatası:\n{str(e)}")
    
    def _populate_table(self):
        """Tabloyu doldur"""
        # Temizle
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.checkboxes.clear()
        
        # Sonuçları ekle
        for result in self.results:
            # Tag belirle
            tags = []
            if "Kritik" in result.reason:
                tags.append("critical")
            elif result.recommended_diameter > result.current_diameter:
                tags.append("increase")
            else:
                tags.append("decrease")
            
            # Ekle
            item_id = self.tree.insert("", "end", 
                text="☐",  # Checkbox karakteri
                values=(
                    result.pipe_id,
                    f"{result.current_diameter:.0f} mm",
                    f"{result.recommended_diameter:.0f} mm",
                    f"{result.current_velocity:.2f} m/s",
                    f"{result.recommended_velocity:.2f} m/s",
                    f"₺{result.cost_difference:+,.0f}",
                    result.reason
                ),
                tags=tags
            )
            
            self.checkboxes[item_id] = False
        
        # Click event
        self.tree.bind("<Button-1>", self._on_tree_click)
    
    def _on_tree_click(self, event):
        """Ağaç tıklama - checkbox toggle"""
        region = self.tree.identify("region", event.x, event.y)
        if region == "tree":
            item = self.tree.identify_row(event.y)
            if item in self.checkboxes:
                # Toggle
                self.checkboxes[item] = not self.checkboxes[item]
                # Güncelle
                text = "☑" if self.checkboxes[item] else "☐"
                self.tree.item(item, text=text)
    
    def _select_all(self):
        """Tümünü seç"""
        for item in self.checkboxes:
            self.checkboxes[item] = True
            self.tree.item(item, text="☑")
    
    def _deselect_all(self):
        """Seçimi temizle"""
        for item in self.checkboxes:
            self.checkboxes[item] = False
            self.tree.item(item, text="☐")
    
    def _select_critical(self):
        """Sadece kritik olanları seç"""
        for item in self.checkboxes:
            tags = self.tree.item(item)['tags']
            if "critical" in tags:
                self.checkboxes[item] = True
                self.tree.item(item, text="☑")
            else:
                self.checkboxes[item] = False
                self.tree.item(item, text="☐")
    
    def _update_cost_summary(self):
        """Maliyet özetini güncelle"""
        increase, decrease, net = self.optimizer.get_total_cost_impact()
        
        self.cost_increase_var.set(f"₺{increase:,.0f}")
        self.cost_decrease_var.set(f"₺{decrease:,.0f}")
        
        color = "red" if net > 0 else "green" if net < 0 else "black"
        self.cost_net_var.set(f"₺{net:+,.0f}")
    
    def _apply_selected(self):
        """Seçili optimizasyonları uygula"""
        # Seçili item'ları bul
        selected_items = [item for item, checked in self.checkboxes.items() if checked]
        
        if not selected_items:
            messagebox.showwarning("Uyarı", "Lütfen uygulanacak önerileri seçin!")
            return
        
        # Pipe ID'leri al
        selected_pipe_ids = []
        for item in selected_items:
            values = self.tree.item(item)['values']
            pipe_id = values[0]
            selected_pipe_ids.append(pipe_id)
        
        # Onay al
        msg = f"{len(selected_pipe_ids)} borunun çapı değiştirilecek.\n"
        msg += "Devam etmek istiyor musunuz?"
        
        if not messagebox.askyesno("Onay", msg):
            return
        
        # Uygula
        applied_count = self.optimizer.apply_optimizations(selected_pipe_ids)
        
        messagebox.showinfo("Başarılı", 
            f"{applied_count} borunun çapı güncellendi.\n"
            "Değişikliklerin etkisini görmek için yeniden hesaplama yapın.")
        
        self.destroy()


class ReportTemplateDialog(tk.Toplevel):
    """
    Rapor Şablonu Seçim Dialogu
    
    Özellikler:
    - Rapor şablonu seçimi (NFPA, TS EN, Detaylı, vb.)
    - Proje bilgileri girişi
    - Rapor içeriği özelleştirme
    - PDF/Excel format seçimi
    - Önizleme ve kaydetme
    """
    
    def __init__(self, parent, current_settings: Optional[ReportSettings] = None):
        super().__init__(parent)
        
        self.settings = current_settings or ReportSettings()
        self.result: Optional[ReportSettings] = None
        
        # Pencere ayarları
        self.title("Rapor Ayarları ve Şablon Seçimi")
        self.geometry("700x800")
        self.minsize(600, 700)
        self.resizable(True, True)
        
        # GUI oluştur
        self._create_widgets()
        
        # Mevcut değerleri yükle
        self._load_current_settings()
        
        # Modal yap
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """GUI bileşenlerini oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # ========== SEKME 1: Proje Bilgileri ==========
        project_frame = ttk.Frame(notebook, padding="10")
        notebook.add(project_frame, text="Proje Bilgileri")
        
        row = 0
        
        # Proje Adı
        ttk.Label(project_frame, text="Proje Adı:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.project_name_var = tk.StringVar(value=self.settings.project_name)
        ttk.Entry(project_frame, textvariable=self.project_name_var, width=50).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Proje No
        ttk.Label(project_frame, text="Proje No:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.project_number_var = tk.StringVar(value=self.settings.project_number)
        ttk.Entry(project_frame, textvariable=self.project_number_var, width=50).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Müşteri
        ttk.Label(project_frame, text="Müşteri:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.client_name_var = tk.StringVar(value=self.settings.client_name)
        ttk.Entry(project_frame, textvariable=self.client_name_var, width=50).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Mühendis
        ttk.Label(project_frame, text="Mühendis:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.engineer_name_var = tk.StringVar(value=self.settings.engineer_name)
        ttk.Entry(project_frame, textvariable=self.engineer_name_var, width=50).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Standart
        ttk.Label(project_frame, text="Standart:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.standard_var = tk.StringVar(value=self.settings.standard)
        standards = ["NFPA 13", "TS EN 12845", "NFPA 13 / TS EN 12845", "FM Global"]
        ttk.Combobox(project_frame, textvariable=self.standard_var, values=standards, 
                    width=47, state="readonly").grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Tarih
        ttk.Label(project_frame, text="Tarih:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=self.settings.date)
        ttk.Entry(project_frame, textvariable=self.date_var, width=50).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Logo dosyası
        ttk.Label(project_frame, text="Şirket Logosu:").grid(row=row, column=0, sticky=tk.W, pady=5)
        logo_frame = ttk.Frame(project_frame)
        logo_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.logo_path_var = tk.StringVar(value=self.settings.company_logo_path)
        ttk.Entry(logo_frame, textvariable=self.logo_path_var, width=35).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(logo_frame, text="Gözat...", command=self._browse_logo, width=10).pack(side=tk.LEFT, padx=(5, 0))
        row += 1
        
        # Notlar
        ttk.Label(project_frame, text="Notlar:").grid(row=row, column=0, sticky=(tk.W, tk.N), pady=5)
        self.notes_text = tk.Text(project_frame, width=50, height=6, wrap=tk.WORD)
        self.notes_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        self.notes_text.insert("1.0", self.settings.notes)
        row += 1
        
        project_frame.columnconfigure(1, weight=1)
        
        # ========== SEKME 2: Şablon Seçimi ==========
        template_frame = ttk.Frame(notebook, padding="10")
        notebook.add(template_frame, text="Rapor Şablonu")
        
        # Şablon açıklaması
        desc_frame = ttk.LabelFrame(template_frame, text="Şablon Bilgisi", padding="10")
        desc_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))
        
        self.template_desc_label = ttk.Label(desc_frame, text="", wraplength=600, justify=tk.LEFT)
        self.template_desc_label.pack(fill=tk.BOTH, expand=True)
        
        # Şablon seçimi
        templates_info = [
            (ReportTemplate.NFPA_STANDARD, "NFPA 13 Standart Format",
             "NFPA 13 standartlarına uygun detaylı hesaplama raporu. "
             "Sistem özeti, düğüm/boru tabloları, hesaplama adımları ve uyumluluk kontrolü içerir."),
            
            (ReportTemplate.TSEN_STANDARD, "TS EN 12845 Standart Format",
             "TS EN 12845 standartlarına uygun hesaplama raporu. "
             "Avrupa standartları formatında, metrik birimler ve EN normlarına göre düzenlenmiştir."),
            
            (ReportTemplate.DETAILED, "Detaylı Teknik Rapor",
             "Tüm hesaplama detayları, grafikler, uyarılar ve önerileri içeren kapsamlı rapor. "
             "Mühendislik değerlendirmesi ve teknik analiz için uygundur."),
            
            (ReportTemplate.SUMMARY, "Özet Rapor",
             "Sadece temel sistem parametreleri ve sonuçları içeren kısa format rapor. "
             "Hızlı değerlendirme ve sunum için idealdir."),
            
            (ReportTemplate.CONTRACTOR, "Yüklenici Raporu",
            "Uygulama ekibi için basitleştirilmiş rapor. "
             "Malzeme listesi, boru çapları ve montaj bilgilerini içerir."),
        ]
        
        self.template_var = tk.StringVar(value=self.settings.template.value)
        
        row = 1
        for template, title, desc in templates_info:
            rb = ttk.Radiobutton(
                template_frame,
                text=title,
                variable=self.template_var,
                value=template.value,
                command=lambda d=desc: self._update_template_description(d)
            )
            rb.grid(row=row, column=0, sticky=tk.W, pady=5, padx=10)
            row += 1
        
        # İlk template'in açıklamasını göster
        self._update_template_description(templates_info[0][2])
        
        # ========== SEKME 3: İçerik Seçenekleri ==========
        content_frame = ttk.Frame(notebook, padding="10")
        notebook.add(content_frame, text="İçerik")
        
        ttk.Label(content_frame, text="Rapora Dahil Edilecek Bölümler:", 
                 font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        self.include_charts_var = tk.BooleanVar(value=self.settings.include_charts)
        ttk.Checkbutton(content_frame, text="Grafikler (Basınç-Düğüm, Debi Dağılımı)", 
                       variable=self.include_charts_var).grid(row=1, column=0, sticky=tk.W, pady=5, padx=20)
        
        self.include_calc_steps_var = tk.BooleanVar(value=self.settings.include_calculation_steps)
        ttk.Checkbutton(content_frame, text="Hesaplama Adımları (Detaylı çözüm)", 
                       variable=self.include_calc_steps_var).grid(row=2, column=0, sticky=tk.W, pady=5, padx=20)
        
        self.include_warnings_var = tk.BooleanVar(value=self.settings.include_warnings)
        ttk.Checkbutton(content_frame, text="Uyarılar ve Öneriler", 
                       variable=self.include_warnings_var).grid(row=3, column=0, sticky=tk.W, pady=5, padx=20)
        
        # İlave açıklamalar
        ttk.Separator(content_frame, orient=tk.HORIZONTAL).grid(row=4, column=0, sticky=(tk.W, tk.E), pady=20)
        
        info_label = ttk.Label(content_frame, 
            text="ℹ Seçilen şablona göre bazı içerikler otomatik olarak dahil edilir veya çıkarılır.\n"
                 "• NFPA/TS EN Standart: Hesaplama adımları zorunludur\n"
                 "• Özet Rapor: Sadece sonuç tabloları içerir\n"
                 "• Detaylı Rapor: Tüm bölümler dahildir",
            foreground="gray",
            wraplength=600,
            justify=tk.LEFT
        )
        info_label.grid(row=5, column=0, sticky=tk.W)
        
        # ========== BUTONLAR ==========
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(button_frame, text="PDF Olarak Kaydet", 
                  command=self._save_as_pdf, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Excel Olarak Kaydet", 
                  command=self._save_as_excel, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="İptal", 
                  command=self.destroy, width=15).pack(side=tk.RIGHT, padx=5)
    
    def _load_current_settings(self):
        """Mevcut ayarları form'a yükle"""
        # Değerler zaten __init__'te varsayılan olarak yükleniyor
        pass
    
    def _update_template_description(self, description: str):
        """Şablon açıklamasını güncelle"""
        self.template_desc_label.config(text=description)
    
    def _browse_logo(self):
        """Logo dosyası seç"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title="Şirket Logosu Seç",
            filetypes=[
                ("Resim Dosyaları", "*.png *.jpg *.jpeg *.bmp"),
                ("Tüm Dosyalar", "*.*")
            ]
        )
        
        if filename:
            self.logo_path_var.set(filename)
    
    def _get_settings(self) -> ReportSettings:
        """Form verilerinden ReportSettings oluştur"""
        return ReportSettings(
            project_name=self.project_name_var.get(),
            project_number=self.project_number_var.get(),
            client_name=self.client_name_var.get(),
            engineer_name=self.engineer_name_var.get(),
            standard=self.standard_var.get(),
            date=self.date_var.get(),
            notes=self.notes_text.get("1.0", tk.END).strip(),
            template=ReportTemplate(self.template_var.get()),
            include_charts=self.include_charts_var.get(),
            include_calculation_steps=self.include_calc_steps_var.get(),
            include_warnings=self.include_warnings_var.get(),
            company_logo_path=self.logo_path_var.get()
        )
    
    def _save_as_pdf(self):
        """PDF olarak kaydet"""
        self.result = self._get_settings()
        self.result.format_type = "pdf"  # Ek özellik
        self.destroy()
    
    def _save_as_excel(self):
        """Excel olarak kaydet"""
        self.result = self._get_settings()
        self.result.format_type = "excel"  # Ek özellik
        self.destroy()


class DXFImportDialog(tk.Toplevel):
    """
    DXF/DWG Import Dialogu
    
    Özellikler:
    - DXF dosyası seçimi
    - Layer listesi ve seçim
    - Önizleme (opsiyonel)
    - Ölçek ve konum ayarları
    - Arka plan olarak ekleme
    """
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.importer = DXFImporter()
        self.selected_layers: List[str] = []
        self.geometries: List[DXFGeometry] = []
        self.result: Optional[Dict] = None  # Import sonucu
        
        # Pencere ayarları
        self.title("DXF/DWG İçe Aktar")
        self.geometry("700x600")
        self.minsize(650, 550)
        self.resizable(True, True)
        
        # GUI oluştur
        self._create_widgets()
        
        # Modal yap
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """GUI bileşenlerini oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # ========== DOSYA SEÇİMİ ==========
        file_frame = ttk.LabelFrame(main_frame, text="DXF Dosyası", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="Dosya:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.filepath_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.filepath_var, state="readonly").grid(
            row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        
        ttk.Button(file_frame, text="Gözat...", command=self._browse_file, width=12).grid(
            row=0, column=2, pady=5)
        
        # Dosya bilgisi
        info_frame = ttk.Frame(file_frame)
        info_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        self.file_info_var = tk.StringVar(value="Dosya seçilmedi")
        ttk.Label(info_frame, textvariable=self.file_info_var, foreground="gray").pack(anchor=tk.W)
        
        # ========== LAYER SEÇİMİ ==========
        layer_frame = ttk.LabelFrame(main_frame, text="Layer Seçimi", padding="10")
        layer_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        layer_frame.columnconfigure(0, weight=1)
        
        # Hızlı seçim butonları
        button_frame = ttk.Frame(layer_frame)
        button_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Button(button_frame, text="Tümünü Seç", 
                  command=self._select_all_layers, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Tümünü Temizle", 
                  command=self._deselect_all_layers, width=12).pack(side=tk.LEFT, padx=2)
        
        # Layer listesi
        list_frame = ttk.Frame(layer_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.layer_listbox = tk.Listbox(list_frame, 
                                        selectmode=tk.MULTIPLE,
                                        yscrollcommand=scrollbar.set,
                                        height=8)
        self.layer_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.layer_listbox.yview)
        
        # ========== AYARLAR ==========
        settings_frame = ttk.LabelFrame(main_frame, text="İçe Aktarma Ayarları", padding="10")
        settings_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        settings_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # Ölçek
        ttk.Label(settings_frame, text="Ölçek:").grid(row=row, column=0, sticky=tk.W, pady=5)
        scale_frame = ttk.Frame(settings_frame)
        scale_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.scale_var = tk.StringVar(value="1.0")
        ttk.Entry(scale_frame, textvariable=self.scale_var, width=10).pack(side=tk.LEFT)
        ttk.Label(scale_frame, text=" (1.0 = Otomatik sığdır)", foreground="gray").pack(side=tk.LEFT, padx=(5, 0))
        row += 1
        
        # Opacity
        ttk.Label(settings_frame, text="Opaklık:").grid(row=row, column=0, sticky=tk.W, pady=5)
        opacity_frame = ttk.Frame(settings_frame)
        opacity_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.opacity_var = tk.DoubleVar(value=0.3)
        opacity_scale = ttk.Scale(opacity_frame, from_=0.1, to=1.0, 
                                 variable=self.opacity_var, orient=tk.HORIZONTAL)
        opacity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.opacity_label = ttk.Label(opacity_frame, text="30%")
        self.opacity_label.pack(side=tk.LEFT, padx=(10, 0))
        
        opacity_scale.config(command=self._update_opacity_label)
        row += 1
        
        # Renk
        ttk.Label(settings_frame, text="Renk:").grid(row=row, column=0, sticky=tk.W, pady=5)
        color_frame = ttk.Frame(settings_frame)
        color_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.color_var = tk.StringVar(value="#808080")
        colors = [
            ("Gri", "#808080"),
            ("Açık Gri", "#C0C0C0"),
            ("Siyah", "#000000"),
            ("Mavi", "#0000FF"),
            ("Yeşil", "#00FF00"),
        ]
        
        for i, (label, color) in enumerate(colors):
            ttk.Radiobutton(color_frame, text=label, 
                          variable=self.color_var, value=color).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Arka plan olarak ekle
        self.as_background_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Arka plan olarak ekle (düzenlenemez)", 
                       variable=self.as_background_var).grid(row=row, column=0, columnspan=2, 
                                                            sticky=tk.W, pady=10)
        
        # ========== BUTONLAR ==========
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(button_frame, text="İçe Aktar", 
                  command=self._import_dxf, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="İptal", 
                  command=self.destroy, width=15).pack(side=tk.RIGHT, padx=5)
    
    def _browse_file(self):
        """DXF dosyası seç"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title="DXF Dosyası Seç",
            filetypes=[
                ("DXF Dosyaları", "*.dxf"),
                ("DWG Dosyaları", "*.dwg"),
                ("Tüm Dosyalar", "*.*")
            ]
        )
        
        if filename:
            self._load_dxf(filename)
    
    def _load_dxf(self, filepath: str):
        """DXF dosyasını yükle"""
        try:
            if self.importer.load_file(filepath):
                self.filepath_var.set(filepath)
                
                # Dosya bilgisi
                info = f"Layer: {len(self.importer.layers)}"
                if self.importer.bounds:
                    info += f" | Boyut: {self.importer.bounds.width:.0f} x {self.importer.bounds.height:.0f}"
                self.file_info_var.set(info)
                
                # Layer'ları listele
                self._populate_layers()
                
            else:
                messagebox.showerror("Hata", "DXF dosyası yüklenemedi!")
                
        except Exception as e:
            messagebox.showerror("Hata", f"DXF yükleme hatası:\n{str(e)}")
    
    def _populate_layers(self):
        """Layer listesini doldur"""
        self.layer_listbox.delete(0, tk.END)
        
        for layer in self.importer.layers:
            display = f"{layer.name} ({layer.entity_count} entity)"
            self.layer_listbox.insert(tk.END, display)
            
            # İlk layer'ı varsayılan olarak seç
            if len(self.importer.layers) > 0:
                self.layer_listbox.selection_set(0)
    
    def _select_all_layers(self):
        """Tüm layer'ları seç"""
        self.layer_listbox.selection_set(0, tk.END)
    
    def _deselect_all_layers(self):
        """Tüm seçimleri temizle"""
        self.layer_listbox.selection_clear(0, tk.END)
    
    def _update_opacity_label(self, value):
        """Opaklık etiketini güncelle"""
        self.opacity_label.config(text=f"{int(float(value) * 100)}%")
    
    def _import_dxf(self):
        """DXF'i içe aktar"""
        # Seçili layer'ları al
        selected_indices = self.layer_listbox.curselection()
        
        if not selected_indices:
            messagebox.showwarning("Uyarı", "Lütfen en az bir layer seçin!")
            return
        
        self.selected_layers = [self.importer.layers[i].name for i in selected_indices]
        
        # Geometrileri çıkart
        self.geometries = self.importer.extract_geometries(self.selected_layers)
        
        if not self.geometries:
            messagebox.showwarning("Uyarı", "Seçili layer'larda geometri bulunamadı!")
            return
        
        # Sonuç hazırla
        try:
            scale = float(self.scale_var.get())
        except ValueError:
            scale = 1.0
        
        self.result = {
            'importer': self.importer,
            'geometries': self.geometries,
            'selected_layers': self.selected_layers,
            'scale': scale,
            'opacity': self.opacity_var.get(),
            'color': self.color_var.get(),
            'as_background': self.as_background_var.get()
        }
        
        messagebox.showinfo("Başarılı", 
            f"{len(self.geometries)} geometrik obje içe aktarıldı.\n"
            f"Layer: {', '.join(self.selected_layers)}")
        
        self.destroy()
