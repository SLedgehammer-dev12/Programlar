"""
FireHydra - Hidrolik Hesaplama Motoru (Engine)
==============================================

Bu modül, hidrolik hesaplamaların temel fonksiyonlarını içerir:
- Hazen-Williams sürtünme kaybı hesabı
- Kot farkı basınç hesabı
- Sprinkler debi/basınç hesapları
- Hız hesapları ve limit kontrolleri

Referans Formüller:
- Hazen-Williams (Metrik): P = 6.05×10^5 × L × Q^1.85 / (C^1.85 × d^4.87)
- Kot Farkı Basıncı: ΔP = ΔZ / 10.2 (metre -> bar)
- Sprinkler Debisi: Q = K × √P
"""

import math
from typing import Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class HydraulicResult:
    """Hidrolik hesaplama sonuç yapısı"""
    pressure_loss: float = 0.0  # Bar
    elevation_loss: float = 0.0  # Bar
    total_loss: float = 0.0  # Bar
    velocity: float = 0.0  # m/s
    reynolds_number: float = 0.0
    flow_regime: str = "Laminar"  # Laminar / Turbulent
    is_valid: bool = True
    error_message: str = ""


class HydraulicEngine:
    """
    Hidrolik Hesaplama Motoru
    
    Tüm temel hidrolik hesaplamaları gerçekleştirir.
    NFPA 13 ve TS EN 12845 standartlarına uygun formüller kullanır.
    """
    
    # Sabitler
    GRAVITY = 9.81  # m/s²
    WATER_DENSITY = 1000  # kg/m³
    WATER_KINEMATIC_VISCOSITY = 1.004e-6  # m²/s (20°C)
    
    # Limitler
    MAX_VELOCITY_GENERAL = 6.0  # m/s (NFPA 13 genel limit)
    MAX_VELOCITY_RISER = 10.0  # m/s (Riser için)
    MIN_SPRINKLER_PRESSURE = 0.35  # Bar (minimum)
    
    def __init__(self):
        pass
    
    @staticmethod
    def calculate_pressure_loss_hazen_williams(
        flow_lpm: float,
        diameter_mm: float,
        c_factor: float,
        length_m: float
    ) -> float:
        """
        Hazen-Williams Sürtünme Kaybı Hesabı (Metrik SI)
        
        Formül:
        P_loss (bar) = (6.05 × 10^5 × L × Q^1.85) / (C^1.85 × d^4.87)
        
        Args:
            flow_lpm: Debi (L/dk)
            diameter_mm: İç çap (mm)
            c_factor: Hazen-Williams C değeri
            length_m: Boru uzunluğu (m)
            
        Returns:
            Basınç kaybı (Bar)
        """
        if flow_lpm <= 0 or diameter_mm <= 0 or c_factor <= 0 or length_m <= 0:
            return 0.0
        
        Q = flow_lpm
        d = diameter_mm
        C = c_factor
        L = length_m
        
        numerator = 6.05 * (10 ** 5) * L * (Q ** 1.85)
        denominator = (C ** 1.85) * (d ** 4.87)
        
        return numerator / denominator if denominator > 0 else 0.0
    
    @staticmethod
    def calculate_pressure_loss_darcy_weisbach(
        flow_lpm: float,
        diameter_mm: float,
        length_m: float,
        friction_factor: float = 0.02
    ) -> float:
        """
        Darcy-Weisbach Sürtünme Kaybı Hesabı
        
        Formül:
        ΔP = f × (L/d) × (ρv²/2)
        
        Args:
            flow_lpm: Debi (L/dk)
            diameter_mm: İç çap (mm)
            length_m: Boru uzunluğu (m)
            friction_factor: Sürtünme faktörü (varsayılan 0.02)
            
        Returns:
            Basınç kaybı (Bar)
        """
        if flow_lpm <= 0 or diameter_mm <= 0:
            return 0.0
        
        d_m = diameter_mm / 1000
        area = math.pi * (d_m ** 2) / 4
        velocity = (flow_lpm / 60000) / area  # m/s
        
        # Darcy-Weisbach
        pressure_loss_pa = friction_factor * (length_m / d_m) * (HydraulicEngine.WATER_DENSITY * velocity ** 2) / 2
        
        return pressure_loss_pa / 100000  # Pa -> Bar
    
    @staticmethod
    def calculate_elevation_pressure(elevation_diff_m: float) -> float:
        """
        Kot Farkı Basınç Hesabı
        
        Formül:
        ΔP = ΔZ / 10.2  (metre -> bar)
        veya
        ΔP = ρgh / 100000  (Pa -> Bar)
        
        Args:
            elevation_diff_m: Kot farkı (m) - Pozitif = yukarı, Negatif = aşağı
            
        Returns:
            Basınç farkı (Bar) - Pozitif = basınç artışı gerekir
        """
        return elevation_diff_m / 10.2
    
    @staticmethod
    def calculate_velocity(flow_lpm: float, diameter_mm: float) -> float:
        """
        Akış Hızı Hesabı
        
        Formül:
        v = Q / A = (Q/60000) / (π×d²/4)
        
        Args:
            flow_lpm: Debi (L/dk)
            diameter_mm: İç çap (mm)
            
        Returns:
            Hız (m/s)
        """
        if diameter_mm <= 0 or flow_lpm <= 0:
            return 0.0
        
        d_m = diameter_mm / 1000
        area = math.pi * (d_m ** 2) / 4
        q_m3s = flow_lpm / 60000  # L/dk -> m³/s
        
        return q_m3s / area if area > 0 else 0.0
    
    @staticmethod
    def calculate_reynolds_number(velocity: float, diameter_mm: float) -> float:
        """
        Reynolds Sayısı Hesabı
        
        Formül:
        Re = v × d / ν
        
        Args:
            velocity: Hız (m/s)
            diameter_mm: İç çap (mm)
            
        Returns:
            Reynolds sayısı (boyutsuz)
        """
        if diameter_mm <= 0:
            return 0.0
        
        d_m = diameter_mm / 1000
        return (velocity * d_m) / HydraulicEngine.WATER_KINEMATIC_VISCOSITY
    
    @staticmethod
    def get_flow_regime(reynolds: float) -> str:
        """Akış rejimini belirle"""
        if reynolds < 2300:
            return "Laminar"
        elif reynolds < 4000:
            return "Transition"
        else:
            return "Turbulent"
    
    @staticmethod
    def calculate_sprinkler_flow(k_factor: float, pressure_bar: float) -> float:
        """
        Sprinkler Debisi Hesabı
        
        Formül:
        Q = K × √P
        
        Args:
            k_factor: K-faktör (Metrik)
            pressure_bar: Basınç (Bar)
            
        Returns:
            Debi (L/dk)
        """
        if k_factor <= 0 or pressure_bar <= 0:
            return 0.0
        return k_factor * math.sqrt(pressure_bar)
    
    @staticmethod
    def calculate_sprinkler_pressure(k_factor: float, flow_lpm: float) -> float:
        """
        Sprinkler Basıncı Hesabı (ters formül)
        
        Formül:
        P = (Q / K)²
        
        Args:
            k_factor: K-faktör (Metrik)
            flow_lpm: Debi (L/dk)
            
        Returns:
            Basınç (Bar)
        """
        if k_factor <= 0:
            return 0.0
        return (flow_lpm / k_factor) ** 2
    
    @staticmethod
    def calculate_density_flow(
        density_mmpm: float,
        area_m2: float
    ) -> float:
        """
        Alan Bazlı Debi Hesabı
        
        Formül:
        Q = Density × Area
        
        Args:
            density_mmpm: Yoğunluk (mm/dk veya L/dk·m²)
            area_m2: Alan (m²)
            
        Returns:
            Debi (L/dk)
        """
        return density_mmpm * area_m2
    
    @staticmethod
    def calculate_minimum_sprinkler_flow(
        k_factor: float,
        min_pressure_bar: float,
        density_mmpm: Optional[float] = None,
        coverage_area_m2: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Minimum Sprinkler Debisi ve Basıncı Hesabı
        
        Kural 1 (Basınç Bazlı): Q_pressure = K × √P_min
        Kural 2 (Alan Bazlı): Q_area = Density × Coverage
        Sonuç: Q = max(Q_pressure, Q_area)
        Basınç: P = (Q / K)²
        
        Args:
            k_factor: K-faktör
            min_pressure_bar: Minimum basınç (Bar)
            density_mmpm: Yoğunluk (mm/dk) - opsiyonel
            coverage_area_m2: Koruma alanı (m²) - opsiyonel
            
        Returns:
            (flow_lpm, pressure_bar)
        """
        # Basınç bazlı minimum debi
        q_pressure = k_factor * math.sqrt(min_pressure_bar)
        
        # Alan bazlı minimum debi
        q_area = 0.0
        if density_mmpm is not None and coverage_area_m2 is not None:
            q_area = density_mmpm * coverage_area_m2
        
        # Maksimum debiyi al
        flow = max(q_pressure, q_area)
        
        # Bu debiye karşılık gelen basınç
        pressure = (flow / k_factor) ** 2 if k_factor > 0 else min_pressure_bar
        
        return (flow, pressure)
    
    @staticmethod
    def calculate_hydraulic_result(
        flow_lpm: float,
        diameter_mm: float,
        c_factor: float,
        length_m: float,
        elevation_diff_m: float = 0.0,
        max_velocity: float = 6.0
    ) -> HydraulicResult:
        """
        Kapsamlı Hidrolik Hesaplama
        
        Tüm parametreleri hesaplar ve bir HydraulicResult döndürür.
        
        Args:
            flow_lpm: Debi (L/dk)
            diameter_mm: İç çap (mm)
            c_factor: Hazen-Williams C değeri
            length_m: Boru uzunluğu (m)
            elevation_diff_m: Kot farkı (m)
            max_velocity: Maksimum izin verilen hız (m/s)
            
        Returns:
            HydraulicResult objesi
        """
        result = HydraulicResult()
        
        # Geçerlilik kontrolü
        if flow_lpm <= 0 or diameter_mm <= 0 or c_factor <= 0:
            result.is_valid = False
            result.error_message = "Geçersiz giriş parametreleri"
            return result
        
        # Hız hesabı
        result.velocity = HydraulicEngine.calculate_velocity(flow_lpm, diameter_mm)
        
        # Reynolds sayısı
        result.reynolds_number = HydraulicEngine.calculate_reynolds_number(
            result.velocity, diameter_mm
        )
        result.flow_regime = HydraulicEngine.get_flow_regime(result.reynolds_number)
        
        # Sürtünme kaybı
        result.pressure_loss = HydraulicEngine.calculate_pressure_loss_hazen_williams(
            flow_lpm, diameter_mm, c_factor, length_m
        )
        
        # Kot farkı
        result.elevation_loss = HydraulicEngine.calculate_elevation_pressure(elevation_diff_m)
        
        # Toplam kayıp
        result.total_loss = result.pressure_loss + result.elevation_loss
        
        # Hız kontrolü
        if result.velocity > max_velocity:
            result.is_valid = False
            result.error_message = f"Hız limiti aşıldı: {result.velocity:.2f} m/s > {max_velocity} m/s"
        
        return result
    
    @staticmethod
    def balance_junction_pressure(
        pressure_main: float,
        pressure_branch: float,
        flow_branch: float
    ) -> Tuple[float, float]:
        """
        Junction (T-Bağlantı) Basınç Dengeleme
        
        Fizik kuralı: Aynı noktada iki farklı basınç olamaz.
        Düşük basınçlı kolun debisini artırarak basınçları eşitle.
        
        Formül:
        Q_new = Q_old × √(P_target / P_current)
        
        Args:
            pressure_main: Ana hat basıncı (Bar)
            pressure_branch: Branşman basıncı (Bar)
            flow_branch: Branşman debisi (L/dk)
            
        Returns:
            (corrected_flow, target_pressure)
        """
        if pressure_main <= 0 or pressure_branch <= 0:
            return (flow_branch, max(pressure_main, pressure_branch))
        
        # Yüksek basıncı hedef al
        target_pressure = max(pressure_main, pressure_branch)
        
        if pressure_branch < target_pressure:
            # Branşman debisini artır
            correction_factor = math.sqrt(target_pressure / pressure_branch)
            corrected_flow = flow_branch * correction_factor
        else:
            corrected_flow = flow_branch
        
        return (corrected_flow, target_pressure)
    
    @staticmethod
    def calculate_equivalent_length(
        fittings: List[Tuple[str, float]]
    ) -> float:
        """
        Fitting Eşdeğer Uzunluk Hesabı
        
        Args:
            fittings: [(fitting_type, eq_length), ...] listesi
            
        Returns:
            Toplam eşdeğer uzunluk (m)
        """
        return sum(eq_len for _, eq_len in fittings)
    
    @staticmethod
    def calculate_pipe_size_for_velocity(
        flow_lpm: float,
        target_velocity: float = 4.0
    ) -> float:
        """
        Hedef hıza göre boru çapı hesabı
        
        Formül:
        d = √(4Q / πv)
        
        Args:
            flow_lpm: Debi (L/dk)
            target_velocity: Hedef hız (m/s)
            
        Returns:
            Önerilen iç çap (mm)
        """
        if flow_lpm <= 0 or target_velocity <= 0:
            return 0.0
        
        q_m3s = flow_lpm / 60000
        d_m = math.sqrt((4 * q_m3s) / (math.pi * target_velocity))
        
        return d_m * 1000  # m -> mm
    
    @staticmethod
    def validate_pipe_capacity(
        flow_lpm: float,
        diameter_mm: float,
        c_factor: float,
        length_m: float,
        available_pressure: float
    ) -> Tuple[bool, str]:
        """
        Boru kapasitesini doğrula
        
        Args:
            flow_lpm: Debi (L/dk)
            diameter_mm: İç çap (mm)
            c_factor: C değeri
            length_m: Uzunluk (m)
            available_pressure: Kullanılabilir basınç (Bar)
            
        Returns:
            (is_valid, message)
        """
        # Sürtünme kaybı
        pressure_loss = HydraulicEngine.calculate_pressure_loss_hazen_williams(
            flow_lpm, diameter_mm, c_factor, length_m
        )
        
        # Hız
        velocity = HydraulicEngine.calculate_velocity(flow_lpm, diameter_mm)
        
        messages = []
        is_valid = True
        
        if pressure_loss > available_pressure:
            is_valid = False
            messages.append(f"Basınç kaybı ({pressure_loss:.2f} bar) kullanılabilir basıncı ({available_pressure:.2f} bar) aşıyor")
        
        if velocity > HydraulicEngine.MAX_VELOCITY_GENERAL:
            is_valid = False
            messages.append(f"Hız ({velocity:.2f} m/s) limiti ({HydraulicEngine.MAX_VELOCITY_GENERAL} m/s) aşıyor")
        
        if is_valid:
            return (True, "Boru kapasitesi yeterli")
        else:
            return (False, "; ".join(messages))


# ==================== Test / Demo ====================
if __name__ == "__main__":
    print("=" * 60)
    print("FireHydra Hidrolik Motor Testi")
    print("=" * 60)
    
    engine = HydraulicEngine()
    
    # Test parametreleri
    test_cases = [
        {"flow": 100, "diameter": 52.5, "c": 120, "length": 10},
        {"flow": 200, "diameter": 52.5, "c": 120, "length": 10},
        {"flow": 300, "diameter": 77.9, "c": 120, "length": 10},
        {"flow": 500, "diameter": 102.3, "c": 120, "length": 10},
    ]
    
    print("\n--- Hazen-Williams Basınç Kaybı Testi ---")
    print(f"{'Debi (L/dk)':<15} {'Çap (mm)':<12} {'Uzunluk (m)':<12} {'ΔP (bar)':<12} {'Hız (m/s)':<12}")
    print("-" * 60)
    
    for tc in test_cases:
        p_loss = engine.calculate_pressure_loss_hazen_williams(
            tc["flow"], tc["diameter"], tc["c"], tc["length"]
        )
        velocity = engine.calculate_velocity(tc["flow"], tc["diameter"])
        print(f"{tc['flow']:<15} {tc['diameter']:<12} {tc['length']:<12} {p_loss:<12.4f} {velocity:<12.2f}")
    
    print("\n--- Sprinkler Hesaplama Testi ---")
    k_factor = 80
    min_pressure = 0.5
    
    flow, pressure = engine.calculate_minimum_sprinkler_flow(k_factor, min_pressure)
    print(f"K-Faktör: {k_factor}")
    print(f"Min. Basınç: {min_pressure} bar")
    print(f"Debi: {flow:.1f} L/dk")
    print(f"Hesaplanan Basınç: {pressure:.3f} bar")
    
    print("\n--- Junction Dengeleme Testi ---")
    p_main = 3.5
    p_branch = 3.2
    q_branch = 100
    
    q_corrected, p_target = engine.balance_junction_pressure(p_main, p_branch, q_branch)
    print(f"Ana Hat Basıncı: {p_main} bar")
    print(f"Branşman Basıncı: {p_branch} bar")
    print(f"Branşman Debisi: {q_branch} L/dk")
    print(f"Düzeltilmiş Debi: {q_corrected:.1f} L/dk")
    print(f"Hedef Basınç: {p_target} bar")
    
    print("\n--- Kapsamlı Hidrolik Hesaplama ---")
    result = engine.calculate_hydraulic_result(
        flow_lpm=150,
        diameter_mm=52.5,
        c_factor=120,
        length_m=15,
        elevation_diff_m=3.0
    )
    print(f"Sürtünme Kaybı: {result.pressure_loss:.4f} bar")
    print(f"Kot Farkı Kaybı: {result.elevation_loss:.4f} bar")
    print(f"Toplam Kayıp: {result.total_loss:.4f} bar")
    print(f"Hız: {result.velocity:.2f} m/s")
    print(f"Reynolds: {result.reynolds_number:.0f}")
    print(f"Akış Rejimi: {result.flow_regime}")
    print(f"Geçerli: {result.is_valid}")
    
    print("\nTest tamamlandı!")
