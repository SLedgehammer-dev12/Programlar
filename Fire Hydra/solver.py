"""
FireHydra - Hidrolik Çözücü (Solver)
====================================

Bu modül, boru ağı için hidrolik hesaplamaları gerçekleştirir.
"Recursive Back-Calculation" (Geriye Doğru Yinelemeli Hesap) algoritmasını kullanır.

Algoritma Adımları:
1. En kritik (en uzak/yüksek) sprinkler'ı bul
2. Başlangıç debisi ve basıncını hesapla
3. Geriye doğru (kaynağa) hesapla
4. Junction noktalarında basınç dengelemesi yap
5. Toplam sistem debisi ve basıncını belirle
"""

import math
from typing import Optional, List, Dict, Tuple, Set
from dataclasses import dataclass, field
from collections import deque
import logging

from models import Node, Pipe, PipeNetwork, NodeType, Coordinates
from engine import HydraulicEngine, HydraulicResult
from database import DatabaseManager, HazardClass


# Logging konfigürasyonu
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FireHydra.Solver")


@dataclass
class CalculationStep:
    """Hesaplama adımı kayıt yapısı"""
    step_number: int
    node_id: str
    node_type: str
    pressure_in: float  # Bar
    pressure_out: float  # Bar
    flow: float  # L/dk
    friction_loss: float  # Bar
    elevation_loss: float  # Bar
    notes: str = ""


@dataclass
class SolverResult:
    """Çözücü sonuç yapısı"""
    success: bool = False
    error_message: str = ""
    
    # Sistem sonuçları
    total_flow: float = 0.0  # L/dk
    total_pressure: float = 0.0  # Bar (pompa çıkışında)
    
    # Sprinkler sonuçları
    sprinkler_count: int = 0
    operating_area_m2: float = 0.0
    density_mmpm: float = 0.0
    
    # Hesaplama detayları
    calculation_steps: List[CalculationStep] = field(default_factory=list)
    iterations: int = 0
    max_velocity: float = 0.0
    
    # Uyarılar
    warnings: List[str] = field(default_factory=list)
    
    def add_warning(self, message: str):
        """Uyarı ekle"""
        self.warnings.append(message)
        logger.warning(message)


class HydraulicSolver:
    """
    Hidrolik Çözücü Sınıfı
    
    Boru ağı için tam hidrolik hesaplama yapar.
    Tree (ağaç) topolojisi için Recursive Back-Calculation kullanır.
    """
    
    # Sabitleri
    MAX_ITERATIONS = 100  # Maksimum iterasyon sayısı
    CONVERGENCE_TOLERANCE = 0.01  # Bar (yakınsama toleransı)
    
    def __init__(self, network: PipeNetwork, db: Optional[DatabaseManager] = None):
        """
        Çözücüyü başlat
        
        Args:
            network: Boru ağı (PipeNetwork)
            db: Veritabanı yöneticisi (opsiyonel)
        """
        self.network = network
        self.db = db
        self.engine = HydraulicEngine()
        
        # Hesaplama parametreleri
        self.density: float = 5.0  # mm/dk (varsayılan OH2)
        self.operating_area: float = 150.0  # m²
        self.hazard_class: Optional[HazardClass] = None
        
        # Sonuç
        self.result = SolverResult()
        
        # Hesaplama sırası
        self._calculation_order: List[str] = []
        self._visited: Set[str] = set()
        
    def set_hazard_class(self, hazard_code: str):
        """Tehlike sınıfını ayarla"""
        if self.db:
            self.hazard_class = self.db.get_hazard_class(hazard_code)
            if self.hazard_class:
                self.density = self.hazard_class.density_mm_min
                logger.info(f"Tehlike sınıfı ayarlandı: {hazard_code}, Yoğunluk: {self.density} mm/dk")
    
    def set_design_parameters(self, density: float, operating_area: float):
        """Tasarım parametrelerini ayarla"""
        self.density = density
        self.operating_area = operating_area
        logger.info(f"Tasarım parametreleri: Yoğunluk={density} mm/dk, Alan={operating_area} m²")
    
    def solve(self) -> SolverResult:
        """
        Ana çözücü fonksiyonu
        
        Recursive Back-Calculation algoritmasını çalıştırır.
        
        Returns:
            SolverResult objesi
        """
        self.result = SolverResult()
        self.network.reset_calculations()
        self._calculation_order = []
        self._visited = set()
        
        try:
            # 1. Kaynak düğümünü kontrol et
            source = self.network.get_source_node()
            if not source:
                self.result.error_message = "Kaynak düğümü (pompa) bulunamadı!"
                return self.result
            
            # 2. Sprinklerleri bul
            sprinklers = self.network.get_sprinklers()
            if not sprinklers:
                self.result.error_message = "Sprinkler bulunamadı!"
                return self.result
            
            self.result.sprinkler_count = len(sprinklers)
            logger.info(f"Toplam {len(sprinklers)} sprinkler bulundu")
            
            # 3. En kritik sprinkler'ı bul
            remote_sprinkler = self.network.find_most_remote_sprinkler()
            if not remote_sprinkler:
                self.result.error_message = "En uzak sprinkler belirlenemedi!"
                return self.result
            
            logger.info(f"En uzak sprinkler: {remote_sprinkler.id}")
            
            # 4. İlk sprinkler için başlangıç hesabı
            self._calculate_initial_sprinkler(remote_sprinkler)
            
            # 5. Geriye doğru hesaplama (Recursive)
            self._back_calculate_to_source(remote_sprinkler.id, source.id)
            
            # 6. Sonuçları topla
            self._compile_results()
            
            self.result.success = True
            logger.info(f"Hesaplama tamamlandı: Q={self.result.total_flow:.1f} L/dk, P={self.result.total_pressure:.2f} bar")
            
        except Exception as e:
            self.result.error_message = f"Hesaplama hatası: {str(e)}"
            logger.error(self.result.error_message)
        
        return self.result
    
    def _calculate_initial_sprinkler(self, sprinkler: Node):
        """
        İlk sprinkler için başlangıç debisi ve basıncını hesapla
        
        Kural 1: Q_area = Density × Coverage_Area
        Kural 2: Q_pressure = K × √P_min
        Sonuç: Q = max(Q_area, Q_pressure)
        """
        k = sprinkler.k_factor
        p_min = sprinkler.min_pressure_required
        coverage = sprinkler.coverage_area
        
        # Alan bazlı debi
        q_area = self.density * coverage
        
        # Basınç bazlı minimum debi
        q_pressure = k * math.sqrt(p_min)
        
        # Maksimum debiyi al
        flow = max(q_area, q_pressure)
        
        # Basınç hesapla: P = (Q/K)²
        pressure = (flow / k) ** 2
        
        # Sprinkler'a ata
        sprinkler.total_flow = flow
        sprinkler.pressure = pressure
        sprinkler.is_calculated = True
        sprinkler.calculation_order = 1
        
        self._calculation_order.append(sprinkler.id)
        
        # Log
        step = CalculationStep(
            step_number=1,
            node_id=sprinkler.id,
            node_type="Sprinkler (Start)",
            pressure_in=0,
            pressure_out=pressure,
            flow=flow,
            friction_loss=0,
            elevation_loss=0,
            notes=f"K={k}, P_min={p_min}, Density={self.density}"
        )
        self.result.calculation_steps.append(step)
        
        logger.info(f"Başlangıç sprinkler: Q={flow:.1f} L/dk, P={pressure:.3f} bar")
    
    def _back_calculate_to_source(self, start_node_id: str, source_id: str):
        """
        Geriye doğru hesaplama (Recursive Back-Calculation)
        
        Sprinkler'dan kaynağa doğru boru ağını takip ederek
        her düğümde basınç ve debi hesaplar.
        """
        # BFS ile kaynağa giden yolu bul
        path = self.network.find_path_to_source(start_node_id)
        
        if not path:
            raise ValueError(f"Kaynağa yol bulunamadı: {start_node_id}")
        
        logger.info(f"Hesaplama yolu: {' -> '.join(path)}")
        
        step_num = len(self.result.calculation_steps) + 1
        
        # Yol boyunca hesapla (sprinkler -> source)
        for i in range(len(path) - 1):
            current_id = path[i]
            next_id = path[i + 1]
            
            current_node = self.network.get_node(current_id)
            next_node = self.network.get_node(next_id)
            pipe = self.network.get_pipe_between_nodes(current_id, next_id)
            
            if not current_node or not next_node or not pipe:
                continue
            
            # Mevcut düğümün değerleri
            p_current = current_node.pressure or 0
            q_current = current_node.total_flow or 0
            
            # Boru parametreleri
            L = pipe.get_total_equivalent_length()
            d = pipe.internal_diameter
            C = pipe.c_factor
            
            # Sürtünme kaybı
            friction_loss = self.engine.calculate_pressure_loss_hazen_williams(
                q_current, d, C, L
            )
            
            # Kot farkı
            z_current = current_node.get_elevation()
            z_next = next_node.get_elevation()
            elevation_diff = z_current - z_next  # Pozitif = yukarı gidiyoruz
            elevation_loss = self.engine.calculate_elevation_pressure(elevation_diff)
            
            # Bir sonraki düğüm basıncı
            p_next = p_current + friction_loss + elevation_loss
            
            # Boru hesaplamalarını güncelle
            pipe.update_flow_calculations(q_current)
            
            # Junction kontrolü (T-Bağlantı)
            if next_node.node_type == NodeType.JUNCTION:
                # Diğer kollardan gelen debiyi ekle
                p_next, q_next = self._handle_junction(next_node, p_next, q_current)
            else:
                q_next = q_current
            
            # Sprinkler ise debi ekle
            if next_node.node_type == NodeType.SPRINKLER and not next_node.is_calculated:
                sprinkler_flow = self._calculate_sprinkler_at_pressure(next_node, p_next)
                q_next = q_current + sprinkler_flow
            
            # Sonraki düğümü güncelle
            next_node.pressure = p_next
            next_node.total_flow = q_next
            next_node.is_calculated = True
            next_node.calculation_order = step_num
            
            self._calculation_order.append(next_id)
            
            # Hız kontrolü
            velocity = pipe.velocity or 0
            if velocity > self.result.max_velocity:
                self.result.max_velocity = velocity
            
            if velocity > HydraulicEngine.MAX_VELOCITY_GENERAL:
                self.result.add_warning(
                    f"Boru {pipe.id}: Hız limiti aşıldı ({velocity:.2f} m/s)"
                )
            
            # Log
            step = CalculationStep(
                step_number=step_num,
                node_id=next_id,
                node_type=next_node.node_type.value,
                pressure_in=p_current,
                pressure_out=p_next,
                flow=q_next,
                friction_loss=friction_loss,
                elevation_loss=elevation_loss,
                notes=f"Pipe: {pipe.id}, L={L:.2f}m, D={d}mm"
            )
            self.result.calculation_steps.append(step)
            
            step_num += 1
    
    def _handle_junction(self, junction: Node, main_pressure: float, 
                        main_flow: float) -> Tuple[float, float]:
        """
        Junction (T-Bağlantı) Noktası İşleme
        
        Birden fazla kol birleştiğinde basınç dengelemesi yapar.
        
        Returns:
            (balanced_pressure, total_flow)
        """
        # Junction'a bağlı tüm boruları bul
        connected_pipes = self.network.get_connected_pipes(junction.id)
        
        total_flow = main_flow
        max_pressure = main_pressure
        
        for pipe in connected_pipes:
            # Diğer uçtaki düğümü bul
            other_node_id = pipe.end_node_id if pipe.start_node_id == junction.id else pipe.start_node_id
            other_node = self.network.get_node(other_node_id)
            
            if not other_node or other_node.is_calculated:
                continue
            
            # Bu bir sprinkler koluysa
            if other_node.node_type == NodeType.SPRINKLER:
                # Sprinkler'ı mevcut basınçta hesapla
                branch_flow = self._calculate_branch_from_junction(
                    junction.id, other_node_id, main_pressure
                )
                total_flow += branch_flow
        
        return (max_pressure, total_flow)
    
    def _calculate_branch_from_junction(self, junction_id: str, 
                                        sprinkler_id: str,
                                        junction_pressure: float) -> float:
        """
        Junction'dan sprinkler'a olan kolu hesapla
        
        Args:
            junction_id: T-Bağlantı düğüm ID
            sprinkler_id: Sprinkler düğüm ID
            junction_pressure: Junction basıncı (Bar)
            
        Returns:
            Bu koldan gelen toplam debi (L/dk)
        """
        sprinkler = self.network.get_node(sprinkler_id)
        pipe = self.network.get_pipe_between_nodes(junction_id, sprinkler_id)
        
        if not sprinkler or not pipe:
            return 0.0
        
        # İteratif hesaplama
        # İlk tahmin: minimum basınçta debi
        k = sprinkler.k_factor
        p_min = sprinkler.min_pressure_required
        
        estimated_flow = k * math.sqrt(p_min)
        
        for iteration in range(self.MAX_ITERATIONS):
            # Sürtünme kaybı
            L = pipe.get_total_equivalent_length()
            friction_loss = self.engine.calculate_pressure_loss_hazen_williams(
                estimated_flow, pipe.internal_diameter, pipe.c_factor, L
            )
            
            # Kot farkı
            z_junction = self.network.get_node(junction_id).get_elevation()
            z_sprinkler = sprinkler.get_elevation()
            elevation_loss = self.engine.calculate_elevation_pressure(z_sprinkler - z_junction)
            
            # Sprinkler'daki basınç
            p_sprinkler = junction_pressure - friction_loss - elevation_loss
            
            if p_sprinkler < p_min:
                p_sprinkler = p_min
            
            # Yeni debi
            new_flow = k * math.sqrt(p_sprinkler)
            
            # Yakınsama kontrolü
            if abs(new_flow - estimated_flow) < 0.1:
                break
            
            estimated_flow = new_flow
        
        # Sprinkler değerlerini güncelle
        sprinkler.pressure = p_sprinkler
        sprinkler.total_flow = new_flow
        sprinkler.is_calculated = True
        
        # Boru değerlerini güncelle
        pipe.update_flow_calculations(new_flow)
        
        self.result.iterations += iteration + 1
        
        return new_flow
    
    def _calculate_sprinkler_at_pressure(self, sprinkler: Node, 
                                         available_pressure: float) -> float:
        """
        Verilen basınçta sprinkler debisini hesapla
        
        Q = K × √P
        
        Returns:
            Sprinkler debisi (L/dk)
        """
        k = sprinkler.k_factor
        p = max(available_pressure, sprinkler.min_pressure_required)
        
        flow = k * math.sqrt(p)
        
        sprinkler.pressure = p
        sprinkler.total_flow = flow
        sprinkler.is_calculated = True
        
        return flow
    
    def _compile_results(self):
        """Sonuçları derle"""
        source = self.network.get_source_node()
        
        if source and source.is_calculated:
            self.result.total_flow = source.total_flow or 0
            self.result.total_pressure = source.pressure or 0
        
        self.result.operating_area_m2 = self.operating_area
        self.result.density_mmpm = self.density
        
        # Hesaplama sonuçlarını ağa kaydet
        self.network.total_system_flow = self.result.total_flow
        self.network.total_system_pressure = self.result.total_pressure
        self.network.is_calculated = True
    
    def get_node_summary(self) -> List[Dict]:
        """Düğüm özet tablosu"""
        summary = []
        
        for node_id in self._calculation_order:
            node = self.network.get_node(node_id)
            if node:
                summary.append({
                    "id": node.id,
                    "type": node.node_type.value,
                    "elevation_m": node.get_elevation(),
                    "pressure_bar": node.pressure or 0,
                    "flow_lpm": node.total_flow or 0,
                    "k_factor": node.k_factor if node.is_sprinkler() else None,
                })
        
        return summary
    
    def get_pipe_summary(self) -> List[Dict]:
        """Boru özet tablosu"""
        summary = []
        
        for pipe in self.network.pipes.values():
            summary.append({
                "id": pipe.id,
                "from": pipe.start_node_id,
                "to": pipe.end_node_id,
                "diameter_mm": pipe.internal_diameter,
                "length_m": pipe.length,
                "eq_length_m": pipe.get_total_equivalent_length(),
                "flow_lpm": pipe.flow or 0,
                "velocity_ms": pipe.velocity or 0,
                "friction_loss_bar": pipe.friction_loss or 0,
            })
        
        return summary
    
    def print_results(self):
        """Sonuçları konsola yazdır"""
        print("\n" + "=" * 70)
        print("FIREHYDRA HİDROLİK HESAPLAMA SONUÇLARI")
        print("=" * 70)
        
        if not self.result.success:
            print(f"\n❌ HATA: {self.result.error_message}")
            return
        
        print(f"\n✅ Hesaplama başarılı!")
        print(f"\n--- SİSTEM SONUÇLARI ---")
        print(f"Toplam Sistem Debisi: {self.result.total_flow:.1f} L/dk")
        print(f"Toplam Sistem Basıncı: {self.result.total_pressure:.2f} Bar")
        print(f"Sprinkler Sayısı: {self.result.sprinkler_count}")
        print(f"Tasarım Yoğunluğu: {self.result.density_mmpm} mm/dk")
        print(f"Tasarım Alanı: {self.result.operating_area_m2} m²")
        print(f"Maksimum Hız: {self.result.max_velocity:.2f} m/s")
        print(f"İterasyon Sayısı: {self.result.iterations}")
        
        if self.result.warnings:
            print(f"\n--- UYARILAR ({len(self.result.warnings)}) ---")
            for w in self.result.warnings:
                print(f"  ⚠️ {w}")
        
        print(f"\n--- HESAPLAMA ADIMLARI ({len(self.result.calculation_steps)}) ---")
        print(f"{'#':<4} {'Düğüm':<12} {'Tip':<15} {'P_in':>8} {'P_out':>8} {'ΔP_f':>8} {'ΔP_z':>8} {'Q':>10}")
        print("-" * 80)
        
        for step in self.result.calculation_steps:
            print(f"{step.step_number:<4} {step.node_id:<12} {step.node_type:<15} "
                  f"{step.pressure_in:>8.3f} {step.pressure_out:>8.3f} "
                  f"{step.friction_loss:>8.4f} {step.elevation_loss:>8.4f} "
                  f"{step.flow:>10.1f}")
        
        print("=" * 70)


# ==================== Test / Demo ====================
if __name__ == "__main__":
    from .models import Coordinates, Fitting, FittingCategory
    
    print("=" * 60)
    print("FireHydra Solver Testi")
    print("=" * 60)
    
    # Test ağı oluştur
    network = PipeNetwork("Solver Test")
    
    # Kaynak (Pompa)
    source = Node(
        id="SOURCE",
        node_type=NodeType.SOURCE,
        coordinates=Coordinates(0, 0, 0)
    )
    network.add_node(source)
    
    # Ana hat junction
    junction = Node(
        id="J1",
        node_type=NodeType.JUNCTION,
        coordinates=Coordinates(10000, 0, 3.0)
    )
    network.add_node(junction)
    
    # Sprinkler 1 (En uzak)
    spr1 = Node(
        id="SPR1",
        node_type=NodeType.SPRINKLER,
        coordinates=Coordinates(20000, 0, 3.5),
        k_factor=80,
        min_pressure_required=0.5,
        coverage_area=12.0
    )
    network.add_node(spr1)
    
    # Sprinkler 2
    spr2 = Node(
        id="SPR2",
        node_type=NodeType.SPRINKLER,
        coordinates=Coordinates(10000, 5000, 3.5),
        k_factor=80,
        min_pressure_required=0.5,
        coverage_area=12.0
    )
    network.add_node(spr2)
    
    # Borular
    pipe1 = Pipe(
        id="P1",
        start_node_id="SOURCE",
        end_node_id="J1",
        length=10.0,
        internal_diameter=77.9,
        nominal_diameter=80,
        c_factor=120
    )
    pipe1.add_fitting(Fitting(category=FittingCategory.GATE_VALVE, equivalent_length=0.3))
    network.add_pipe(pipe1)
    
    pipe2 = Pipe(
        id="P2",
        start_node_id="J1",
        end_node_id="SPR1",
        length=10.0,
        internal_diameter=52.5,
        nominal_diameter=50,
        c_factor=120
    )
    pipe2.add_fitting(Fitting(category=FittingCategory.TEE_FLOW_TURNED, equivalent_length=3.0))
    pipe2.add_fitting(Fitting(category=FittingCategory.ELBOW_90, equivalent_length=1.5))
    network.add_pipe(pipe2)
    
    pipe3 = Pipe(
        id="P3",
        start_node_id="J1",
        end_node_id="SPR2",
        length=5.0,
        internal_diameter=52.5,
        nominal_diameter=50,
        c_factor=120
    )
    network.add_pipe(pipe3)
    
    print(f"\nAğ: {network}")
    
    # Çözücüyü çalıştır
    solver = HydraulicSolver(network)
    solver.set_design_parameters(density=5.0, operating_area=150.0)
    
    result = solver.solve()
    solver.print_results()
