"""
Network Analysis Dashboard

Gerçek zamanlı sistem analizi ve görselleştirme:
- Toplam akış (flow rate)
- Basınç düşümü (pressure drop)
- Pompa gücü (pump power)
- Hata/uyarı sayısı
- Grafik ve gauge göstergeler
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import math


class DashboardPosition(Enum):
    """Dashboard pozisyon seçenekleri"""
    LEFT = "left"
    RIGHT = "right"
    BOTTOM = "bottom"
    FLOATING = "floating"


@dataclass
class NetworkStats:
    """Network istatistikleri"""
    total_flow: float = 0.0  # L/min
    total_pressure_drop: float = 0.0  # bar
    pump_power: float = 0.0  # kW
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # Detaylar
    total_length: float = 0.0  # m
    total_sprinklers: int = 0
    avg_velocity: float = 0.0  # m/s
    max_velocity: float = 0.0  # m/s
    min_pressure: float = 0.0  # bar
    max_pressure: float = 0.0  # bar


class GaugeWidget(tk.Canvas):
    """
    Gauge gösterge widget'ı
    
    Dairesel gauge ile değer gösterimi
    """
    
    def __init__(self, parent, width=150, height=150, **kwargs):
        super().__init__(parent, width=width, height=height, 
                        bg='white', highlightthickness=0, **kwargs)
        
        self.width = width
        self.height = height
        self.value = 0.0
        self.min_value = 0.0
        self.max_value = 100.0
        self.unit = ""
        self.title = ""
        
        self.colors = {
            'bg': '#f0f0f0',
            'arc_bg': '#e0e0e0',
            'arc_fill': '#4CAF50',
            'warning': '#FF9800',
            'critical': '#F44336',
            'text': '#333333'
        }
        
        self._draw()
    
    def set_value(self, value: float, min_val: float = 0, max_val: float = 100, 
                  unit: str = "", title: str = ""):
        """Değeri güncelle"""
        self.value = max(min_val, min(max_val, value))
        self.min_value = min_val
        self.max_value = max_val
        self.unit = unit
        self.title = title
        self._draw()
    
    def _draw(self):
        """Gauge çiz"""
        self.delete('all')
        
        # Merkez ve yarıçap
        cx = self.width / 2
        cy = self.height / 2
        radius = min(cx, cy) - 20
        
        # Başlık
        if self.title:
            self.create_text(cx, 15, text=self.title, 
                           font=('Arial', 10, 'bold'), fill=self.colors['text'])
        
        # Arka plan arc (gri)
        self.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                       start=0, extent=180, style=tk.ARC, width=15,
                       outline=self.colors['arc_bg'])
        
        # Değer yüzdesi
        if self.max_value > self.min_value:
            percent = (self.value - self.min_value) / (self.max_value - self.min_value)
        else:
            percent = 0
        
        extent = 180 * percent
        
        # Renk seçimi
        if percent > 0.9:
            color = self.colors['critical']
        elif percent > 0.7:
            color = self.colors['warning']
        else:
            color = self.colors['arc_fill']
        
        # Değer arc
        self.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                       start=0, extent=extent, style=tk.ARC, width=15,
                       outline=color)
        
        # Değer metni
        value_text = f"{self.value:.1f}"
        self.create_text(cx, cy - 10, text=value_text,
                        font=('Arial', 20, 'bold'), fill=self.colors['text'])
        
        # Birim
        if self.unit:
            self.create_text(cx, cy + 15, text=self.unit,
                           font=('Arial', 9), fill='gray')
        
        # Min/Max etiketleri
        self.create_text(cx - radius - 5, cy + 5, text=f"{self.min_value:.0f}",
                        font=('Arial', 8), fill='gray', anchor=tk.E)
        self.create_text(cx + radius + 5, cy + 5, text=f"{self.max_value:.0f}",
                        font=('Arial', 8), fill='gray', anchor=tk.W)


class SparklineWidget(tk.Canvas):
    """
    Sparkline grafik widget'ı
    
    Küçük trend grafiği gösterimi
    """
    
    def __init__(self, parent, width=200, height=60, **kwargs):
        super().__init__(parent, width=width, height=height,
                        bg='white', highlightthickness=1, 
                        highlightbackground='#ddd', **kwargs)
        
        self.width = width
        self.height = height
        self.data: List[float] = []
        self.max_points = 50
        self.color = '#2196F3'
        
    def add_point(self, value: float):
        """Yeni veri noktası ekle"""
        self.data.append(value)
        
        # Maksimum nokta sayısını aş
        if len(self.data) > self.max_points:
            self.data.pop(0)
        
        self._draw()
    
    def set_data(self, data: List[float]):
        """Tüm veriyi ayarla"""
        self.data = data[-self.max_points:] if len(data) > self.max_points else data.copy()
        self._draw()
    
    def clear(self):
        """Veriyi temizle"""
        self.data.clear()
        self.delete('all')
    
    def _draw(self):
        """Sparkline çiz"""
        self.delete('all')
        
        if len(self.data) < 2:
            return
        
        # Padding
        pad_x = 10
        pad_y = 10
        
        # Min/max değerler
        min_val = min(self.data)
        max_val = max(self.data)
        
        # Aynı değerler için range
        if max_val == min_val:
            max_val = min_val + 1
        
        # Ölçekleme
        scale_x = (self.width - 2 * pad_x) / (len(self.data) - 1)
        scale_y = (self.height - 2 * pad_y) / (max_val - min_val)
        
        # Noktalar
        points = []
        for i, value in enumerate(self.data):
            x = pad_x + i * scale_x
            y = self.height - pad_y - (value - min_val) * scale_y
            points.extend([x, y])
        
        # Çizgi çiz
        if len(points) >= 4:
            self.create_line(points, fill=self.color, width=2, smooth=True)
        
        # Dolgu alanı (opsiyonel)
        if len(points) >= 4:
            fill_points = points.copy()
            fill_points.extend([self.width - pad_x, self.height - pad_y])
            fill_points.extend([pad_x, self.height - pad_y])
            
            self.create_polygon(fill_points, fill=self.color, 
                              stipple='gray25', outline='')


class NetworkDashboard(ttk.Frame):
    """
    Network Analysis Dashboard
    
    Gerçek zamanlı sistem analizi paneli
    """
    
    def __init__(self, parent, position: DashboardPosition = DashboardPosition.RIGHT):
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)
        
        self.position = position
        self.stats = NetworkStats()
        
        # Sparkline veri geçmişi
        self.flow_history: List[float] = []
        self.pressure_history: List[float] = []
        
        # Widgets
        self.gauges: Dict[str, GaugeWidget] = {}
        self.sparklines: Dict[str, SparklineWidget] = {}
        self.labels: Dict[str, ttk.Label] = {}
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Dashboard widget'larını oluştur"""
        # Header
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(header, text="📊 Network Analysis", 
                 font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        
        # Refresh butonu
        ttk.Button(header, text="🔄", width=3, 
                  command=self._on_refresh).pack(side=tk.RIGHT)
        
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # ========== GAUGES ==========
        gauge_frame = ttk.LabelFrame(self, text="Sistem Durumu", padding=10)
        gauge_frame.pack(fill=tk.BOTH, padx=5, pady=5)
        
        # Flow gauge
        self.gauges['flow'] = GaugeWidget(gauge_frame, width=140, height=140)
        self.gauges['flow'].grid(row=0, column=0, padx=10, pady=10)
        
        # Pressure gauge
        self.gauges['pressure'] = GaugeWidget(gauge_frame, width=140, height=140)
        self.gauges['pressure'].grid(row=0, column=1, padx=10, pady=10)
        
        # Power gauge
        self.gauges['power'] = GaugeWidget(gauge_frame, width=140, height=140)
        self.gauges['power'].grid(row=1, column=0, padx=10, pady=10)
        
        # Velocity gauge
        self.gauges['velocity'] = GaugeWidget(gauge_frame, width=140, height=140)
        self.gauges['velocity'].grid(row=1, column=1, padx=10, pady=10)
        
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # ========== SPARKLINES ==========
        sparkline_frame = ttk.LabelFrame(self, text="Trend Grafikleri", padding=10)
        sparkline_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(sparkline_frame, text="Akış:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sparklines['flow'] = SparklineWidget(sparkline_frame, width=180, height=50)
        self.sparklines['flow'].grid(row=0, column=1, pady=2, padx=5)
        
        ttk.Label(sparkline_frame, text="Basınç:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.sparklines['pressure'] = SparklineWidget(sparkline_frame, width=180, height=50)
        self.sparklines['pressure'].grid(row=1, column=1, pady=2, padx=5)
        
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # ========== VALIDATION STATUS ==========
        status_frame = ttk.LabelFrame(self, text="Doğrulama Durumu", padding=10)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Hata sayısı
        error_frame = ttk.Frame(status_frame)
        error_frame.pack(fill=tk.X, pady=2)
        ttk.Label(error_frame, text="❌ Hatalar:", foreground='red').pack(side=tk.LEFT)
        self.labels['errors'] = ttk.Label(error_frame, text="0", 
                                          font=('Arial', 10, 'bold'), foreground='red')
        self.labels['errors'].pack(side=tk.RIGHT)
        
        # Uyarı sayısı
        warning_frame = ttk.Frame(status_frame)
        warning_frame.pack(fill=tk.X, pady=2)
        ttk.Label(warning_frame, text="⚠️ Uyarılar:", foreground='orange').pack(side=tk.LEFT)
        self.labels['warnings'] = ttk.Label(warning_frame, text="0",
                                           font=('Arial', 10, 'bold'), foreground='orange')
        self.labels['warnings'].pack(side=tk.RIGHT)
        
        # Bilgi sayısı
        info_frame = ttk.Frame(status_frame)
        info_frame.pack(fill=tk.X, pady=2)
        ttk.Label(info_frame, text="ℹ️ Bilgiler:", foreground='blue').pack(side=tk.LEFT)
        self.labels['info'] = ttk.Label(info_frame, text="0",
                                       font=('Arial', 10, 'bold'), foreground='blue')
        self.labels['info'].pack(side=tk.RIGHT)
        
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # ========== NETWORK DETAILS ==========
        details_frame = ttk.LabelFrame(self, text="Network Detayları", padding=10)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_detail_row(details_frame, "Toplam Uzunluk:", "length", "m", 0)
        self._create_detail_row(details_frame, "Sprinkler Sayısı:", "sprinklers", "adet", 1)
        self._create_detail_row(details_frame, "Ort. Hız:", "avg_vel", "m/s", 2)
        self._create_detail_row(details_frame, "Max Hız:", "max_vel", "m/s", 3)
        self._create_detail_row(details_frame, "Min Basınç:", "min_press", "bar", 4)
        self._create_detail_row(details_frame, "Max Basınç:", "max_press", "bar", 5)
    
    def _create_detail_row(self, parent, label_text: str, key: str, unit: str, row: int):
        """Detay satırı oluştur"""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=2)
        
        value_label = ttk.Label(parent, text=f"0.0 {unit}", 
                               font=('Arial', 9, 'bold'))
        value_label.grid(row=row, column=1, sticky=tk.E, pady=2)
        
        self.labels[key] = value_label
    
    def update_stats(self, stats: NetworkStats):
        """İstatistikleri güncelle"""
        self.stats = stats
        
        # Gauges güncelle
        self.gauges['flow'].set_value(
            stats.total_flow, 0, 2000, "L/min", "Toplam Akış"
        )
        
        self.gauges['pressure'].set_value(
            stats.total_pressure_drop, 0, 10, "bar", "Basınç Düşümü"
        )
        
        self.gauges['power'].set_value(
            stats.pump_power, 0, 100, "kW", "Pompa Gücü"
        )
        
        self.gauges['velocity'].set_value(
            stats.max_velocity, 0, 10, "m/s", "Max Hız"
        )
        
        # Sparklines güncelle
        self.flow_history.append(stats.total_flow)
        self.pressure_history.append(stats.total_pressure_drop)
        
        self.sparklines['flow'].set_data(self.flow_history)
        self.sparklines['pressure'].set_data(self.pressure_history)
        
        # Validation status
        self.labels['errors'].config(text=str(stats.error_count))
        self.labels['warnings'].config(text=str(stats.warning_count))
        self.labels['info'].config(text=str(stats.info_count))
        
        # Network details
        self.labels['length'].config(text=f"{stats.total_length:.1f} m")
        self.labels['sprinklers'].config(text=f"{stats.total_sprinklers} adet")
        self.labels['avg_vel'].config(text=f"{stats.avg_velocity:.2f} m/s")
        self.labels['max_vel'].config(text=f"{stats.max_velocity:.2f} m/s")
        self.labels['min_press'].config(text=f"{stats.min_pressure:.2f} bar")
        self.labels['max_press'].config(text=f"{stats.max_pressure:.2f} bar")
    
    def clear_history(self):
        """Geçmiş verileri temizle"""
        self.flow_history.clear()
        self.pressure_history.clear()
        self.sparklines['flow'].clear()
        self.sparklines['pressure'].clear()
    
    def _on_refresh(self):
        """Yenileme butonu"""
        # Ana pencereye event gönder
        self.event_generate('<<DashboardRefresh>>')


def calculate_network_stats(network_data: Dict) -> NetworkStats:
    """
    Network verisinden istatistikleri hesapla
    
    Args:
        network_data: Network'ten alınan veri
        
    Returns:
        NetworkStats objesi
    """
    stats = NetworkStats()
    
    # Pipes
    pipes = network_data.get('pipes', [])
    for pipe in pipes:
        stats.total_length += pipe.get('length', 0)
        
        # Velocity
        velocity = pipe.get('velocity', 0)
        if velocity > stats.max_velocity:
            stats.max_velocity = velocity
        
        # Pressure
        pressure = pipe.get('pressure', 0)
        if stats.min_pressure == 0 or pressure < stats.min_pressure:
            stats.min_pressure = pressure
        if pressure > stats.max_pressure:
            stats.max_pressure = pressure
    
    # Sprinklers
    sprinklers = network_data.get('sprinklers', [])
    stats.total_sprinklers = len(sprinklers)
    
    for sprinkler in sprinklers:
        stats.total_flow += sprinkler.get('flow_rate', 0)
    
    # Pump
    pump = network_data.get('pump')
    if pump:
        stats.pump_power = pump.get('power', 0)
    
    # Pressure drop
    stats.total_pressure_drop = stats.max_pressure - stats.min_pressure
    
    # Average velocity
    if len(pipes) > 0:
        total_vel = sum(p.get('velocity', 0) for p in pipes)
        stats.avg_velocity = total_vel / len(pipes)
    
    # Validation results
    validation = network_data.get('validation', {})
    stats.error_count = validation.get('error_count', 0)
    stats.warning_count = validation.get('warning_count', 0)
    stats.info_count = validation.get('info_count', 0)
    
    return stats
