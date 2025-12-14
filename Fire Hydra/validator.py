"""
FireHydra - Doğrulama Modülü (Validator)
=========================================

Real-time validation ve uyarı sistemi.

Kontroller:
- Sprinkler mesafe kontrolleri
- Coverage area kontrolleri
- Minimum/maksimum basınç uyarıları
- Boru hızı kontrolleri
- NFPA standart uyumluluk
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math

from models import PipeNetwork, Node, Pipe, NodeType, ProjectSettings


class ValidationLevel(Enum):
    """Doğrulama seviyesi"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Doğrulama sorunu"""
    level: ValidationLevel
    category: str  # "Spacing", "Coverage", "Pressure", "Velocity", "Standard"
    message: str
    node_id: Optional[str] = None
    pipe_id: Optional[str] = None
    suggestion: Optional[str] = None
    
    def __str__(self):
        location = ""
        if self.node_id:
            location = f" [Node: {self.node_id}]"
        elif self.pipe_id:
            location = f" [Pipe: {self.pipe_id}]"
        
        return f"{self.level.value.upper()}: {self.message}{location}"


class NetworkValidator:
    """
    Ağ Doğrulayıcı
    
    NFPA 13 ve diğer standartlara göre ağı doğrular.
    """
    
    def __init__(self, network: PipeNetwork, settings: ProjectSettings):
        self.network = network
        self.settings = settings
        self.issues: List[ValidationIssue] = []
    
    def validate_all(self) -> List[ValidationIssue]:
        """Tüm kontrolleri yap"""
        self.issues.clear()
        
        self._check_sprinkler_spacing()
        self._check_coverage_area()
        self._check_pipe_velocity()
        self._check_minimum_pressure()
        self._check_isolated_nodes()
        self._check_standard_compliance()
        
        return self.issues
    
    def _check_sprinkler_spacing(self):
        """Sprinkler arası mesafeleri kontrol et"""
        sprinklers = [n for n in self.network.nodes.values() if n.node_type == NodeType.SPRINKLER]
        
        # NFPA 13: Minimum 1.8m (6 ft), Maksimum 4.6m (15 ft) sprinkler arası mesafe
        min_spacing = 1800  # mm
        max_spacing = 4600  # mm
        
        for i, sprinkler1 in enumerate(sprinklers):
            for sprinkler2 in sprinklers[i+1:]:
                distance = sprinkler1.coordinates.distance_2d(sprinkler2.coordinates)
                
                if distance < min_spacing:
                    self.issues.append(ValidationIssue(
                        level=ValidationLevel.WARNING,
                        category="Spacing",
                        message=f"Sprinkler arası mesafe çok kısa: {distance/1000:.2f}m (min: 1.8m)",
                        node_id=sprinkler1.id,
                        suggestion=f"Sprinkler'ı {sprinkler2.id} ile arasında en az 1.8m mesafe bırakın."
                    ))
                elif distance > max_spacing:
                    # Sadece birbirine bağlı olanları kontrol et
                    connected = self._are_nodes_connected(sprinkler1.id, sprinkler2.id)
                    if connected:
                        self.issues.append(ValidationIssue(
                            level=ValidationLevel.WARNING,
                            category="Spacing",
                            message=f"Sprinkler arası mesafe çok uzun: {distance/1000:.2f}m (max: 4.6m)",
                            node_id=sprinkler1.id,
                            suggestion="Araya ek sprinkler ekleyin veya mesafeyi azaltın."
                        ))
    
    def _check_coverage_area(self):
        """Kaplama alanı kontrolü"""
        sprinklers = [n for n in self.network.nodes.values() if n.node_type == NodeType.SPRINKLER]
        
        # NFPA 13: Light Hazard max 18.6 m², Ordinary Hazard max 12.1 m²
        max_coverage_map = {
            "Light Hazard": 18.6,
            "Ordinary": 12.1,
            "Extra Hazard": 9.3
        }
        
        # Tehlike sınıfına göre max coverage
        hazard_str = self.settings.hazard_class.value
        max_coverage = 12.1  # Varsayılan
        for key, value in max_coverage_map.items():
            if key in hazard_str:
                max_coverage = value
                break
        
        for sprinkler in sprinklers:
            coverage = sprinkler.coverage_area
            
            if coverage > max_coverage:
                self.issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="Coverage",
                    message=f"Kaplama alanı fazla: {coverage:.1f}m² (max: {max_coverage:.1f}m²)",
                    node_id=sprinkler.id,
                    suggestion=f"Kaplama alanını {max_coverage}m² veya daha az yapın."
                ))
            elif coverage < 6.0:
                self.issues.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    category="Coverage",
                    message=f"Kaplama alanı düşük: {coverage:.1f}m² (tipik: 9-12m²)",
                    node_id=sprinkler.id,
                    suggestion="Sprinkler aralığını artırarak kaplama alanını optimize edebilirsiniz."
                ))
    
    def _check_pipe_velocity(self):
        """Boru hızı kontrolü"""
        if not self.network.pipes:
            return
        
        # NFPA 13: Maksimum 6 m/s (20 ft/s) önerilir, 10 m/s mutlak maksimum
        max_velocity_recommended = 6.0  # m/s
        max_velocity_absolute = 10.0  # m/s
        
        for pipe in self.network.pipes.values():
            if pipe.flow_rate and pipe.flow_rate > 0:
                # Hız hesapla: V = Q / A
                # Q: m³/s, A: m²
                flow_m3s = (pipe.flow_rate / 60) / 1000  # L/dk -> m³/s
                diameter_m = pipe.internal_diameter / 1000  # mm -> m
                area_m2 = math.pi * (diameter_m / 2) ** 2
                
                velocity = flow_m3s / area_m2 if area_m2 > 0 else 0
                
                if velocity > max_velocity_absolute:
                    self.issues.append(ValidationIssue(
                        level=ValidationLevel.CRITICAL,
                        category="Velocity",
                        message=f"Boru hızı çok yüksek: {velocity:.2f} m/s (max: 10 m/s)",
                        pipe_id=pipe.id,
                        suggestion=f"Boru çapını artırın. Önerilen minimum çap: {self._suggest_diameter(pipe.flow_rate, max_velocity_recommended):.0f}mm"
                    ))
                elif velocity > max_velocity_recommended:
                    self.issues.append(ValidationIssue(
                        level=ValidationLevel.WARNING,
                        category="Velocity",
                        message=f"Boru hızı yüksek: {velocity:.2f} m/s (önerilen max: 6 m/s)",
                        pipe_id=pipe.id,
                        suggestion=f"Boru çapını {self._suggest_diameter(pipe.flow_rate, max_velocity_recommended):.0f}mm'ye çıkarmayı düşünün."
                    ))
    
    def _check_minimum_pressure(self):
        """Minimum basınç kontrolü"""
        sprinklers = [n for n in self.network.nodes.values() if n.node_type == NodeType.SPRINKLER]
        
        for sprinkler in sprinklers:
            if sprinkler.pressure is not None:
                min_required = sprinkler.min_pressure_required or 0.5
                
                if sprinkler.pressure < min_required:
                    self.issues.append(ValidationIssue(
                        level=ValidationLevel.CRITICAL,
                        category="Pressure",
                        message=f"Basınç yetersiz: {sprinkler.pressure:.2f} bar (min: {min_required:.2f} bar)",
                        node_id=sprinkler.id,
                        suggestion="Pompa kapasitesini artırın veya boru çaplarını büyütün."
                    ))
                elif sprinkler.pressure < min_required * 1.1:
                    self.issues.append(ValidationIssue(
                        level=ValidationLevel.WARNING,
                        category="Pressure",
                        message=f"Basınç marjinal: {sprinkler.pressure:.2f} bar (min: {min_required:.2f} bar)",
                        node_id=sprinkler.id,
                        suggestion="Basınç marjını artırmayı düşünün."
                    ))
    
    def _check_isolated_nodes(self):
        """İzole node'ları kontrol et"""
        for node in self.network.nodes.values():
            neighbors = self.network.get_neighbors(node.id)
            
            if len(neighbors) == 0 and node.node_type != NodeType.SOURCE:
                self.issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="Connectivity",
                    message=f"İzole node: Hiçbir bağlantısı yok",
                    node_id=node.id,
                    suggestion="Node'u sisteme bağlayın."
                ))
            elif len(neighbors) == 1 and node.node_type == NodeType.SPRINKLER:
                # Dead-end sprinkler - bu normal olabilir
                self.issues.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    category="Connectivity",
                    message=f"Uç noktada sprinkler (dead-end)",
                    node_id=node.id,
                    suggestion="Normal bir durum, ancak sistem güvenilirliği için loop oluşturmayı düşünün."
                ))
    
    def _check_standard_compliance(self):
        """Standart uyumluluk kontrolü"""
        sprinklers = [n for n in self.network.nodes.values() if n.node_type == NodeType.SPRINKLER]
        
        # NFPA 13: Design area için minimum sprinkler sayısı
        design_area = self.settings.design_area
        avg_coverage = self.settings.default_coverage_area
        min_sprinklers = int(design_area / avg_coverage)
        
        if len(sprinklers) < min_sprinklers:
            self.issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                category="Standard",
                message=f"Tasarım alanı için yetersiz sprinkler: {len(sprinklers)} (önerilen min: {min_sprinklers})",
                suggestion=f"Tasarım alanı {design_area}m² için en az {min_sprinklers} sprinkler gerekir."
            ))
        
        # Kaynak kontrolü
        sources = [n for n in self.network.nodes.values() if n.node_type == NodeType.SOURCE]
        if len(sources) == 0:
            self.issues.append(ValidationIssue(
                level=ValidationLevel.CRITICAL,
                category="Standard",
                message="Su kaynağı (pompa) tanımlanmamış",
                suggestion="Sisteme en az bir kaynak node ekleyin."
            ))
    
    def _are_nodes_connected(self, node_id1: str, node_id2: str) -> bool:
        """İki node birbirine bağlı mı?"""
        for pipe in self.network.pipes.values():
            if (pipe.start_node_id == node_id1 and pipe.end_node_id == node_id2) or \
               (pipe.start_node_id == node_id2 and pipe.end_node_id == node_id1):
                return True
        return False
    
    def _suggest_diameter(self, flow_rate: float, max_velocity: float) -> float:
        """Verilen debi ve maksimum hız için önerilen çap (mm)"""
        # V = Q / A => A = Q / V => D = sqrt(4*A/pi)
        flow_m3s = (flow_rate / 60) / 1000  # L/dk -> m³/s
        area_m2 = flow_m3s / max_velocity
        diameter_m = math.sqrt(4 * area_m2 / math.pi)
        diameter_mm = diameter_m * 1000
        
        # En yakın standart çapa yuvarla
        standard_diameters = [25, 32, 40, 50, 65, 80, 100, 125, 150, 200]
        for d in standard_diameters:
            if d >= diameter_mm:
                return d
        
        return 200  # Maksimum
    
    def get_issues_by_level(self, level: ValidationLevel) -> List[ValidationIssue]:
        """Belirli seviyedeki sorunları getir"""
        return [issue for issue in self.issues if issue.level == level]
    
    def get_issues_by_category(self, category: str) -> List[ValidationIssue]:
        """Belirli kategorideki sorunları getir"""
        return [issue for issue in self.issues if issue.category == category]
    
    def has_critical_issues(self) -> bool:
        """Kritik sorun var mı?"""
        return any(issue.level == ValidationLevel.CRITICAL for issue in self.issues)
    
    def has_errors(self) -> bool:
        """Hata var mı?"""
        return any(issue.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL] 
                  for issue in self.issues)
    
    def get_summary(self) -> Dict[str, int]:
        """Özet istatistik"""
        return {
            "critical": len(self.get_issues_by_level(ValidationLevel.CRITICAL)),
            "error": len(self.get_issues_by_level(ValidationLevel.ERROR)),
            "warning": len(self.get_issues_by_level(ValidationLevel.WARNING)),
            "info": len(self.get_issues_by_level(ValidationLevel.INFO)),
            "total": len(self.issues)
        }
