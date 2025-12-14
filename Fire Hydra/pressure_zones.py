"""
Pressure Zone Management

Basınç bölgeleri yönetimi:
- Zone tanımlama ve sınırları
- Min/max basınç limitleri
- Renk kodlaması
- Bölge bazlı raporlama
"""

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json


class ZoneType(Enum):
    """Basınç bölgesi tipi"""
    STANDARD = "standard"  # Normal bölge
    HIGH_PRESSURE = "high_pressure"  # Yüksek basınç
    LOW_PRESSURE = "low_pressure"  # Düşük basınç
    CRITICAL = "critical"  # Kritik alan


@dataclass
class PressureZone:
    """
    Basınç bölgesi tanımı
    
    Attributes:
        id: Benzersiz ID
        name: Bölge adı
        zone_type: Bölge tipi
        min_pressure: Minimum basınç (bar)
        max_pressure: Maximum basınç (bar)
        color: Görsel renk (hex)
        nodes: Bölgedeki node ID'leri
        description: Açıklama
    """
    id: str
    name: str
    zone_type: ZoneType = ZoneType.STANDARD
    min_pressure: float = 1.0  # bar
    max_pressure: float = 10.0  # bar
    color: str = "#4CAF50"
    nodes: List[str] = field(default_factory=list)
    description: str = ""
    
    def __post_init__(self):
        if isinstance(self.zone_type, str):
            self.zone_type = ZoneType(self.zone_type)
    
    def is_pressure_valid(self, pressure: float) -> bool:
        """Basınç limit kontrolü"""
        return self.min_pressure <= pressure <= self.max_pressure
    
    def to_dict(self) -> Dict:
        """Dictionary'ye çevir"""
        return {
            'id': self.id,
            'name': self.name,
            'zone_type': self.zone_type.value,
            'min_pressure': self.min_pressure,
            'max_pressure': self.max_pressure,
            'color': self.color,
            'nodes': self.nodes.copy(),
            'description': self.description
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'PressureZone':
        """Dictionary'den oluştur"""
        return PressureZone(
            id=data['id'],
            name=data['name'],
            zone_type=ZoneType(data.get('zone_type', 'standard')),
            min_pressure=data.get('min_pressure', 1.0),
            max_pressure=data.get('max_pressure', 10.0),
            color=data.get('color', '#4CAF50'),
            nodes=data.get('nodes', []),
            description=data.get('description', '')
        )


class PressureZoneManager:
    """
    Basınç bölgeleri yöneticisi
    
    Bölge oluşturma, düzenleme, silme ve validation
    """
    
    def __init__(self):
        self.zones: Dict[str, PressureZone] = {}
        self._next_id = 1
    
    def add_zone(self, zone: PressureZone) -> None:
        """Yeni bölge ekle"""
        if not zone.id:
            zone.id = self._generate_id()
        self.zones[zone.id] = zone
    
    def remove_zone(self, zone_id: str) -> bool:
        """Bölge sil"""
        if zone_id in self.zones:
            del self.zones[zone_id]
            return True
        return False
    
    def get_zone(self, zone_id: str) -> Optional[PressureZone]:
        """Bölge al"""
        return self.zones.get(zone_id)
    
    def get_zone_by_node(self, node_id: str) -> Optional[PressureZone]:
        """Node'a göre bölge bul"""
        for zone in self.zones.values():
            if node_id in zone.nodes:
                return zone
        return None
    
    def assign_node_to_zone(self, node_id: str, zone_id: str) -> bool:
        """Node'u bölgeye ata"""
        # Önce başka bölgelerden kaldır
        self.remove_node_from_all_zones(node_id)
        
        # Yeni bölgeye ekle
        zone = self.get_zone(zone_id)
        if zone:
            if node_id not in zone.nodes:
                zone.nodes.append(node_id)
            return True
        return False
    
    def remove_node_from_all_zones(self, node_id: str) -> None:
        """Node'u tüm bölgelerden kaldır"""
        for zone in self.zones.values():
            if node_id in zone.nodes:
                zone.nodes.remove(node_id)
    
    def validate_zone_pressures(self, node_pressures: Dict[str, float]) -> Dict[str, List[str]]:
        """
        Bölge basınç limitlerini kontrol et
        
        Args:
            node_pressures: {node_id: pressure} dictionary
            
        Returns:
            {zone_id: [violated_node_ids]} dictionary
        """
        violations = {}
        
        for zone_id, zone in self.zones.items():
            violated_nodes = []
            
            for node_id in zone.nodes:
                pressure = node_pressures.get(node_id)
                if pressure is not None:
                    if not zone.is_pressure_valid(pressure):
                        violated_nodes.append(node_id)
            
            if violated_nodes:
                violations[zone_id] = violated_nodes
        
        return violations
    
    def get_zone_statistics(self, node_pressures: Dict[str, float]) -> Dict[str, Dict]:
        """
        Bölge istatistikleri
        
        Returns:
            {zone_id: {min, max, avg, node_count}}
        """
        stats = {}
        
        for zone_id, zone in self.zones.items():
            pressures = [node_pressures.get(nid) for nid in zone.nodes 
                        if nid in node_pressures]
            pressures = [p for p in pressures if p is not None]
            
            if pressures:
                stats[zone_id] = {
                    'min': min(pressures),
                    'max': max(pressures),
                    'avg': sum(pressures) / len(pressures),
                    'node_count': len(zone.nodes),
                    'pressure_count': len(pressures)
                }
            else:
                stats[zone_id] = {
                    'min': 0,
                    'max': 0,
                    'avg': 0,
                    'node_count': len(zone.nodes),
                    'pressure_count': 0
                }
        
        return stats
    
    def _generate_id(self) -> str:
        """Yeni ID oluştur"""
        zone_id = f"ZONE_{self._next_id:03d}"
        self._next_id += 1
        return zone_id
    
    def save_to_dict(self) -> Dict:
        """Dictionary'ye kaydet"""
        return {
            'zones': [zone.to_dict() for zone in self.zones.values()],
            'next_id': self._next_id
        }
    
    def load_from_dict(self, data: Dict) -> None:
        """Dictionary'den yükle"""
        self.zones.clear()
        for zone_data in data.get('zones', []):
            zone = PressureZone.from_dict(zone_data)
            self.zones[zone.id] = zone
        self._next_id = data.get('next_id', 1)


class PressureZoneDialog(tk.Toplevel):
    """
    Basınç bölgesi düzenleme dialogu
    """
    
    def __init__(self, parent, zone: Optional[PressureZone] = None):
        super().__init__(parent)
        
        self.zone = zone
        self.result: Optional[PressureZone] = None
        
        # Pencere ayarları
        title = "Bölge Düzenle" if zone else "Yeni Bölge"
        self.title(title)
        self.geometry("500x450")
        self.resizable(False, False)
        
        self._create_widgets()
        
        # Modal
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        
        # ID (salt okunur)
        if self.zone:
            ttk.Label(main_frame, text="ID:").grid(row=row, column=0, sticky=tk.W, pady=5)
            ttk.Label(main_frame, text=self.zone.id, foreground='gray').grid(
                row=row, column=1, sticky=tk.W, pady=5)
            row += 1
        
        # Bölge adı
        ttk.Label(main_frame, text="Bölge Adı:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=self.zone.name if self.zone else "")
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Bölge tipi
        ttk.Label(main_frame, text="Bölge Tipi:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(
            value=self.zone.zone_type.value if self.zone else ZoneType.STANDARD.value)
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=27)
        type_combo['values'] = [zt.value for zt in ZoneType]
        type_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Min basınç
        ttk.Label(main_frame, text="Min Basınç (bar):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.min_pressure_var = tk.DoubleVar(
            value=self.zone.min_pressure if self.zone else 1.0)
        ttk.Spinbox(main_frame, from_=0, to=20, increment=0.1,
                   textvariable=self.min_pressure_var, width=28).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Max basınç
        ttk.Label(main_frame, text="Max Basınç (bar):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.max_pressure_var = tk.DoubleVar(
            value=self.zone.max_pressure if self.zone else 10.0)
        ttk.Spinbox(main_frame, from_=0, to=20, increment=0.1,
                   textvariable=self.max_pressure_var, width=28).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Renk seçimi
        ttk.Label(main_frame, text="Renk:").grid(row=row, column=0, sticky=tk.W, pady=5)
        color_frame = ttk.Frame(main_frame)
        color_frame.grid(row=row, column=1, sticky=tk.W, pady=5)
        
        self.color_var = tk.StringVar(value=self.zone.color if self.zone else "#4CAF50")
        self.color_preview = tk.Label(color_frame, text="    ", 
                                      bg=self.color_var.get(), width=3, relief=tk.RAISED)
        self.color_preview.pack(side=tk.LEFT)
        
        ttk.Button(color_frame, text="Renk Seç...", 
                  command=self._choose_color).pack(side=tk.LEFT, padx=(10, 0))
        row += 1
        
        # Açıklama
        ttk.Label(main_frame, text="Açıklama:").grid(row=row, column=0, sticky=(tk.W, tk.N), pady=5)
        self.description_text = tk.Text(main_frame, height=5, width=30)
        self.description_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        if self.zone:
            self.description_text.insert('1.0', self.zone.description)
        row += 1
        
        # Butonlar
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Kaydet", command=self._save, width=15).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="İptal", command=self.destroy, width=15).pack(
            side=tk.LEFT, padx=5)
    
    def _choose_color(self):
        """Renk seçici aç"""
        color = colorchooser.askcolor(self.color_var.get(), parent=self)
        if color[1]:  # Hex renk
            self.color_var.set(color[1])
            self.color_preview.config(bg=color[1])
    
    def _save(self):
        """Kaydet"""
        # Validasyon
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Uyarı", "Bölge adı boş olamaz!")
            return
        
        min_p = self.min_pressure_var.get()
        max_p = self.max_pressure_var.get()
        
        if min_p >= max_p:
            messagebox.showwarning("Uyarı", "Min basınç, max basınçtan küçük olmalı!")
            return
        
        # Zone oluştur
        if self.zone:
            # Mevcut zone'u güncelle
            self.zone.name = name
            self.zone.zone_type = ZoneType(self.type_var.get())
            self.zone.min_pressure = min_p
            self.zone.max_pressure = max_p
            self.zone.color = self.color_var.get()
            self.zone.description = self.description_text.get('1.0', tk.END).strip()
            self.result = self.zone
        else:
            # Yeni zone
            self.result = PressureZone(
                id="",  # Manager tarafından atanacak
                name=name,
                zone_type=ZoneType(self.type_var.get()),
                min_pressure=min_p,
                max_pressure=max_p,
                color=self.color_var.get(),
                description=self.description_text.get('1.0', tk.END).strip()
            )
        
        self.destroy()


class PressureZonePanel(ttk.Frame):
    """
    Basınç bölgeleri yönetim paneli
    """
    
    def __init__(self, parent, zone_manager: PressureZoneManager):
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)
        
        self.zone_manager = zone_manager
        self.on_zone_changed = None  # Callback
        
        self._create_widgets()
        self._refresh_list()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        # Header
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(header, text="🗺️ Basınç Bölgeleri", 
                 font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        
        # Butonlar
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="➕ Yeni", command=self._add_zone, width=10).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="✏️ Düzenle", command=self._edit_zone, width=10).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🗑️ Sil", command=self._delete_zone, width=10).pack(
            side=tk.LEFT, padx=2)
        
        # Liste
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.zone_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=10)
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.zone_listbox.yview)
        
        self.zone_listbox.bind('<Double-Button-1>', lambda e: self._edit_zone())
    
    def _refresh_list(self):
        """Listeyi yenile"""
        self.zone_listbox.delete(0, tk.END)
        
        for zone in self.zone_manager.zones.values():
            display = f"{zone.name} ({zone.min_pressure:.1f}-{zone.max_pressure:.1f} bar)"
            self.zone_listbox.insert(tk.END, display)
    
    def _add_zone(self):
        """Yeni bölge ekle"""
        dialog = PressureZoneDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            self.zone_manager.add_zone(dialog.result)
            self._refresh_list()
            
            if self.on_zone_changed:
                self.on_zone_changed()
    
    def _edit_zone(self):
        """Bölge düzenle"""
        selection = self.zone_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        zone_id = list(self.zone_manager.zones.keys())[idx]
        zone = self.zone_manager.get_zone(zone_id)
        
        dialog = PressureZoneDialog(self, zone)
        self.wait_window(dialog)
        
        if dialog.result:
            self._refresh_list()
            
            if self.on_zone_changed:
                self.on_zone_changed()
    
    def _delete_zone(self):
        """Bölge sil"""
        selection = self.zone_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        zone_id = list(self.zone_manager.zones.keys())[idx]
        zone = self.zone_manager.get_zone(zone_id)
        
        if messagebox.askyesno("Onay", f"'{zone.name}' bölgesini silmek istediğinize emin misiniz?"):
            self.zone_manager.remove_zone(zone_id)
            self._refresh_list()
            
            if self.on_zone_changed:
                self.on_zone_changed()
