"""
FireHydra - Pompa ve Tank Modülü
================================

Bu modül, yangın söndürme sistemleri için:
- Pompa seçimi ve eğri analizi (NFPA 20)
- Su deposu hesabı (TS EN 12845, BYKHY)
- Pompa eğrisi çakıştırma kontrolü

NFPA 20 Pompa Gereksinimleri:
- Churn (Kapalı vana): P ≤ 1.4 × P_rated
- Nominal: Q_rated @ P_rated
- Overload: Q = 1.5 × Q_rated @ P ≥ 0.65 × P_rated
"""

import math
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum


class PumpType(Enum):
    """Pompa tipleri"""
    HORIZONTAL_SPLIT_CASE = "Horizontal Split Case"
    VERTICAL_TURBINE = "Vertical Turbine"
    END_SUCTION = "End Suction"
    INLINE = "Inline"
    JOCKEY = "Jockey"
    DIESEL = "Diesel Engine Driven"


class HazardDuration(Enum):
    """Tehlike sınıfına göre su deposu süreleri (dakika)"""
    # NFPA 13 / TS EN 12845
    LIGHT_HAZARD = 30
    ORDINARY_HAZARD_1 = 60
    ORDINARY_HAZARD_2 = 60
    HIGH_HAZARD_PROCESS = 90
    HIGH_HAZARD_STORAGE = 120
    
    # BYKHY (Türkiye)
    BYKHY_KONUT = 30
    BYKHY_OFIS = 60
    BYKHY_TICARI = 60
    BYKHY_ENDUSTRI = 90


@dataclass
class PumpCurvePoint:
    """Pompa eğrisi noktası"""
    flow_lpm: float  # L/dk
    pressure_bar: float  # Bar
    efficiency: float = 0.0  # %


@dataclass
class FirePump:
    """
    Yangın Pompası Sınıfı
    
    NFPA 20 uyumlu pompa eğrisi analizi yapar.
    """
    id: str = ""
    brand: str = ""
    model: str = ""
    pump_type: PumpType = PumpType.HORIZONTAL_SPLIT_CASE
    
    # Nominal değerler
    rated_flow_lpm: float = 0.0  # L/dk
    rated_pressure_bar: float = 0.0  # Bar
    
    # NFPA 20 kontrol noktaları
    churn_pressure_bar: float = 0.0  # Kapalı vana basıncı
    overload_flow_lpm: float = 0.0  # 150% debi
    overload_pressure_bar: float = 0.0  # 150% debideki basınç
    
    # Performans verileri
    power_kw: float = 0.0
    efficiency_percent: float = 0.0
    npsh_required_m: float = 0.0
    
    # Pompa eğrisi noktaları
    curve_points: List[PumpCurvePoint] = field(default_factory=list)
    
    def __post_init__(self):
        """NFPA 20 varsayılan değerlerini ayarla"""
        if self.churn_pressure_bar == 0 and self.rated_pressure_bar > 0:
            # Churn basıncı maksimum 140% rated
            self.churn_pressure_bar = self.rated_pressure_bar * 1.3
        
        if self.overload_flow_lpm == 0 and self.rated_flow_lpm > 0:
            self.overload_flow_lpm = self.rated_flow_lpm * 1.5
        
        if self.overload_pressure_bar == 0 and self.rated_pressure_bar > 0:
            # 150% debide minimum 65% basınç
            self.overload_pressure_bar = self.rated_pressure_bar * 0.7
    
    def generate_curve(self, points: int = 10):
        """
        Pompa eğrisi oluştur (3 nokta üzerinden polinom interpolasyonu)
        
        Noktalar: Churn, Rated, Overload
        """
        self.curve_points = []
        
        if self.rated_flow_lpm <= 0:
            return
        
        # 3 ana nokta
        points_data = [
            (0, self.churn_pressure_bar),
            (self.rated_flow_lpm, self.rated_pressure_bar),
            (self.overload_flow_lpm, self.overload_pressure_bar),
        ]
        
        # Polinom katsayıları (2. derece)
        # P = a*Q² + b*Q + c
        # 3 bilinmeyen, 3 denklem
        Q0, P0 = points_data[0]
        Q1, P1 = points_data[1]
        Q2, P2 = points_data[2]
        
        # Cramer kuralı ile çözüm
        det = Q0**2 * (Q1 - Q2) - Q1**2 * (Q0 - Q2) + Q2**2 * (Q0 - Q1)
        
        if abs(det) < 1e-10:
            # Lineer interpolasyon kullan
            for i in range(points + 1):
                q = (self.overload_flow_lpm / points) * i
                if q <= self.rated_flow_lpm:
                    t = q / self.rated_flow_lpm if self.rated_flow_lpm > 0 else 0
                    p = self.churn_pressure_bar + t * (self.rated_pressure_bar - self.churn_pressure_bar)
                else:
                    t = (q - self.rated_flow_lpm) / (self.overload_flow_lpm - self.rated_flow_lpm)
                    p = self.rated_pressure_bar + t * (self.overload_pressure_bar - self.rated_pressure_bar)
                self.curve_points.append(PumpCurvePoint(q, p))
            return
        
        a = (P0 * (Q1 - Q2) - P1 * (Q0 - Q2) + P2 * (Q0 - Q1)) / det
        b = (Q0**2 * (P1 - P2) - Q1**2 * (P0 - P2) + Q2**2 * (P0 - P1)) / det
        c = P0  # Q=0'da P=P0
        
        # Eğri noktaları oluştur
        for i in range(points + 1):
            q = (self.overload_flow_lpm / points) * i
            p = a * q**2 + b * q + c
            p = max(p, self.overload_pressure_bar * 0.5)  # Alt limit
            self.curve_points.append(PumpCurvePoint(q, p))
    
    def get_pressure_at_flow(self, flow_lpm: float) -> float:
        """
        Verilen debide pompa basıncını getir (interpolasyon)
        """
        if not self.curve_points:
            self.generate_curve()
        
        if flow_lpm <= 0:
            return self.churn_pressure_bar
        
        if flow_lpm >= self.overload_flow_lpm:
            return self.overload_pressure_bar
        
        # İki nokta arasında lineer interpolasyon
        for i in range(len(self.curve_points) - 1):
            p1 = self.curve_points[i]
            p2 = self.curve_points[i + 1]
            
            if p1.flow_lpm <= flow_lpm <= p2.flow_lpm:
                t = (flow_lpm - p1.flow_lpm) / (p2.flow_lpm - p1.flow_lpm)
                return p1.pressure_bar + t * (p2.pressure_bar - p1.pressure_bar)
        
        return self.rated_pressure_bar
    
    def check_system_point(self, system_flow: float, system_pressure: float) -> Tuple[bool, str]:
        """
        Sistem noktasını pompa eğrisi ile karşılaştır
        
        Args:
            system_flow: Sistem debisi (L/dk)
            system_pressure: Sistem basıncı (Bar)
            
        Returns:
            (is_suitable, message)
        """
        pump_pressure = self.get_pressure_at_flow(system_flow)
        
        if pump_pressure >= system_pressure:
            margin = ((pump_pressure / system_pressure) - 1) * 100
            return (True, f"✅ POMPA UYGUN! Basınç marjı: %{margin:.1f}")
        else:
            deficit = ((system_pressure / pump_pressure) - 1) * 100
            return (False, f"❌ POMPA YETERSİZ! Basınç açığı: %{deficit:.1f}")
    
    def check_nfpa20_compliance(self) -> Tuple[bool, List[str]]:
        """
        NFPA 20 uyumluluk kontrolü
        
        Kurallar:
        1. Churn basıncı ≤ 140% × Rated basınç
        2. 150% debide basınç ≥ 65% × Rated basınç
        """
        issues = []
        is_compliant = True
        
        # Churn kontrolü
        if self.churn_pressure_bar > self.rated_pressure_bar * 1.4:
            issues.append(f"Churn basıncı çok yüksek: {self.churn_pressure_bar:.2f} bar > {self.rated_pressure_bar * 1.4:.2f} bar")
            is_compliant = False
        
        # Overload kontrolü
        if self.overload_pressure_bar < self.rated_pressure_bar * 0.65:
            issues.append(f"Overload basıncı çok düşük: {self.overload_pressure_bar:.2f} bar < {self.rated_pressure_bar * 0.65:.2f} bar")
            is_compliant = False
        
        if is_compliant:
            issues.append("✅ NFPA 20 uyumlu")
        
        return (is_compliant, issues)
    
    def __str__(self):
        return f"{self.brand} {self.model} ({self.rated_flow_lpm} L/dk @ {self.rated_pressure_bar} bar)"


@dataclass
class WaterTankResult:
    """Su deposu hesap sonucu"""
    required_volume_m3: float = 0.0
    system_flow_lpm: float = 0.0
    hose_stream_lpm: float = 0.0
    total_flow_lpm: float = 0.0
    duration_min: int = 0
    hazard_class: str = ""
    standard: str = ""


class PumpAndTankModule:
    """
    Pompa ve Tank Hesaplama Modülü
    
    NFPA 20, TS EN 12845 ve BYKHY standartlarına uygun
    pompa seçimi ve su deposu hesabı yapar.
    """
    
    # Hidrant debi değerleri (L/dk)
    HOSE_STREAM_FLOWS = {
        "LIGHT_HAZARD": 250,
        "ORDINARY_HAZARD_1": 500,
        "ORDINARY_HAZARD_2": 500,
        "HIGH_HAZARD_PROCESS": 1000,
        "HIGH_HAZARD_STORAGE": 1000,
        "BYKHY_KONUT": 0,
        "BYKHY_OFIS": 500,
        "BYKHY_TICARI": 500,
        "BYKHY_ENDUSTRI": 1000,
    }
    
    # Su süresi (dakika)
    DURATIONS = {
        "LIGHT_HAZARD": 30,
        "ORDINARY_HAZARD_1": 60,
        "ORDINARY_HAZARD_2": 60,
        "HIGH_HAZARD_PROCESS": 90,
        "HIGH_HAZARD_STORAGE": 120,
        "BYKHY_KONUT": 30,
        "BYKHY_OFIS": 60,
        "BYKHY_TICARI": 60,
        "BYKHY_ENDUSTRI": 90,
    }
    
    def __init__(self):
        self.pumps: List[FirePump] = []
        self._load_default_pumps()
    
    def _load_default_pumps(self):
        """Varsayılan pompa kataloğunu yükle"""
        default_pumps = [
            # Düşük kapasite
            FirePump(id="P001", brand="Generic", model="FP-50/8",
                    rated_flow_lpm=500, rated_pressure_bar=8,
                    pump_type=PumpType.END_SUCTION, power_kw=15),
            
            FirePump(id="P002", brand="Generic", model="FP-100/8",
                    rated_flow_lpm=1000, rated_pressure_bar=8,
                    pump_type=PumpType.END_SUCTION, power_kw=30),
            
            # Orta kapasite
            FirePump(id="P003", brand="Generic", model="FP-150/10",
                    rated_flow_lpm=1500, rated_pressure_bar=10,
                    pump_type=PumpType.HORIZONTAL_SPLIT_CASE, power_kw=55),
            
            FirePump(id="P004", brand="Generic", model="FP-200/10",
                    rated_flow_lpm=2000, rated_pressure_bar=10,
                    pump_type=PumpType.HORIZONTAL_SPLIT_CASE, power_kw=75),
            
            # Yüksek kapasite
            FirePump(id="P005", brand="Generic", model="FP-300/12",
                    rated_flow_lpm=3000, rated_pressure_bar=12,
                    pump_type=PumpType.HORIZONTAL_SPLIT_CASE, power_kw=110),
            
            FirePump(id="P006", brand="Generic", model="FP-500/12",
                    rated_flow_lpm=5000, rated_pressure_bar=12,
                    pump_type=PumpType.HORIZONTAL_SPLIT_CASE, power_kw=185),
            
            # Jockey pompası
            FirePump(id="J001", brand="Generic", model="JP-5/12",
                    rated_flow_lpm=50, rated_pressure_bar=12,
                    pump_type=PumpType.JOCKEY, power_kw=2.2),
        ]
        
        for pump in default_pumps:
            pump.generate_curve()
        
        self.pumps = default_pumps
    
    def add_pump(self, pump: FirePump):
        """Pompa ekle"""
        pump.generate_curve()
        self.pumps.append(pump)
    
    def get_pump_by_id(self, pump_id: str) -> Optional[FirePump]:
        """ID ile pompa getir"""
        for pump in self.pumps:
            if pump.id == pump_id:
                return pump
        return None
    
    def find_suitable_pumps(self, required_flow: float, 
                           required_pressure: float,
                           margin_percent: float = 10) -> List[Tuple[FirePump, float]]:
        """
        Uygun pompaları bul
        
        Args:
            required_flow: Gereken debi (L/dk)
            required_pressure: Gereken basınç (Bar)
            margin_percent: Güvenlik marjı (%)
            
        Returns:
            [(pump, margin), ...] - Marj yüzdesine göre sıralı
        """
        suitable = []
        
        required_pressure_with_margin = required_pressure * (1 + margin_percent / 100)
        
        for pump in self.pumps:
            if pump.pump_type == PumpType.JOCKEY:
                continue  # Jockey pompaları hariç tut
            
            available_pressure = pump.get_pressure_at_flow(required_flow)
            
            if available_pressure >= required_pressure_with_margin:
                margin = ((available_pressure / required_pressure) - 1) * 100
                suitable.append((pump, margin))
        
        # Marj yüzdesine göre sırala (düşükten yükseğe)
        suitable.sort(key=lambda x: x[1])
        
        return suitable
    
    def calculate_water_tank(self, system_flow_lpm: float,
                            hazard_class: str,
                            standard: str = "NFPA") -> WaterTankResult:
        """
        Su deposu hacmini hesapla
        
        Formül: V = (Q_system + Q_hose) × Duration
        
        Args:
            system_flow_lpm: Sistem debisi (L/dk)
            hazard_class: Tehlike sınıfı kodu
            standard: Standart (NFPA, EN, BYKHY)
            
        Returns:
            WaterTankResult objesi
        """
        result = WaterTankResult()
        result.system_flow_lpm = system_flow_lpm
        result.hazard_class = hazard_class
        result.standard = standard
        
        # Hazard sınıfını standarda göre eşle
        hazard_key = hazard_class.upper().replace(" ", "_")
        
        # Süre
        result.duration_min = self.DURATIONS.get(hazard_key, 60)
        
        # Hidrant debisi
        result.hose_stream_lpm = self.HOSE_STREAM_FLOWS.get(hazard_key, 500)
        
        # Toplam debi
        result.total_flow_lpm = system_flow_lpm + result.hose_stream_lpm
        
        # Hacim hesabı (L -> m³)
        volume_liters = result.total_flow_lpm * result.duration_min
        result.required_volume_m3 = volume_liters / 1000
        
        return result
    
    def calculate_tank_dimensions(self, volume_m3: float,
                                  aspect_ratio: float = 2.0) -> Dict:
        """
        Tank boyutları hesapla (dikdörtgen tank için)
        
        Args:
            volume_m3: Tank hacmi (m³)
            aspect_ratio: Uzunluk/Genişlik oranı
            
        Returns:
            {length, width, height, surface_area}
        """
        # Varsayılan yükseklik 3m
        height = 3.0
        
        # Taban alanı
        base_area = volume_m3 / height
        
        # Uzunluk ve genişlik
        width = math.sqrt(base_area / aspect_ratio)
        length = width * aspect_ratio
        
        # Yüzey alanı
        surface_area = 2 * (length * width + length * height + width * height)
        
        return {
            "length_m": round(length, 2),
            "width_m": round(width, 2),
            "height_m": height,
            "base_area_m2": round(base_area, 2),
            "surface_area_m2": round(surface_area, 2),
            "volume_m3": volume_m3
        }
    
    def get_jockey_pump_requirements(self, main_pump: FirePump) -> Dict:
        """
        Jockey pompa gereksinimlerini hesapla
        
        NFPA 20 gereksinimleri:
        - Debi: 1-2% ana pompa debisi
        - Basınç: Ana pompa churn basıncı + 0.7 bar
        """
        jockey_flow = main_pump.rated_flow_lpm * 0.01  # %1
        jockey_pressure = main_pump.churn_pressure_bar + 0.7
        
        return {
            "flow_lpm": round(jockey_flow, 1),
            "pressure_bar": round(jockey_pressure, 2),
            "purpose": "Sistem basıncını koruma ve küçük sızıntıları telafi"
        }
    
    def print_pump_analysis(self, pump: FirePump, system_flow: float, 
                           system_pressure: float):
        """Pompa analizi yazdır"""
        print("\n" + "=" * 60)
        print("POMPA ANALİZİ")
        print("=" * 60)
        
        print(f"\nPompa: {pump}")
        print(f"Tip: {pump.pump_type.value}")
        print(f"Güç: {pump.power_kw} kW")
        
        print(f"\n--- NFPA 20 Kontrol Noktaları ---")
        print(f"Churn (Q=0): {pump.churn_pressure_bar:.2f} bar")
        print(f"Nominal (Q={pump.rated_flow_lpm}): {pump.rated_pressure_bar:.2f} bar")
        print(f"Overload (Q={pump.overload_flow_lpm:.0f}): {pump.overload_pressure_bar:.2f} bar")
        
        is_compliant, issues = pump.check_nfpa20_compliance()
        print(f"\n--- NFPA 20 Uyumluluk ---")
        for issue in issues:
            print(f"  {issue}")
        
        print(f"\n--- Sistem Noktası Kontrolü ---")
        print(f"Sistem İhtiyacı: {system_flow:.0f} L/dk @ {system_pressure:.2f} bar")
        
        pump_pressure = pump.get_pressure_at_flow(system_flow)
        print(f"Pompa Çıkışı: {system_flow:.0f} L/dk @ {pump_pressure:.2f} bar")
        
        is_suitable, message = pump.check_system_point(system_flow, system_pressure)
        print(f"Sonuç: {message}")
        
        print("=" * 60)


# ==================== Test / Demo ====================
if __name__ == "__main__":
    print("=" * 60)
    print("FireHydra Pompa ve Tank Modülü Testi")
    print("=" * 60)
    
    module = PumpAndTankModule()
    
    # Sistem gereksinimleri
    system_flow = 1500  # L/dk
    system_pressure = 8.5  # Bar
    
    print(f"\n--- SİSTEM GEREKSİNİMLERİ ---")
    print(f"Debi: {system_flow} L/dk")
    print(f"Basınç: {system_pressure} bar")
    
    # Uygun pompaları bul
    print(f"\n--- UYGUN POMPALAR ---")
    suitable = module.find_suitable_pumps(system_flow, system_pressure)
    
    for pump, margin in suitable:
        print(f"  {pump} - Marj: %{margin:.1f}")
    
    # En uygun pompa analizi
    if suitable:
        best_pump = suitable[0][0]
        module.print_pump_analysis(best_pump, system_flow, system_pressure)
        
        # Jockey pompa
        jockey = module.get_jockey_pump_requirements(best_pump)
        print(f"\n--- JOCKEY POMPA GEREKSİNİMİ ---")
        print(f"Debi: {jockey['flow_lpm']} L/dk")
        print(f"Basınç: {jockey['pressure_bar']} bar")
    
    # Su deposu hesabı
    print(f"\n--- SU DEPOSU HESABI ---")
    tank_result = module.calculate_water_tank(system_flow, "ORDINARY_HAZARD_2")
    
    print(f"Tehlike Sınıfı: {tank_result.hazard_class}")
    print(f"Sistem Debisi: {tank_result.system_flow_lpm} L/dk")
    print(f"Hidrant Debisi: {tank_result.hose_stream_lpm} L/dk")
    print(f"Toplam Debi: {tank_result.total_flow_lpm} L/dk")
    print(f"Süre: {tank_result.duration_min} dakika")
    print(f"Gerekli Hacim: {tank_result.required_volume_m3:.1f} m³")
    
    # Tank boyutları
    dimensions = module.calculate_tank_dimensions(tank_result.required_volume_m3)
    print(f"\n--- TANK BOYUTLARI ---")
    print(f"Uzunluk: {dimensions['length_m']} m")
    print(f"Genişlik: {dimensions['width_m']} m")
    print(f"Yükseklik: {dimensions['height_m']} m")
    
    print("\nTest tamamlandı!")
