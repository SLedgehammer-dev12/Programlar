"""
FireHydra - Veri Modelleri (Models)
===================================

Graph (Çizge) Teorisi tabanlı veri yapıları:
- Node: Düğüm sınıfı (Sprinkler, Fitting, Source, Junction, Cap)
- Pipe: Boru sınıfı (iki Node arasındaki bağlantı)
- Fitting: Ek parça sınıfı (Dirsek, Vana, T-Parça vb.)
- PipeNetwork: Tüm sistemi temsil eden Graph yapısı
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Tuple
from enum import Enum
import math
import uuid
from datetime import datetime


class DesignStandard(Enum):
    """Tasarım standartları"""
    NFPA_13 = "NFPA 13"
    NFPA_13R = "NFPA 13R"
    NFPA_13D = "NFPA 13D"
    TS_EN_12845 = "TS EN 12845"
    BYKHY_2017 = "BYKHY 2017"
    FM_GLOBAL = "FM Global"


class HazardClass(Enum):
    """Tehlike sınıfı"""
    LIGHT = "Light Hazard (Hafif)"
    ORDINARY_1 = "Ordinary Hazard Group 1 (Orta Tehlike Grup 1)"
    ORDINARY_2 = "Ordinary Hazard Group 2 (Orta Tehlike Grup 2)"
    EXTRA_1 = "Extra Hazard Group 1 (Yüksek Tehlike Grup 1)"
    EXTRA_2 = "Extra Hazard Group 2 (Yüksek Tehlike Grup 2)"
    STORAGE_1 = "Storage Class I-IV (Depolama Sınıf I-IV)"
    STORAGE_2 = "Storage Class V+ (Depolama Sınıf V+)"


@dataclass
class ProjectSettings:
    """Proje ayarları ve bilgileri"""
    # Proje Bilgileri
    project_name: str = "Yeni Proje"
    project_number: str = ""
    location: str = ""
    client: str = ""
    engineer: str = ""
    date_created: str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y"))
    
    # Tasarım Parametreleri
    design_standard: DesignStandard = DesignStandard.NFPA_13
    hazard_class: HazardClass = HazardClass.ORDINARY_1
    
    # Varsayılan Değerler
    default_pipe_c_factor: float = 120.0  # Hazen-Williams C faktörü
    default_sprinkler_k_factor: float = 80.0  # Metrik K-faktör
    default_coverage_area: float = 12.0  # m²
    default_min_pressure: float = 0.5  # bar
    
    # Sistem Parametreleri
    design_density: float = 5.0  # mm/dk (Light Hazard için)
    design_area: float = 84.0  # m² (12 sprinkler için)
    min_residual_pressure: float = 0.5  # bar
    
    # Grid Ayarları
    grid_spacing: int = 1000  # mm
    snap_to_grid: bool = True
    
    # Birimler
    length_unit: str = "mm"  # mm, m, ft
    pressure_unit: str = "bar"  # bar, psi, kPa
    flow_unit: str = "L/dk"  # L/dk, L/min, gpm
    
    def get_design_density_for_hazard(self) -> float:
        """Tehlike sınıfına göre tasarım yoğunluğu"""
        density_map = {
            HazardClass.LIGHT: 2.5,
            HazardClass.ORDINARY_1: 5.0,
            HazardClass.ORDINARY_2: 6.5,
            HazardClass.EXTRA_1: 12.0,
            HazardClass.EXTRA_2: 15.0,
        }
        return density_map.get(self.hazard_class, 5.0)
    
    def get_design_area_for_hazard(self) -> float:
        """Tehlike sınıfına göre tasarım alanı (m²)"""
        area_map = {
            HazardClass.LIGHT: 84.0,  # 12 sprinkler
            HazardClass.ORDINARY_1: 140.0,  # ~20 sprinkler
            HazardClass.ORDINARY_2: 140.0,
            HazardClass.EXTRA_1: 232.0,  # ~33 sprinkler
            HazardClass.EXTRA_2: 232.0,
        }
        return area_map.get(self.hazard_class, 140.0)


class NodeType(Enum):
    """Düğüm tipleri"""
    SPRINKLER = "Sprinkler"
    FITTING = "Fitting"
    SOURCE = "Source"        # Pompa çıkışı / Su kaynağı
    JUNCTION = "Junction"    # T-Bağlantı noktası
    CAP = "Cap"              # Kör tapa / Uç nokta
    RISER = "Riser"          # Dikey boru (Yükseliş)


class FittingCategory(Enum):
    """Fitting kategorileri"""
    ELBOW_90 = "Elbow_90"
    ELBOW_45 = "Elbow_45"
    TEE_FLOW_TURNED = "Tee_Flow_Turned"
    TEE_FLOW_STRAIGHT = "Tee_Flow_Straight"
    GATE_VALVE = "Gate_Valve"
    CHECK_VALVE = "Check_Valve_Swing"
    BUTTERFLY_VALVE = "Butterfly_Valve"
    ALARM_VALVE = "Alarm_Valve"
    REDUCER = "Reducer"


@dataclass
class Coordinates:
    """3D Koordinat yapısı"""
    x: float = 0.0  # Canvas X (mm veya piksel)
    y: float = 0.0  # Canvas Y (mm veya piksel)
    z: float = 0.0  # Yükseklik / Kot (metre) - Hidrolik hesap için kritik
    
    def distance_2d(self, other: 'Coordinates') -> float:
        """2D mesafe hesabı (x, y)"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def distance_3d(self, other: 'Coordinates') -> float:
        """3D mesafe hesabı"""
        return math.sqrt(
            (self.x - other.x)**2 + 
            (self.y - other.y)**2 + 
            (self.z - other.z)**2
        )
    
    def elevation_difference(self, other: 'Coordinates') -> float:
        """Kot farkı (metre)"""
        return self.z - other.z
    
    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)
    
    def __str__(self):
        return f"({self.x:.1f}, {self.y:.1f}, z={self.z:.2f}m)"


@dataclass
class Fitting:
    """Boru ek parçası (Dirsek, Vana vb.)"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: FittingCategory = FittingCategory.ELBOW_90
    equivalent_length: float = 0.0  # Metre
    description: str = ""
    
    def __str__(self):
        return f"{self.category.value} (Eq.L={self.equivalent_length:.2f}m)"


@dataclass
class Node:
    """
    Düğüm (Node) Sınıfı
    
    Her boru ucu, dirsek, T-parça veya sprinkler bir Node'dur.
    Graph yapısında vertex (köşe) görevi görür.
    """
    id: str = field(default_factory=lambda: f"N_{uuid.uuid4().hex[:6]}")
    node_type: NodeType = NodeType.FITTING
    coordinates: Coordinates = field(default_factory=Coordinates)
    
    # Hesaplama Sonuçları (başlangıçta None)
    pressure: Optional[float] = None  # Bar
    total_flow: Optional[float] = None  # L/dk
    
    # Sprinkler özellikleri (sadece SPRINKLER tipi için)
    k_factor: float = 80.0  # Metrik K-faktör
    min_pressure_required: float = 0.5  # Bar (minimum açılma basıncı)
    coverage_area: float = 12.0  # m² (koruma alanı)
    
    # Bağlı borular (Graph bağlantıları)
    connected_pipe_ids: List[str] = field(default_factory=list)
    
    # Hesaplama durumu
    is_calculated: bool = False
    calculation_order: int = -1  # Hesaplama sırası
    
    # Görsel özellikler (UI için)
    label: str = ""
    color: str = "#000000"
    
    def get_elevation(self) -> float:
        """Kot değerini metre cinsinden döndür"""
        return self.coordinates.z
    
    def set_elevation(self, elevation_m: float):
        """Kot değerini ayarla"""
        self.coordinates.z = elevation_m
    
    def calculate_sprinkler_flow(self, density_mmpm: Optional[float] = None) -> float:
        """
        Sprinkler debisini hesapla
        
        Kural 1 (Alan Bazlı): Q_area = Density × Coverage_Area
        Kural 2 (Basınç Bazlı): Q_pressure = K × √P_min
        Sonuç: Q = max(Q_area, Q_pressure)
        """
        if self.node_type != NodeType.SPRINKLER:
            return 0.0
        
        # Basınç bazlı minimum debi
        q_pressure = self.k_factor * math.sqrt(self.min_pressure_required)
        
        # Alan bazlı minimum debi
        q_area = 0.0
        if density_mmpm is not None:
            q_area = density_mmpm * self.coverage_area
        
        return max(q_pressure, q_area)
    
    def calculate_pressure_from_flow(self, flow_lpm: float) -> float:
        """
        Verilen debiden sprinkler basıncını hesapla
        P = (Q / K)²
        """
        if self.k_factor <= 0:
            return 0.0
        return (flow_lpm / self.k_factor) ** 2
    
    def is_sprinkler(self) -> bool:
        return self.node_type == NodeType.SPRINKLER
    
    def is_source(self) -> bool:
        return self.node_type == NodeType.SOURCE
    
    def is_junction(self) -> bool:
        return self.node_type == NodeType.JUNCTION
    
    def __str__(self):
        p_str = f"{self.pressure:.2f} bar" if self.pressure else "N/A"
        q_str = f"{self.total_flow:.1f} L/dk" if self.total_flow else "N/A"
        return f"Node({self.id}, {self.node_type.value}, P={p_str}, Q={q_str})"
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Node):
            return self.id == other.id
        return False


@dataclass
class Pipe:
    """
    Boru (Pipe) Sınıfı
    
    İki Node arasındaki bağlantıyı temsil eder.
    Graph yapısında edge (kenar) görevi görür.
    """
    id: str = field(default_factory=lambda: f"P_{uuid.uuid4().hex[:6]}")
    start_node_id: str = ""  # Kaynak tarafa yakın node
    end_node_id: str = ""    # Uç tarafa yakın node
    
    # Fiziksel özellikler
    length: float = 0.0  # Metre (geometrik uzunluk)
    internal_diameter: float = 52.5  # mm (iç çap)
    nominal_diameter: float = 50.0  # mm (nominal çap)
    c_factor: float = 120.0  # Hazen-Williams C değeri
    material: str = "Steel"
    
    # Fitting listesi
    fittings: List[Fitting] = field(default_factory=list)
    
    # Hesaplama sonuçları
    flow: Optional[float] = None  # L/dk
    velocity: Optional[float] = None  # m/s
    friction_loss: Optional[float] = None  # Bar
    friction_loss_per_meter: Optional[float] = None  # Bar/m
    
    # Yön bilgisi
    is_vertical: bool = False  # Dikey boru (riser)
    elevation_change: float = 0.0  # Başlangıç-bitiş kot farkı (m)
    
    # Görsel özellikler
    color: str = "#0066CC"
    line_width: float = 2.0
    
    def get_total_equivalent_length(self) -> float:
        """
        Toplam eşdeğer uzunluk hesabı
        L_total = L_physical + Σ(L_eq_fittings)
        """
        fitting_eq_length = sum(f.equivalent_length for f in self.fittings)
        return self.length + fitting_eq_length
    
    def get_fitting_equivalent_length(self) -> float:
        """Sadece fittinglerin eşdeğer uzunluk toplamı"""
        return sum(f.equivalent_length for f in self.fittings)
    
    def add_fitting(self, fitting: Fitting):
        """Boruya fitting ekle"""
        self.fittings.append(fitting)
    
    def remove_fitting(self, fitting_id: str):
        """Fitting kaldır"""
        self.fittings = [f for f in self.fittings if f.id != fitting_id]
    
    def calculate_velocity(self, flow_lpm: float) -> float:
        """
        Akış hızını hesapla (m/s)
        v = Q / A = (Q / 1000 / 60) / (π × d² / 4)
        Q: L/dk, d: m
        """
        if self.internal_diameter <= 0:
            return 0.0
        
        d_m = self.internal_diameter / 1000  # mm -> m
        area = math.pi * (d_m ** 2) / 4  # m²
        q_m3s = flow_lpm / 1000 / 60  # L/dk -> m³/s
        
        return q_m3s / area if area > 0 else 0.0
    
    def calculate_friction_loss(self, flow_lpm: float) -> float:
        """
        Hazen-Williams sürtünme kaybı hesabı (Bar)
        
        P_loss = (6.05 × 10^5 × L × Q^1.85) / (C^1.85 × d^4.87)
        
        Args:
            flow_lpm: Debi (L/dk)
            
        Returns:
            Basınç kaybı (Bar)
        """
        if flow_lpm <= 0 or self.internal_diameter <= 0 or self.c_factor <= 0:
            return 0.0
        
        L = self.get_total_equivalent_length()  # Toplam eşdeğer uzunluk
        Q = flow_lpm
        C = self.c_factor
        d = self.internal_diameter  # mm
        
        # Hazen-Williams metrik formül
        numerator = 6.05 * (10 ** 5) * L * (Q ** 1.85)
        denominator = (C ** 1.85) * (d ** 4.87)
        
        return numerator / denominator if denominator > 0 else 0.0
    
    def calculate_friction_loss_per_meter(self, flow_lpm: float) -> float:
        """Metre başına sürtünme kaybı (Bar/m)"""
        total_loss = self.calculate_friction_loss(flow_lpm)
        L = self.get_total_equivalent_length()
        return total_loss / L if L > 0 else 0.0
    
    def update_flow_calculations(self, flow_lpm: float):
        """Akış hesaplamalarını güncelle"""
        self.flow = flow_lpm
        self.velocity = self.calculate_velocity(flow_lpm)
        self.friction_loss = self.calculate_friction_loss(flow_lpm)
        self.friction_loss_per_meter = self.calculate_friction_loss_per_meter(flow_lpm)
    
    def check_velocity_limit(self, max_velocity: float = 6.0) -> bool:
        """
        Hız limitini kontrol et
        NFPA 13: Maksimum 6 m/s (bazı durumlarda 10 m/s)
        """
        if self.velocity is None:
            return True
        return self.velocity <= max_velocity
    
    def __str__(self):
        q_str = f"{self.flow:.1f} L/dk" if self.flow else "N/A"
        v_str = f"{self.velocity:.2f} m/s" if self.velocity else "N/A"
        return f"Pipe({self.id}, D={self.nominal_diameter}mm, L={self.length:.2f}m, Q={q_str}, v={v_str})"
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Pipe):
            return self.id == other.id
        return False


class PipeNetwork:
    """
    Boru Ağı (Pipe Network) - Graph Yapısı
    
    Tüm Node'ları ve Pipe'ları içeren graf yapısı.
    Hidrolik hesaplama ve traversal (gezinme) işlemlerini yönetir.
    """
    
    def __init__(self, name: str = "Yeni Proje"):
        self.name = name
        self.nodes: Dict[str, Node] = {}  # node_id -> Node
        self.pipes: Dict[str, Pipe] = {}  # pipe_id -> Pipe
        
        # Graph adjacency (komşuluk) yapısı
        self._adjacency: Dict[str, Set[str]] = {}  # node_id -> set of connected node_ids
        
        # Kaynak düğümü (Pompa çıkışı)
        self.source_node_id: Optional[str] = None
        
        # Hesaplama sonuçları
        self.total_system_flow: float = 0.0  # L/dk
        self.total_system_pressure: float = 0.0  # Bar
        self.is_calculated: bool = False
        
    def add_node(self, node: Node) -> str:
        """Düğüm ekle"""
        self.nodes[node.id] = node
        self._adjacency[node.id] = set()
        
        # Source düğümü otomatik ata
        if node.node_type == NodeType.SOURCE and self.source_node_id is None:
            self.source_node_id = node.id
            
        return node.id
    
    def remove_node(self, node_id: str) -> bool:
        """Düğüm kaldır"""
        if node_id not in self.nodes:
            return False
        
        # Bağlı boruları da kaldır
        connected_pipes = self.get_connected_pipes(node_id)
        for pipe in connected_pipes:
            self.remove_pipe(pipe.id)
        
        # Adjacency'den kaldır
        del self._adjacency[node_id]
        for adj_set in self._adjacency.values():
            adj_set.discard(node_id)
        
        # Node'u kaldır
        del self.nodes[node_id]
        return True
    
    def add_pipe(self, pipe: Pipe) -> str:
        """Boru ekle ve Graph bağlantılarını güncelle"""
        # Node'ların varlığını kontrol et
        if pipe.start_node_id not in self.nodes:
            raise ValueError(f"Başlangıç düğümü bulunamadı: {pipe.start_node_id}")
        if pipe.end_node_id not in self.nodes:
            raise ValueError(f"Bitiş düğümü bulunamadı: {pipe.end_node_id}")
        
        self.pipes[pipe.id] = pipe
        
        # Adjacency güncelle (çift yönlü)
        self._adjacency[pipe.start_node_id].add(pipe.end_node_id)
        self._adjacency[pipe.end_node_id].add(pipe.start_node_id)
        
        # Node'lara boru referansı ekle
        self.nodes[pipe.start_node_id].connected_pipe_ids.append(pipe.id)
        self.nodes[pipe.end_node_id].connected_pipe_ids.append(pipe.id)
        
        # Kot farkını hesapla
        start_z = self.nodes[pipe.start_node_id].get_elevation()
        end_z = self.nodes[pipe.end_node_id].get_elevation()
        pipe.elevation_change = end_z - start_z
        
        return pipe.id
    
    def remove_pipe(self, pipe_id: str) -> bool:
        """Boru kaldır"""
        if pipe_id not in self.pipes:
            return False
        
        pipe = self.pipes[pipe_id]
        
        # Adjacency güncelle
        self._adjacency[pipe.start_node_id].discard(pipe.end_node_id)
        self._adjacency[pipe.end_node_id].discard(pipe.start_node_id)
        
        # Node referanslarından kaldır
        if pipe.start_node_id in self.nodes:
            self.nodes[pipe.start_node_id].connected_pipe_ids.remove(pipe_id)
        if pipe.end_node_id in self.nodes:
            self.nodes[pipe.end_node_id].connected_pipe_ids.remove(pipe_id)
        
        del self.pipes[pipe_id]
        return True
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Node getir"""
        return self.nodes.get(node_id)
    
    def get_pipe(self, pipe_id: str) -> Optional[Pipe]:
        """Pipe getir"""
        return self.pipes.get(pipe_id)
    
    def get_connected_nodes(self, node_id: str) -> List[Node]:
        """Bir düğüme bağlı tüm düğümleri getir"""
        if node_id not in self._adjacency:
            return []
        return [self.nodes[nid] for nid in self._adjacency[node_id] if nid in self.nodes]
    
    def get_connected_pipes(self, node_id: str) -> List[Pipe]:
        """Bir düğüme bağlı tüm boruları getir"""
        if node_id not in self.nodes:
            return []
        return [self.pipes[pid] for pid in self.nodes[node_id].connected_pipe_ids if pid in self.pipes]
    
    def get_pipe_between_nodes(self, node1_id: str, node2_id: str) -> Optional[Pipe]:
        """İki düğüm arasındaki boruyu getir"""
        for pipe in self.pipes.values():
            if (pipe.start_node_id == node1_id and pipe.end_node_id == node2_id) or \
               (pipe.start_node_id == node2_id and pipe.end_node_id == node1_id):
                return pipe
        return None
    
    def get_sprinklers(self) -> List[Node]:
        """Tüm sprinklerleri getir"""
        return [n for n in self.nodes.values() if n.node_type == NodeType.SPRINKLER]
    
    def get_source_node(self) -> Optional[Node]:
        """Kaynak düğümünü getir"""
        if self.source_node_id:
            return self.nodes.get(self.source_node_id)
        return None
    
    def find_path_to_source(self, start_node_id: str) -> List[str]:
        """
        Bir düğümden kaynağa (pompa) giden yolu bul (BFS)
        
        Returns:
            Node ID listesi (başlangıçtan kaynağa)
        """
        if not self.source_node_id or start_node_id == self.source_node_id:
            return [start_node_id]
        
        # BFS
        from collections import deque
        
        visited = set()
        queue = deque([(start_node_id, [start_node_id])])
        
        while queue:
            current, path = queue.popleft()
            
            if current == self.source_node_id:
                return path
            
            if current in visited:
                continue
            visited.add(current)
            
            for neighbor_id in self._adjacency.get(current, set()):
                if neighbor_id not in visited:
                    queue.append((neighbor_id, path + [neighbor_id]))
        
        return []  # Yol bulunamadı
    
    def find_most_remote_sprinkler(self) -> Optional[Node]:
        """
        Hidrolik olarak en uzak sprinkler'ı bul
        Kriterleri:
        1. Kaynağa en uzak (boru uzunluğu toplamı)
        2. En yüksek kotta
        """
        sprinklers = self.get_sprinklers()
        if not sprinklers:
            return None
        
        if not self.source_node_id:
            return sprinklers[0]
        
        max_distance = -1
        max_elevation = -float('inf')
        remote_sprinkler = None
        
        for sprinkler in sprinklers:
            path = self.find_path_to_source(sprinkler.id)
            
            # Yol boyunca toplam boru uzunluğu
            total_length = 0
            for i in range(len(path) - 1):
                pipe = self.get_pipe_between_nodes(path[i], path[i + 1])
                if pipe:
                    total_length += pipe.length
            
            elevation = sprinkler.get_elevation()
            
            # En uzak ve en yüksek olanı seç
            if total_length > max_distance or \
               (total_length == max_distance and elevation > max_elevation):
                max_distance = total_length
                max_elevation = elevation
                remote_sprinkler = sprinkler
        
        return remote_sprinkler
    
    def split_pipe_at_point(self, pipe_id: str, split_point: Coordinates, 
                           new_node_type: NodeType = NodeType.JUNCTION) -> Optional[Tuple[Node, Pipe, Pipe]]:
        """
        Bir boruyu belirtilen noktada ikiye böl
        
        Auto-Split algoritması:
        1. Eski boruyu sil
        2. Yeni bir Junction node oluştur
        3. İki yeni boru oluştur (Pipe_A_New ve Pipe_New_B)
        
        Returns:
            (new_node, pipe1, pipe2) veya None
        """
        if pipe_id not in self.pipes:
            return None
        
        old_pipe = self.pipes[pipe_id]
        start_node = self.nodes[old_pipe.start_node_id]
        end_node = self.nodes[old_pipe.end_node_id]
        
        # Yeni junction node oluştur
        new_node = Node(
            node_type=new_node_type,
            coordinates=split_point,
        )
        self.add_node(new_node)
        
        # Başlangıç-yeni node arası uzunluk
        length1 = start_node.coordinates.distance_2d(split_point) / 1000  # mm -> m
        
        # Yeni node-bitiş arası uzunluk
        length2 = split_point.distance_2d(end_node.coordinates) / 1000  # mm -> m
        
        # Oranları hesapla (fittingleri paylaştırmak için)
        total_length = old_pipe.length
        ratio1 = length1 / total_length if total_length > 0 else 0.5
        
        # İlk boru (start -> new_node)
        pipe1 = Pipe(
            start_node_id=start_node.id,
            end_node_id=new_node.id,
            length=length1,
            internal_diameter=old_pipe.internal_diameter,
            nominal_diameter=old_pipe.nominal_diameter,
            c_factor=old_pipe.c_factor,
            material=old_pipe.material,
        )
        
        # İkinci boru (new_node -> end)
        pipe2 = Pipe(
            start_node_id=new_node.id,
            end_node_id=end_node.id,
            length=length2,
            internal_diameter=old_pipe.internal_diameter,
            nominal_diameter=old_pipe.nominal_diameter,
            c_factor=old_pipe.c_factor,
            material=old_pipe.material,
        )
        
        # Eski boruyu kaldır ve yenileri ekle
        self.remove_pipe(pipe_id)
        self.add_pipe(pipe1)
        self.add_pipe(pipe2)
        
        return (new_node, pipe1, pipe2)
    
    def get_statistics(self) -> Dict:
        """Ağ istatistiklerini getir"""
        sprinklers = self.get_sprinklers()
        total_pipe_length = sum(p.length for p in self.pipes.values())
        
        return {
            "total_nodes": len(self.nodes),
            "total_pipes": len(self.pipes),
            "total_sprinklers": len(sprinklers),
            "total_pipe_length_m": total_pipe_length,
            "has_source": self.source_node_id is not None,
            "is_calculated": self.is_calculated,
            "system_flow_lpm": self.total_system_flow,
            "system_pressure_bar": self.total_system_pressure,
        }
    
    def reset_calculations(self):
        """Tüm hesaplama sonuçlarını sıfırla"""
        for node in self.nodes.values():
            node.pressure = None
            node.total_flow = None
            node.is_calculated = False
            node.calculation_order = -1
        
        for pipe in self.pipes.values():
            pipe.flow = None
            pipe.velocity = None
            pipe.friction_loss = None
            pipe.friction_loss_per_meter = None
        
        self.total_system_flow = 0.0
        self.total_system_pressure = 0.0
        self.is_calculated = False
    
    def __str__(self):
        stats = self.get_statistics()
        return (f"PipeNetwork('{self.name}', "
                f"Nodes={stats['total_nodes']}, "
                f"Pipes={stats['total_pipes']}, "
                f"Sprinklers={stats['total_sprinklers']})")


# ==================== Test / Demo ====================
if __name__ == "__main__":
    print("=" * 50)
    print("FireHydra Models Test")
    print("=" * 50)
    
    # Basit bir ağ oluştur
    network = PipeNetwork("Test Projesi")
    
    # Kaynak (Pompa) düğümü
    source = Node(
        id="N_SOURCE",
        node_type=NodeType.SOURCE,
        coordinates=Coordinates(0, 0, 0)
    )
    network.add_node(source)
    
    # Junction (T-Bağlantı)
    junction = Node(
        id="N_JUNCTION",
        node_type=NodeType.JUNCTION,
        coordinates=Coordinates(5000, 0, 3)  # 3m yükseklik
    )
    network.add_node(junction)
    
    # Sprinkler 1
    spr1 = Node(
        id="N_SPR1",
        node_type=NodeType.SPRINKLER,
        coordinates=Coordinates(10000, 0, 3.5),
        k_factor=80,
        min_pressure_required=0.5
    )
    network.add_node(spr1)
    
    # Sprinkler 2
    spr2 = Node(
        id="N_SPR2",
        node_type=NodeType.SPRINKLER,
        coordinates=Coordinates(10000, 3000, 3.5),
        k_factor=80,
        min_pressure_required=0.5
    )
    network.add_node(spr2)
    
    # Borular
    pipe1 = Pipe(
        id="P_1",
        start_node_id="N_SOURCE",
        end_node_id="N_JUNCTION",
        length=5.0,
        internal_diameter=77.9,
        nominal_diameter=80,
        c_factor=120
    )
    pipe1.add_fitting(Fitting(category=FittingCategory.GATE_VALVE, equivalent_length=0.3))
    network.add_pipe(pipe1)
    
    pipe2 = Pipe(
        id="P_2",
        start_node_id="N_JUNCTION",
        end_node_id="N_SPR1",
        length=5.0,
        internal_diameter=52.5,
        nominal_diameter=50,
        c_factor=120
    )
    pipe2.add_fitting(Fitting(category=FittingCategory.TEE_FLOW_TURNED, equivalent_length=3.0))
    network.add_pipe(pipe2)
    
    pipe3 = Pipe(
        id="P_3",
        start_node_id="N_JUNCTION",
        end_node_id="N_SPR2",
        length=3.0,
        internal_diameter=52.5,
        nominal_diameter=50,
        c_factor=120
    )
    network.add_pipe(pipe3)
    
    # Test sonuçları
    print(f"\n{network}")
    print(f"İstatistikler: {network.get_statistics()}")
    
    # En uzak sprinkler
    remote = network.find_most_remote_sprinkler()
    print(f"\nEn uzak sprinkler: {remote}")
    
    # Sprinkler debi hesabı
    for spr in network.get_sprinklers():
        q = spr.calculate_sprinkler_flow()
        print(f"  {spr.id}: Q = {q:.1f} L/dk")
    
    # Boru sürtünme kaybı testi
    print("\n--- Sürtünme Kaybı Testi ---")
    test_flow = 100  # L/dk
    for pipe in network.pipes.values():
        pipe.update_flow_calculations(test_flow)
        print(f"  {pipe.id}: ΔP = {pipe.friction_loss:.4f} Bar, v = {pipe.velocity:.2f} m/s")
    
    print("\nTest tamamlandı!")
