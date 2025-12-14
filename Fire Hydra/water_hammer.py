"""
Water Hammer Analysis Module - Transient Flow Analysis
FireHydra - Yangın Söndürme Sistemi Hidrolik Hesaplama
"""

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math


@dataclass
class WaterHammerResult:
    """Su darbesi analiz sonucu"""
    max_pressure: float  # Bar
    min_pressure: float  # Bar
    pressure_wave_velocity: float  # m/s
    critical_time: float  # saniye
    severity: str  # 'Low', 'Medium', 'High', 'Critical'
    recommendations: List[str]
    pipe_results: Dict[str, Dict]  # Boru bazlı sonuçlar


class WaterHammerAnalyzer:
    """Su darbesi analiz motoru"""
    
    def __init__(self, network, solver_results=None):
        self.network = network
        self.solver_results = solver_results
        
        # Sabitler
        self.WATER_BULK_MODULUS = 2.2e9  # Pa (su sıkıştırma modülü)
        self.WATER_DENSITY = 1000  # kg/m³
        self.STEEL_ELASTIC_MODULUS = 2.0e11  # Pa (çelik elastik modülü)
    
    def analyze(self, valve_closure_time: float = 1.0, 
                pump_trip_time: float = 0.5) -> WaterHammerResult:
        """
        Su darbesi analizi yap
        
        Args:
            valve_closure_time: Valf kapanma süresi (saniye)
            pump_trip_time: Pompa durma süresi (saniye)
        """
        try:
            # Basınç dalga hızını hesapla
            wave_velocity = self._calculate_wave_velocity()
            
            # Kritik süreyi hesapla (Joukowsky formülü)
            critical_time = self._calculate_critical_time(wave_velocity)
            
            # Boru bazlı analizler
            pipe_results = {}
            max_surge_pressure = 0
            min_pressure = float('inf')
            
            for pipe in self.network.pipes:
                result = self._analyze_pipe(pipe, wave_velocity, valve_closure_time)
                pipe_results[pipe.id] = result
                
                max_surge_pressure = max(max_surge_pressure, result['surge_pressure'])
                min_pressure = min(min_pressure, result['min_pressure'])
            
            # Şiddet seviyesini belirle
            severity, recommendations = self._evaluate_severity(
                max_surge_pressure, min_pressure, critical_time, 
                valve_closure_time, pump_trip_time
            )
            
            return WaterHammerResult(
                max_pressure=max_surge_pressure,
                min_pressure=min_pressure,
                pressure_wave_velocity=wave_velocity,
                critical_time=critical_time,
                severity=severity,
                recommendations=recommendations,
                pipe_results=pipe_results
            )
            
        except Exception as e:
            raise Exception(f"Su darbesi analiz hatası: {str(e)}")
    
    def _calculate_wave_velocity(self) -> float:
        """
        Basınç dalga hızını hesapla
        
        Joukowsky formülü: a = sqrt(K / (ρ * (1 + (K*D)/(E*t))))
        K: Su sıkıştırma modülü
        ρ: Su yoğunluğu
        D: Boru iç çapı
        E: Boru malzemesi elastik modülü
        t: Boru et kalınlığı
        """
        # Ortalama boru özelliklerini kullan
        if not self.network.pipes:
            return 1000  # Varsayılan değer
        
        # İlk borudan parametreler al (basitleştirilmiş)
        avg_diameter = sum(p.diameter_mm for p in self.network.pipes) / len(self.network.pipes) / 1000  # m
        
        # Standart Schedule 40 boru için et kalınlığı yaklaşımı
        wall_thickness = avg_diameter * 0.1  # Yaklaşık %10
        
        # Dalga hızı hesabı
        k_over_rho = self.WATER_BULK_MODULUS / self.WATER_DENSITY
        k_d_over_e_t = (self.WATER_BULK_MODULUS * avg_diameter) / (self.STEEL_ELASTIC_MODULUS * wall_thickness)
        
        wave_velocity = math.sqrt(k_over_rho / (1 + k_d_over_e_t))
        
        return wave_velocity
    
    def _calculate_critical_time(self, wave_velocity: float) -> float:
        """
        Kritik zamanı hesapla
        
        t_c = 2L / a
        L: Boru uzunluğu
        a: Dalga hızı
        """
        if not self.network.pipes:
            return 0
        
        # En uzun boru hattını bul
        max_length = max(p.length for p in self.network.pipes)
        
        # Toplam hat uzunluğu (yaklaşık)
        total_length = sum(p.length for p in self.network.pipes)
        
        # Kritik süre (en uzun boru için)
        critical_time = (2 * max_length) / wave_velocity
        
        return critical_time
    
    def _analyze_pipe(self, pipe, wave_velocity: float, 
                     closure_time: float) -> Dict:
        """Tek bir boru için su darbesi analizi"""
        
        # Boru hızını al (hesaplama yapılmışsa)
        if hasattr(pipe, 'velocity') and pipe.velocity:
            velocity = pipe.velocity  # m/s
        else:
            # Tahmini hız (varsayılan: 2 m/s)
            velocity = 2.0
        
        # Joukowsky basınç artışı
        # ΔP = ρ * a * ΔV
        delta_v = velocity  # Hız değişimi (tam kapanma)
        
        # Pascal cinsinden basınç artışı
        surge_pressure_pa = self.WATER_DENSITY * wave_velocity * delta_v
        
        # Bar'a çevir
        surge_pressure_bar = surge_pressure_pa / 1e5
        
        # Mevcut işletme basıncı (hesaplama sonucundan veya varsayılan)
        if self.solver_results and hasattr(pipe, 'pressure'):
            operating_pressure = getattr(pipe, 'pressure', 5.0)
        else:
            operating_pressure = 5.0  # Bar (varsayılan)
        
        # Maksimum ve minimum basınçlar
        max_pressure = operating_pressure + surge_pressure_bar
        min_pressure = operating_pressure - surge_pressure_bar
        
        # Boru kritik süresi
        pipe_critical_time = (2 * pipe.length) / wave_velocity
        
        # Kapanma tipi (ani mi, yavaş mı?)
        if closure_time < pipe_critical_time:
            closure_type = "Ani Kapanma (Rapid Closure)"
            surge_factor = 1.0  # Tam Joukowsky etkisi
        else:
            closure_type = "Yavaş Kapanma (Slow Closure)"
            surge_factor = pipe_critical_time / closure_time  # Azaltılmış etki
        
        # Düzeltilmiş basınç artışı
        adjusted_surge = surge_pressure_bar * surge_factor
        adjusted_max = operating_pressure + adjusted_surge
        adjusted_min = operating_pressure - adjusted_surge
        
        return {
            'surge_pressure': adjusted_max,
            'min_pressure': max(0, adjusted_min),  # Negatif olamaz
            'pressure_rise': adjusted_surge,
            'velocity': velocity,
            'critical_time': pipe_critical_time,
            'closure_type': closure_type,
            'surge_factor': surge_factor
        }
    
    def _evaluate_severity(self, max_pressure: float, min_pressure: float,
                          critical_time: float, valve_time: float,
                          pump_time: float) -> Tuple[str, List[str]]:
        """Şiddet seviyesini ve önerileri belirle"""
        
        recommendations = []
        
        # Basınç değerlendirmesi
        if max_pressure > 16:  # 16 Bar üzeri
            severity = "Critical"
            recommendations.append("⚠️ KRİTİK: Maksimum basınç çok yüksek! Acil koruma gerekli.")
            recommendations.append("• Surge tankı (hidrofor) kurulumu zorunlu")
            recommendations.append("• Yavaş kapanan valf kullanın (min 5 saniye)")
            recommendations.append("• Basınç kırıcı valf ekleyin")
            
        elif max_pressure > 12:  # 12-16 Bar arası
            severity = "High"
            recommendations.append("⚠️ YÜKSEK RİSK: Su darbesi riski yüksek")
            recommendations.append("• Surge koruma sistemi önerilir")
            recommendations.append("• Valf kapanma süresini artırın (3+ saniye)")
            recommendations.append("• Hava valfleri ekleyin")
            
        elif max_pressure > 10:  # 10-12 Bar arası
            severity = "Medium"
            recommendations.append("⚠ ORTA RİSK: Su darbesi önlemleri alınmalı")
            recommendations.append("• Yavaş kapanan valfler kullanın (2+ saniye)")
            recommendations.append("• Hava valfleri düşünülebilir")
            
        else:
            severity = "Low"
            recommendations.append("✓ DÜŞÜK RİSK: Su darbesi etkisi kabul edilebilir seviyede")
            recommendations.append("• Standart valfler yeterli")
        
        # Minimum basınç kontrolü
        if min_pressure < 0:
            recommendations.append("⚠️ UYARI: Negatif basınç riski - Kavitasyon olabilir!")
            recommendations.append("• Hava valfleri mutlaka ekleyin")
            recommendations.append("• Vakum kırıcı valf düşünün")
            if severity == "Low":
                severity = "Medium"
        
        # Kritik süre kontrolü
        if valve_time < critical_time:
            recommendations.append(f"⚠ Valf kapanma süresi ({valve_time:.2f}s) kritik sürenin ({critical_time:.2f}s) altında!")
            recommendations.append(f"• Valf kapanma süresini en az {critical_time*1.5:.2f} saniyeye çıkarın")
        
        # Genel öneriler
        recommendations.append("\n📋 GENEL ÖNERİLER:")
        recommendations.append("• Tüm borular basınç sınıfına uygun seçilmeli")
        recommendations.append("• Kritik noktalara basınç göstergesi yerleştirin")
        recommendations.append("• Düzenli bakım ve kontrol yapın")
        recommendations.append("• Operatörleri su darbesi riskleri konusunda eğitin")
        
        return severity, recommendations


class WaterHammerDialog(tk.Toplevel):
    """Su darbesi analiz dialogu"""
    
    def __init__(self, parent, network, solver_results=None):
        super().__init__(parent)
        self.network = network
        self.solver_results = solver_results
        self.result = None
        
        self.title("Su Darbesi (Water Hammer) Analizi")
        self.geometry("900x700")
        
        # Modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Merkeze al
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Üst kısım: Parametreler
        param_frame = ttk.LabelFrame(main_frame, text="Analiz Parametreleri", padding=10)
        param_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Valf kapanma süresi
        ttk.Label(param_frame, text="Valf Kapanma Süresi (saniye):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.valve_time_var = tk.DoubleVar(value=1.0)
        ttk.Entry(param_frame, textvariable=self.valve_time_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(param_frame, text="(Önerilen: >2 saniye)").grid(row=0, column=2, sticky=tk.W)
        
        # Pompa durma süresi
        ttk.Label(param_frame, text="Pompa Durma Süresi (saniye):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.pump_time_var = tk.DoubleVar(value=0.5)
        ttk.Entry(param_frame, textvariable=self.pump_time_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(param_frame, text="(Elektrik kesintisi durumu)").grid(row=1, column=2, sticky=tk.W)
        
        # Analiz butonu
        ttk.Button(param_frame, text="Analizi Başlat", 
                  command=self._run_analysis).grid(row=2, column=0, columnspan=3, pady=10)
        
        # Orta kısım: Sonuçlar özeti
        summary_frame = ttk.LabelFrame(main_frame, text="Analiz Sonuçları", padding=10)
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Sonuç grid
        self.result_labels = {}
        
        labels = [
            ("Maksimum Basınç:", "max_pressure"),
            ("Minimum Basınç:", "min_pressure"),
            ("Dalga Hızı:", "wave_velocity"),
            ("Kritik Süre:", "critical_time"),
            ("Şiddet Seviyesi:", "severity")
        ]
        
        for row, (label, key) in enumerate(labels):
            ttk.Label(summary_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=3)
            value_label = ttk.Label(summary_frame, text="-", font=('Arial', 10, 'bold'))
            value_label.grid(row=row, column=1, sticky=tk.W, padx=10)
            self.result_labels[key] = value_label
        
        # Alt kısım: Detaylı sonuçlar ve öneriler
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Boru sonuçları sekmesi
        pipe_frame = ttk.Frame(notebook, padding=10)
        notebook.add(pipe_frame, text="Boru Bazlı Sonuçlar")
        
        # Boru sonuçları tablosu
        columns = ('pipe_id', 'max_pressure', 'min_pressure', 'surge', 'velocity', 'closure_type')
        self.pipe_tree = ttk.Treeview(pipe_frame, columns=columns, show='headings', height=10)
        
        self.pipe_tree.heading('pipe_id', text='Boru ID')
        self.pipe_tree.heading('max_pressure', text='Max Basınç (Bar)')
        self.pipe_tree.heading('min_pressure', text='Min Basınç (Bar)')
        self.pipe_tree.heading('surge', text='Basınç Artışı (Bar)')
        self.pipe_tree.heading('velocity', text='Hız (m/s)')
        self.pipe_tree.heading('closure_type', text='Kapanma Tipi')
        
        self.pipe_tree.column('pipe_id', width=100)
        self.pipe_tree.column('max_pressure', width=120)
        self.pipe_tree.column('min_pressure', width=120)
        self.pipe_tree.column('surge', width=130)
        self.pipe_tree.column('velocity', width=100)
        self.pipe_tree.column('closure_type', width=200)
        
        scrollbar = ttk.Scrollbar(pipe_frame, orient=tk.VERTICAL, command=self.pipe_tree.yview)
        self.pipe_tree.configure(yscrollcommand=scrollbar.set)
        
        self.pipe_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Öneriler sekmesi
        rec_frame = ttk.Frame(notebook, padding=10)
        notebook.add(rec_frame, text="Öneriler ve Koruma")
        
        # Öneriler text widget
        self.recommendations_text = tk.Text(rec_frame, wrap=tk.WORD, height=15, width=80)
        rec_scrollbar = ttk.Scrollbar(rec_frame, orient=tk.VERTICAL, command=self.recommendations_text.yview)
        self.recommendations_text.configure(yscrollcommand=rec_scrollbar.set)
        
        self.recommendations_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rec_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Butonlar
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Rapor Oluştur", 
                  command=self._generate_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Kapat", 
                  command=self.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _run_analysis(self):
        """Analizi çalıştır"""
        try:
            valve_time = self.valve_time_var.get()
            pump_time = self.pump_time_var.get()
            
            if valve_time <= 0 or pump_time <= 0:
                messagebox.showerror("Hata", "Süreler pozitif olmalıdır!")
                return
            
            # Analiz yap
            analyzer = WaterHammerAnalyzer(self.network, self.solver_results)
            result = analyzer.analyze(valve_time, pump_time)
            
            self.result = result
            
            # Sonuçları göster
            self._display_results(result)
            
        except Exception as e:
            messagebox.showerror("Analiz Hatası", f"Analiz sırasında hata oluştu:\n{str(e)}")
    
    def _display_results(self, result: WaterHammerResult):
        """Sonuçları göster"""
        # Özet değerleri güncelle
        self.result_labels['max_pressure'].config(text=f"{result.max_pressure:.2f} Bar")
        self.result_labels['min_pressure'].config(text=f"{result.min_pressure:.2f} Bar")
        self.result_labels['wave_velocity'].config(text=f"{result.pressure_wave_velocity:.1f} m/s")
        self.result_labels['critical_time'].config(text=f"{result.critical_time:.3f} saniye")
        
        # Şiddet seviyesi (renkli)
        severity_colors = {
            'Low': 'green',
            'Medium': 'orange',
            'High': 'red',
            'Critical': 'darkred'
        }
        self.result_labels['severity'].config(
            text=result.severity,
            foreground=severity_colors.get(result.severity, 'black')
        )
        
        # Boru tablosunu doldur
        for item in self.pipe_tree.get_children():
            self.pipe_tree.delete(item)
        
        for pipe_id, data in result.pipe_results.items():
            self.pipe_tree.insert('', tk.END, values=(
                pipe_id,
                f"{data['surge_pressure']:.2f}",
                f"{data['min_pressure']:.2f}",
                f"{data['pressure_rise']:.2f}",
                f"{data['velocity']:.2f}",
                data['closure_type']
            ))
        
        # Önerileri göster
        self.recommendations_text.delete('1.0', tk.END)
        self.recommendations_text.insert('1.0', '\n'.join(result.recommendations))
    
    def _generate_report(self):
        """Rapor oluştur"""
        if not self.result:
            messagebox.showwarning("Uyarı", "Önce analiz yapmalısınız!")
            return
        
        # Basit text raporu
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("SU DARBESİ (WATER HAMMER) ANALİZ RAPORU")
        report_lines.append("=" * 70)
        report_lines.append("")
        report_lines.append(f"Analiz Tarihi: {tk.datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
        report_lines.append(f"Proje: {self.network.project_name}")
        report_lines.append("")
        report_lines.append("SONUÇLAR:")
        report_lines.append("-" * 70)
        report_lines.append(f"Maksimum Basınç: {self.result.max_pressure:.2f} Bar")
        report_lines.append(f"Minimum Basınç: {self.result.min_pressure:.2f} Bar")
        report_lines.append(f"Dalga Hızı: {self.result.pressure_wave_velocity:.1f} m/s")
        report_lines.append(f"Kritik Süre: {self.result.critical_time:.3f} saniye")
        report_lines.append(f"Şiddet Seviyesi: {self.result.severity}")
        report_lines.append("")
        report_lines.append("ÖNERİLER:")
        report_lines.append("-" * 70)
        report_lines.extend(self.result.recommendations)
        
        report_text = '\n'.join(report_lines)
        
        # Raporu göster (yeni pencere)
        report_window = tk.Toplevel(self)
        report_window.title("Su Darbesi Raporu")
        report_window.geometry("800x600")
        
        text_widget = tk.Text(report_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert('1.0', report_text)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(report_window, text="Kapat", 
                  command=report_window.destroy).pack(pady=5)


def show_water_hammer_analysis(parent, network, solver_results=None):
    """Su darbesi analiz dialogunu göster"""
    dialog = WaterHammerDialog(parent, network, solver_results)
    parent.wait_window(dialog)
    return dialog.result
