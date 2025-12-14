"""
FireHydra - Optimizasyon Modülü
================================

Boru çapı optimizasyonu ve maliyet analizi.

Kriterler:
- Hız limitleri (NFPA 13: max 6 m/s önerilen, 10 m/s mutlak)
- Basınç kayıpları
- Maliyet optimizasyonu
- Standart çaplara uyum
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math

from models import PipeNetwork, Pipe
from database import DatabaseManager


@dataclass
class OptimizationResult:
    """Optimizasyon sonucu"""
    pipe_id: str
    current_diameter: float
    recommended_diameter: float
    current_velocity: float
    recommended_velocity: float
    current_headloss: float
    recommended_headloss: float
    cost_difference: float  # TL
    reason: str


class PipeOptimizer:
    """
    Boru Çapı Optimizasyonu
    
    NFPA 13 standartlarına göre optimal boru çaplarını hesaplar.
    """
    
    # Standart boru çapları (mm)
    STANDARD_DIAMETERS = [25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300]
    
    # Hız limitleri (m/s)
    MAX_VELOCITY_RECOMMENDED = 6.0
    MAX_VELOCITY_ABSOLUTE = 10.0
    MIN_VELOCITY = 0.5  # Çok düşük hız da istenmeyen
    
    # Maliyet faktörleri (TL/m - tahmini)
    COST_PER_METER = {
        25: 50,
        32: 65,
        40: 80,
        50: 100,
        65: 130,
        80: 160,
        100: 200,
        125: 280,
        150: 360,
        200: 500,
        250: 720,
        300: 950
    }
    
    def __init__(self, network: PipeNetwork, db: DatabaseManager):
        self.network = network
        self.db = db
        self.results: List[OptimizationResult] = []
    
    def optimize_all_pipes(self, optimize_for: str = "velocity") -> List[OptimizationResult]:
        """
        Tüm boruları optimize et
        
        Args:
            optimize_for: "velocity" (hız bazlı) veya "cost" (maliyet bazlı)
        """
        self.results.clear()
        
        for pipe in self.network.pipes.values():
            if pipe.flow_rate and pipe.flow_rate > 0:
                result = self._optimize_pipe(pipe, optimize_for)
                if result:
                    self.results.append(result)
        
        return self.results
    
    def _optimize_pipe(self, pipe: Pipe, optimize_for: str) -> Optional[OptimizationResult]:
        """Tek bir boruyu optimize et"""
        current_diameter = pipe.internal_diameter
        flow_rate = pipe.flow_rate
        length = pipe.length
        c_factor = pipe.c_factor
        
        # Mevcut hız ve basınç kaybı
        current_velocity = self._calculate_velocity(flow_rate, current_diameter)
        current_headloss = self._calculate_headloss(flow_rate, current_diameter, length, c_factor)
        
        # Optimal çap bul
        if optimize_for == "velocity":
            recommended_diameter = self._find_optimal_diameter_by_velocity(flow_rate, current_diameter)
        else:  # cost
            recommended_diameter = self._find_optimal_diameter_by_cost(
                flow_rate, current_diameter, length, c_factor
            )
        
        # Değişiklik gerekli mi?
        if recommended_diameter == current_diameter:
            return None
        
        # Yeni hız ve basınç kaybı
        recommended_velocity = self._calculate_velocity(flow_rate, recommended_diameter)
        recommended_headloss = self._calculate_headloss(flow_rate, recommended_diameter, length, c_factor)
        
        # Maliyet farkı
        cost_diff = self._calculate_cost_difference(
            current_diameter, recommended_diameter, length
        )
        
        # Neden açıklaması
        reason = self._get_reason(current_velocity, recommended_velocity, current_headloss, recommended_headloss)
        
        return OptimizationResult(
            pipe_id=pipe.id,
            current_diameter=current_diameter,
            recommended_diameter=recommended_diameter,
            current_velocity=current_velocity,
            recommended_velocity=recommended_velocity,
            current_headloss=current_headloss,
            recommended_headloss=recommended_headloss,
            cost_difference=cost_diff,
            reason=reason
        )
    
    def _calculate_velocity(self, flow_rate: float, diameter: float) -> float:
        """
        Boru hızını hesapla (m/s)
        
        Args:
            flow_rate: Debi (L/dk)
            diameter: İç çap (mm)
        """
        if diameter <= 0:
            return 0
        
        # V = Q / A
        flow_m3s = (flow_rate / 60) / 1000  # L/dk -> m³/s
        diameter_m = diameter / 1000  # mm -> m
        area_m2 = math.pi * (diameter_m / 2) ** 2
        
        velocity = flow_m3s / area_m2
        return velocity
    
    def _calculate_headloss(self, flow_rate: float, diameter: float, length: float, c_factor: float) -> float:
        """
        Basınç kaybı hesapla (Hazen-Williams denklemi)
        
        Args:
            flow_rate: Debi (L/dk)
            diameter: İç çap (mm)
            length: Uzunluk (m)
            c_factor: Hazen-Williams C faktörü
        
        Returns:
            Basınç kaybı (bar)
        """
        if diameter <= 0 or c_factor <= 0:
            return 0
        
        # Hazen-Williams: hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)
        # Q: m³/s, D: m, hf: m
        flow_m3s = (flow_rate / 60) / 1000  # L/dk -> m³/s
        diameter_m = diameter / 1000  # mm -> m
        
        hf_m = (10.67 * length * (flow_m3s ** 1.852)) / ((c_factor ** 1.852) * (diameter_m ** 4.87))
        
        # m -> bar (1 m su sütunu ≈ 0.0981 bar)
        hf_bar = hf_m * 0.0981
        
        return hf_bar
    
    def _find_optimal_diameter_by_velocity(self, flow_rate: float, current_diameter: float) -> float:
        """Hız kriterine göre optimal çap"""
        # Mevcut hızı kontrol et
        current_velocity = self._calculate_velocity(flow_rate, current_diameter)
        
        # Hız çok yüksekse -> çapı büyüt
        if current_velocity > self.MAX_VELOCITY_ABSOLUTE:
            # Mutlak maksimum aşıldı, acil büyütme gerekli
            target_velocity = self.MAX_VELOCITY_RECOMMENDED
            required_diameter = self._diameter_for_velocity(flow_rate, target_velocity)
            return self._get_next_standard_diameter(required_diameter, up=True)
        
        elif current_velocity > self.MAX_VELOCITY_RECOMMENDED:
            # Önerilen limit aşıldı, büyütme önerilir
            target_velocity = self.MAX_VELOCITY_RECOMMENDED
            required_diameter = self._diameter_for_velocity(flow_rate, target_velocity)
            return self._get_next_standard_diameter(required_diameter, up=True)
        
        # Hız çok düşükse -> çapı küçült (maliyet optimizasyonu)
        elif current_velocity < self.MIN_VELOCITY:
            # En yakın standart küçük çap
            smaller_diameter = self._get_next_standard_diameter(current_diameter, up=False)
            if smaller_diameter < current_diameter:
                new_velocity = self._calculate_velocity(flow_rate, smaller_diameter)
                # Yeni hız hala limitler içindeyse küçült
                if new_velocity <= self.MAX_VELOCITY_RECOMMENDED:
                    return smaller_diameter
        
        # Mevcut çap uygun
        return current_diameter
    
    def _find_optimal_diameter_by_cost(self, flow_rate: float, current_diameter: float, 
                                       length: float, c_factor: float) -> float:
        """Maliyet kriterine göre optimal çap"""
        current_velocity = self._calculate_velocity(flow_rate, current_diameter)
        current_headloss = self._calculate_headloss(flow_rate, current_diameter, length, c_factor)
        
        # Hız limiti aşılıyorsa önce hız optimizasyonu
        if current_velocity > self.MAX_VELOCITY_ABSOLUTE:
            return self._find_optimal_diameter_by_velocity(flow_rate, current_diameter)
        
        # Maliyet/performans dengesi
        best_diameter = current_diameter
        best_score = self._calculate_cost_score(current_diameter, current_velocity, current_headloss, length)
        
        # Bir küçük ve bir büyük çapları dene
        for test_diameter in [
            self._get_next_standard_diameter(current_diameter, up=False),
            self._get_next_standard_diameter(current_diameter, up=True)
        ]:
            if test_diameter == current_diameter:
                continue
            
            test_velocity = self._calculate_velocity(flow_rate, test_diameter)
            test_headloss = self._calculate_headloss(flow_rate, test_diameter, length, c_factor)
            
            # Hız limiti kontrol
            if test_velocity > self.MAX_VELOCITY_RECOMMENDED:
                continue
            
            test_score = self._calculate_cost_score(test_diameter, test_velocity, test_headloss, length)
            
            if test_score < best_score:
                best_score = test_score
                best_diameter = test_diameter
        
        return best_diameter
    
    def _calculate_cost_score(self, diameter: float, velocity: float, headloss: float, length: float) -> float:
        """Maliyet skoru hesapla (düşük = iyi)"""
        # Boru maliyeti
        pipe_cost = self.COST_PER_METER.get(int(diameter), 0) * length
        
        # Basınç kaybı maliyeti (enerji maliyeti - tahmini)
        # Yüksek basınç kaybı = daha güçlü pompa = daha yüksek işletme maliyeti
        headloss_cost = headloss * 1000  # Basınç kaybı faktörü
        
        # Toplam skor
        total_score = pipe_cost + headloss_cost
        
        return total_score
    
    def _diameter_for_velocity(self, flow_rate: float, target_velocity: float) -> float:
        """Belirli bir hız için gerekli çap (mm)"""
        # V = Q / A => A = Q / V => D = sqrt(4*A/pi)
        flow_m3s = (flow_rate / 60) / 1000  # L/dk -> m³/s
        area_m2 = flow_m3s / target_velocity
        diameter_m = math.sqrt(4 * area_m2 / math.pi)
        diameter_mm = diameter_m * 1000
        
        return diameter_mm
    
    def _get_next_standard_diameter(self, diameter: float, up: bool = True) -> float:
        """En yakın standart çapı bul"""
        if up:
            # Bir üst standart çap
            for std_d in self.STANDARD_DIAMETERS:
                if std_d >= diameter:
                    return std_d
            return self.STANDARD_DIAMETERS[-1]  # En büyük
        else:
            # Bir alt standart çap
            for std_d in reversed(self.STANDARD_DIAMETERS):
                if std_d <= diameter:
                    return std_d
            return self.STANDARD_DIAMETERS[0]  # En küçük
    
    def _calculate_cost_difference(self, current_diameter: float, new_diameter: float, length: float) -> float:
        """Maliyet farkı (TL)"""
        current_cost = self.COST_PER_METER.get(int(current_diameter), 0) * length
        new_cost = self.COST_PER_METER.get(int(new_diameter), 0) * length
        
        return new_cost - current_cost
    
    def _get_reason(self, current_velocity: float, new_velocity: float, 
                    current_headloss: float, new_headloss: float) -> str:
        """Optimizasyon nedeni"""
        if current_velocity > self.MAX_VELOCITY_ABSOLUTE:
            return f"Kritik: Hız çok yüksek ({current_velocity:.2f} m/s > {self.MAX_VELOCITY_ABSOLUTE} m/s)"
        elif current_velocity > self.MAX_VELOCITY_RECOMMENDED:
            return f"Hız yüksek ({current_velocity:.2f} m/s > {self.MAX_VELOCITY_RECOMMENDED} m/s)"
        elif current_velocity < self.MIN_VELOCITY:
            saving = -(new_velocity - current_velocity)
            return f"Maliyet optimizasyonu (hız düşük: {current_velocity:.2f} m/s)"
        elif new_headloss < current_headloss * 0.8:
            reduction = ((current_headloss - new_headloss) / current_headloss) * 100
            return f"Basınç kaybı azaltma (%{reduction:.1f} azalma)"
        else:
            return "Optimizasyon"
    
    def apply_optimizations(self, selected_pipe_ids: Optional[List[str]] = None):
        """
        Optimizasyonları uygula
        
        Args:
            selected_pipe_ids: Uygulanacak boru ID'leri (None ise hepsi)
        """
        applied_count = 0
        
        for result in self.results:
            if selected_pipe_ids is None or result.pipe_id in selected_pipe_ids:
                pipe = self.network.get_pipe(result.pipe_id)
                if pipe:
                    pipe.internal_diameter = result.recommended_diameter
                    pipe.nominal_diameter = int(result.recommended_diameter)
                    applied_count += 1
        
        return applied_count
    
    def get_total_cost_impact(self) -> Tuple[float, float, float]:
        """
        Toplam maliyet etkisi
        
        Returns:
            (artış_toplam, azalış_toplam, net_fark)
        """
        increase = sum(r.cost_difference for r in self.results if r.cost_difference > 0)
        decrease = sum(abs(r.cost_difference) for r in self.results if r.cost_difference < 0)
        net = sum(r.cost_difference for r in self.results)
        
        return (increase, decrease, net)
    
    def get_summary(self) -> Dict[str, int]:
        """Özet istatistik"""
        return {
            "total": len(self.results),
            "increase_diameter": len([r for r in self.results if r.recommended_diameter > r.current_diameter]),
            "decrease_diameter": len([r for r in self.results if r.recommended_diameter < r.current_diameter]),
            "critical": len([r for r in self.results if "Kritik" in r.reason]),
        }
