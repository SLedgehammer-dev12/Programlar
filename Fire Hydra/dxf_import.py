"""
FireHydra - DXF/DWG Import Modülü
=================================

DXF/DWG dosyalarından bina planlarını içe aktarma.

Özellikler:
- ezdxf kütüphanesi ile DXF okuma
- Layer seçimi ve filtreleme
- Koordinat dönüşümü (DXF → Canvas)
- Arka plan olarak görüntüleme
- Line, Circle, Arc, Polyline desteği
"""

# pyright: reportMissingImports=false

import os
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

# ezdxf (opsiyonel)
try:
    import ezdxf  # type: ignore
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False


class DXFEntityType(Enum):
    """DXF entity tipleri"""
    LINE = "LINE"
    CIRCLE = "CIRCLE"
    ARC = "ARC"
    POLYLINE = "POLYLINE"
    LWPOLYLINE = "LWPOLYLINE"
    OTHER = "OTHER"


@dataclass
class DXFLayer:
    """DXF Layer bilgisi"""
    name: str
    color: int = 7  # Beyaz
    is_frozen: bool = False
    is_locked: bool = False
    entity_count: int = 0


@dataclass
class DXFBounds:
    """DXF dosyası sınırları"""
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    
    @property
    def width(self) -> float:
        return self.max_x - self.min_x
    
    @property
    def height(self) -> float:
        return self.max_y - self.min_y
    
    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2
    
    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2


@dataclass
class DXFGeometry:
    """DXF geometrik entity"""
    entity_type: DXFEntityType
    layer: str
    color: int
    points: List[Tuple[float, float]]  # (x, y) koordinatları
    
    # Daire/Arc için
    center: Optional[Tuple[float, float]] = None
    radius: Optional[float] = None
    start_angle: Optional[float] = None  # Derece
    end_angle: Optional[float] = None    # Derece


class DXFImporter:
    """
    DXF/DWG Import Sınıfı
    
    DXF dosyalarını okur ve FireHydra canvas'ına uygun formata dönüştürür.
    """
    
    def __init__(self):
        # ezdxf mevcut değilse type bilgisi Any ile temsil edilir
        self.doc: Optional[Any] = None
        self.filepath: str = ""
        self.layers: List[DXFLayer] = []
        self.bounds: Optional[DXFBounds] = None
        self.geometries: List[DXFGeometry] = []
    
    def load_file(self, filepath: str) -> bool:
        """
        DXF dosyasını yükle
        
        Args:
            filepath: DXF dosya yolu
            
        Returns:
            Başarılı ise True
        """
        if not HAS_EZDXF:
            print("HATA: ezdxf kütüphanesi yüklü değil. 'pip install ezdxf' ile yükleyin.")
            return False
        
        if not os.path.exists(filepath):
            print(f"HATA: Dosya bulunamadı: {filepath}")
            return False
        
        try:
            # DXF oku
            self.doc = ezdxf.readfile(filepath)
            self.filepath = filepath
            
            # Layer'ları analiz et
            self._analyze_layers()
            
            # Sınırları hesapla
            self._calculate_bounds()
            
            return True
            
        except Exception as e:
            print(f"DXF yükleme hatası: {e}")
            return False
    
    def _analyze_layers(self):
        """Layer'ları analiz et"""
        self.layers = []
        
        if not self.doc:
            return
        
        # Layer tanımlarını al
        layer_table = self.doc.layers
        
        for layer in layer_table:
            # Entity sayısını hesapla
            entity_count = 0
            modelspace = self.doc.modelspace()
            
            for entity in modelspace:
                if entity.dxf.layer == layer.dxf.name:
                    entity_count += 1
            
            dxf_layer = DXFLayer(
                name=layer.dxf.name,
                color=layer.dxf.color,
                is_frozen=layer.is_frozen(),
                is_locked=layer.is_locked(),
                entity_count=entity_count
            )
            
            self.layers.append(dxf_layer)
    
    def _calculate_bounds(self):
        """Dosya sınırlarını hesapla"""
        if not self.doc:
            return
        
        modelspace = self.doc.modelspace()
        
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for entity in modelspace:
            # Entity tipine göre sınırları al
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                
                min_x = min(min_x, start.x, end.x)
                min_y = min(min_y, start.y, end.y)
                max_x = max(max_x, start.x, end.x)
                max_y = max(max_y, start.y, end.y)
            
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                
                min_x = min(min_x, center.x - radius)
                min_y = min(min_y, center.y - radius)
                max_x = max(max_x, center.x + radius)
                max_y = max(max_y, center.y + radius)
            
            elif entity.dxftype() in ('LWPOLYLINE', 'POLYLINE'):
                for point in entity.get_points():
                    min_x = min(min_x, point[0])
                    min_y = min(min_y, point[1])
                    max_x = max(max_x, point[0])
                    max_y = max(max_y, point[1])
        
        if min_x != float('inf'):
            self.bounds = DXFBounds(min_x, min_y, max_x, max_y)
    
    def extract_geometries(self, selected_layers: Optional[List[str]] = None) -> List[DXFGeometry]:
        """
        Seçili layer'lardan geometrileri çıkart
        
        Args:
            selected_layers: Seçili layer isimleri (None ise hepsi)
            
        Returns:
            DXFGeometry listesi
        """
        if not self.doc:
            return []
        
        self.geometries = []
        modelspace = self.doc.modelspace()
        
        for entity in modelspace:
            layer_name = entity.dxf.layer
            
            # Layer filtresi
            if selected_layers and layer_name not in selected_layers:
                continue
            
            # Skip frozen/invisible layers
            if entity.dxf.invisible:
                continue
            
            # Entity tipine göre işle
            geom = None
            
            if entity.dxftype() == 'LINE':
                geom = self._extract_line(entity)
            
            elif entity.dxftype() == 'CIRCLE':
                geom = self._extract_circle(entity)
            
            elif entity.dxftype() == 'ARC':
                geom = self._extract_arc(entity)
            
            elif entity.dxftype() in ('LWPOLYLINE', 'POLYLINE'):
                geom = self._extract_polyline(entity)
            
            if geom:
                self.geometries.append(geom)
        
        return self.geometries
    
    def _extract_line(self, entity) -> DXFGeometry:
        """LINE entity'sini çıkart"""
        start = entity.dxf.start
        end = entity.dxf.end
        
        return DXFGeometry(
            entity_type=DXFEntityType.LINE,
            layer=entity.dxf.layer,
            color=entity.dxf.color,
            points=[(start.x, start.y), (end.x, end.y)]
        )
    
    def _extract_circle(self, entity) -> DXFGeometry:
        """CIRCLE entity'sini çıkart"""
        center = entity.dxf.center
        
        return DXFGeometry(
            entity_type=DXFEntityType.CIRCLE,
            layer=entity.dxf.layer,
            color=entity.dxf.color,
            points=[],
            center=(center.x, center.y),
            radius=entity.dxf.radius
        )
    
    def _extract_arc(self, entity) -> DXFGeometry:
        """ARC entity'sini çıkart"""
        center = entity.dxf.center
        
        return DXFGeometry(
            entity_type=DXFEntityType.ARC,
            layer=entity.dxf.layer,
            color=entity.dxf.color,
            points=[],
            center=(center.x, center.y),
            radius=entity.dxf.radius,
            start_angle=entity.dxf.start_angle,
            end_angle=entity.dxf.end_angle
        )
    
    def _extract_polyline(self, entity) -> DXFGeometry:
        """POLYLINE/LWPOLYLINE entity'sini çıkart"""
        points = []
        
        for point in entity.get_points():
            points.append((point[0], point[1]))
        
        return DXFGeometry(
            entity_type=DXFEntityType.POLYLINE,
            layer=entity.dxf.layer,
            color=entity.dxf.color,
            points=points
        )
    
    def transform_to_canvas(self, geom: DXFGeometry, 
                           canvas_width: int, canvas_height: int,
                           scale: float = 1.0, 
                           offset_x: float = 0, offset_y: float = 0) -> DXFGeometry:
        """
        Geometriyi canvas koordinatlarına dönüştür
        
        Args:
            geom: DXF geometri
            canvas_width: Canvas genişliği
            canvas_height: Canvas yüksekliği
            scale: Ölçek faktörü
            offset_x: X ofseti
            offset_y: Y ofseti
            
        Returns:
            Dönüştürülmüş geometri
        """
        if not self.bounds:
            return geom
        
        # Otomatik merkez ve ölçek hesapla
        if scale == 1.0:
            # Canvas'a sığdır
            scale_x = (canvas_width * 0.8) / self.bounds.width
            scale_y = (canvas_height * 0.8) / self.bounds.height
            scale = min(scale_x, scale_y)
        
        if offset_x == 0 and offset_y == 0:
            # Merkeze hizala
            offset_x = canvas_width / 2 - (self.bounds.center_x * scale)
            offset_y = canvas_height / 2 + (self.bounds.center_y * scale)  # Y ters
        
        # Koordinatları dönüştür
        def transform_point(x: float, y: float) -> Tuple[float, float]:
            # DXF koordinatları (mm) → Canvas koordinatları (px)
            canvas_x = x * scale + offset_x
            canvas_y = -y * scale + offset_y  # Y ekseni ters
            return (canvas_x, canvas_y)
        
        # Yeni geometri oluştur
        new_geom = DXFGeometry(
            entity_type=geom.entity_type,
            layer=geom.layer,
            color=geom.color,
            points=[transform_point(x, y) for x, y in geom.points]
        )
        
        # Daire/Arc parametrelerini dönüştür
        if geom.center:
            new_geom.center = transform_point(geom.center[0], geom.center[1])
            new_geom.radius = geom.radius * scale if geom.radius else None
            new_geom.start_angle = geom.start_angle
            new_geom.end_angle = geom.end_angle
        
        return new_geom
    
    def get_layer_names(self) -> List[str]:
        """Layer isimlerini al"""
        return [layer.name for layer in self.layers]
    
    def get_layer_info(self, layer_name: str) -> Optional[DXFLayer]:
        """Layer bilgisini al"""
        for layer in self.layers:
            if layer.name == layer_name:
                return layer
        return None


# ==================== Test ====================
if __name__ == "__main__":
    print("FireHydra DXF Import Testi")
    print("=" * 50)
    
    if not HAS_EZDXF:
        print("HATA: ezdxf kütüphanesi yüklü değil!")
        print("Yüklemek için: pip install ezdxf")
    else:
        print("ezdxf kütüphanesi yüklü ✓")
        
        # Test dosyası
        test_file = "test_plan.dxf"
        
        if os.path.exists(test_file):
            importer = DXFImporter()
            
            if importer.load_file(test_file):
                print(f"\nDosya yüklendi: {test_file}")
                print(f"Layer sayısı: {len(importer.layers)}")
                
                for layer in importer.layers:
                    print(f"  - {layer.name}: {layer.entity_count} entity")
                
                if importer.bounds:
                    print(f"\nSınırlar:")
                    print(f"  X: {importer.bounds.min_x:.2f} → {importer.bounds.max_x:.2f}")
                    print(f"  Y: {importer.bounds.min_y:.2f} → {importer.bounds.max_y:.2f}")
                    print(f"  Boyut: {importer.bounds.width:.2f} x {importer.bounds.height:.2f}")
                
                # Geometrileri çıkart
                geometries = importer.extract_geometries()
                print(f"\nÇıkarılan geometri sayısı: {len(geometries)}")
                
                # Tip dağılımı
                type_counts = {}
                for geom in geometries:
                    type_name = geom.entity_type.value
                    type_counts[type_name] = type_counts.get(type_name, 0) + 1
                
                for type_name, count in type_counts.items():
                    print(f"  {type_name}: {count}")
        else:
            print(f"\nTest dosyası bulunamadı: {test_file}")
    
    print("\nTest tamamlandı!")
