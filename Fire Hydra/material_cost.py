"""
Material/Cost Database

Malzeme ve maliyet veritabanı yönetimi:
- Boru, fitting, sprinkler fiyat listesi
- Tedarikçi bilgileri
- Maliyet hesaplama
- Excel import/export
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3


class MaterialType(Enum):
    """Malzeme tipi"""
    PIPE = "pipe"
    FITTING = "fitting"
    SPRINKLER = "sprinkler"
    PUMP = "pump"
    VALVE = "valve"
    ACCESSORY = "accessory"


@dataclass
class MaterialItem:
    """
    Malzeme öğesi
    
    Attributes:
        id: Benzersiz ID
        name: Malzeme adı
        material_type: Malzeme tipi
        description: Açıklama
        unit: Birim (m, adet, takım)
        unit_price: Birim fiyat (TL)
        supplier: Tedarikçi
        catalog_code: Katalog kodu
        specifications: Özellikler (JSON)
    """
    id: int
    name: str
    material_type: MaterialType
    description: str = ""
    unit: str = "adet"
    unit_price: float = 0.0
    supplier: str = ""
    catalog_code: str = ""
    specifications: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.material_type, str):
            self.material_type = MaterialType(self.material_type)
    
    def to_dict(self) -> Dict:
        """Dictionary'ye çevir"""
        return {
            'id': self.id,
            'name': self.name,
            'material_type': self.material_type.value,
            'description': self.description,
            'unit': self.unit,
            'unit_price': self.unit_price,
            'supplier': self.supplier,
            'catalog_code': self.catalog_code,
            'specifications': self.specifications
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'MaterialItem':
        """Dictionary'den oluştur"""
        return MaterialItem(
            id=data.get('id', 0),
            name=data['name'],
            material_type=MaterialType(data.get('material_type', 'pipe')),
            description=data.get('description', ''),
            unit=data.get('unit', 'adet'),
            unit_price=data.get('unit_price', 0.0),
            supplier=data.get('supplier', ''),
            catalog_code=data.get('catalog_code', ''),
            specifications=data.get('specifications', {})
        )


@dataclass
class CostEstimate:
    """Maliyet tahmini"""
    items: List[Tuple[MaterialItem, float]] = field(default_factory=list)  # (item, quantity)
    labor_cost: float = 0.0
    overhead_percent: float = 15.0  # Genel giderler %
    profit_percent: float = 10.0  # Kâr marjı %
    
    @property
    def material_cost(self) -> float:
        """Toplam malzeme maliyeti"""
        return sum(item.unit_price * qty for item, qty in self.items)
    
    @property
    def subtotal(self) -> float:
        """Ara toplam"""
        return self.material_cost + self.labor_cost
    
    @property
    def overhead_cost(self) -> float:
        """Genel gider maliyeti"""
        return self.subtotal * (self.overhead_percent / 100)
    
    @property
    def profit(self) -> float:
        """Kâr"""
        return (self.subtotal + self.overhead_cost) * (self.profit_percent / 100)
    
    @property
    def total_cost(self) -> float:
        """Toplam maliyet"""
        return self.subtotal + self.overhead_cost + self.profit
    
    def add_item(self, item: MaterialItem, quantity: float):
        """Malzeme ekle"""
        self.items.append((item, quantity))
    
    def get_breakdown(self) -> Dict:
        """Maliyet dökümü"""
        return {
            'material_cost': self.material_cost,
            'labor_cost': self.labor_cost,
            'subtotal': self.subtotal,
            'overhead_cost': self.overhead_cost,
            'profit': self.profit,
            'total_cost': self.total_cost
        }


class MaterialDatabase:
    """
    Malzeme veritabanı yöneticisi
    """
    
    def __init__(self, db_path: str = "materials.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Veritabanını başlat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                material_type TEXT NOT NULL,
                description TEXT,
                unit TEXT DEFAULT 'adet',
                unit_price REAL DEFAULT 0.0,
                supplier TEXT,
                catalog_code TEXT,
                specifications TEXT
            )
        ''')
        
        # Örnek veriler ekle (ilk çalıştırmada)
        cursor.execute("SELECT COUNT(*) FROM materials")
        if cursor.fetchone()[0] == 0:
            self._insert_sample_data(cursor)
        
        conn.commit()
        conn.close()
    
    def _insert_sample_data(self, cursor):
        """Örnek verileri ekle"""
        samples = [
            # Borular
            ("Çelik Boru DN50", "pipe", "Dikişsiz çelik boru DN50", "m", 125.50, "ABC Metal", "STL-DN50", "{}"),
            ("Çelik Boru DN65", "pipe", "Dikişsiz çelik boru DN65", "m", 165.75, "ABC Metal", "STL-DN65", "{}"),
            ("Çelik Boru DN80", "pipe", "Dikişsiz çelik boru DN80", "m", 205.00, "ABC Metal", "STL-DN80", "{}"),
            ("Çelik Boru DN100", "pipe", "Dikişsiz çelik boru DN100", "m", 285.50, "ABC Metal", "STL-DN100", "{}"),
            
            # Fittingler
            ("Dirsek 90° DN50", "fitting", "Galvanizli dirsek 90°", "adet", 45.00, "XYZ Vana", "ELB90-50", "{}"),
            ("Dirsek 90° DN65", "fitting", "Galvanizli dirsek 90°", "adet", 65.00, "XYZ Vana", "ELB90-65", "{}"),
            ("T Parça DN50", "fitting", "T bağlantı parçası", "adet", 55.00, "XYZ Vana", "TEE-50", "{}"),
            ("Redüksiyon DN80x50", "fitting", "Redüksiyon", "adet", 38.00, "XYZ Vana", "RED-8050", "{}"),
            
            # Sprinklerlar
            ("Sprinkler K80 Upright", "sprinkler", "K=80 yukarı tip", "adet", 125.00, "FireTech", "SPR-K80-UP", '{"k_factor": 80, "type": "upright"}'),
            ("Sprinkler K115 Pendent", "sprinkler", "K=115 aşağı tip", "adet", 145.00, "FireTech", "SPR-K115-PD", '{"k_factor": 115, "type": "pendent"}'),
            ("Sprinkler K160 Sidewall", "sprinkler", "K=160 duvar tipi", "adet", 185.00, "FireTech", "SPR-K160-SW", '{"k_factor": 160, "type": "sidewall"}'),
            
            # Vanalar
            ("Kelebek Vana DN50", "valve", "Kelebek vana", "adet", 850.00, "XYZ Vana", "BFV-50", "{}"),
            ("Kelebek Vana DN80", "valve", "Kelebek vana", "adet", 1250.00, "XYZ Vana", "BFV-80", "{}"),
            ("Kontrol Vanası DN65", "valve", "Alarm kontrol vanası", "adet", 3500.00, "XYZ Vana", "ACV-65", "{}"),
            
            # Aksesuarlar
            ("Askı Kelepçesi DN50", "accessory", "Boru askı kelepçesi", "adet", 18.50, "Genel", "HGR-50", "{}"),
            ("Askı Kelepçesi DN80", "accessory", "Boru askı kelepçesi", "adet", 25.00, "Genel", "HGR-80", "{}"),
            ("Manometre 0-16 bar", "accessory", "Gliserinli manometre", "adet", 185.00, "Genel", "MAN-16", "{}"),
        ]
        
        cursor.executemany(
            "INSERT INTO materials (name, material_type, description, unit, unit_price, supplier, catalog_code, specifications) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            samples
        )
    
    def get_all_materials(self, material_type: Optional[MaterialType] = None) -> List[MaterialItem]:
        """Tüm malzemeleri getir"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if material_type:
            cursor.execute("SELECT * FROM materials WHERE material_type = ?", (material_type.value,))
        else:
            cursor.execute("SELECT * FROM materials")
        
        items = []
        for row in cursor.fetchall():
            specs = json.loads(row[8]) if row[8] else {}
            item = MaterialItem(
                id=row[0],
                name=row[1],
                material_type=MaterialType(row[2]),
                description=row[3] or "",
                unit=row[4] or "adet",
                unit_price=row[5] or 0.0,
                supplier=row[6] or "",
                catalog_code=row[7] or "",
                specifications=specs
            )
            items.append(item)
        
        conn.close()
        return items
    
    def add_material(self, item: MaterialItem) -> int:
        """Malzeme ekle"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        specs_json = json.dumps(item.specifications)
        
        cursor.execute('''
            INSERT INTO materials (name, material_type, description, unit, unit_price, supplier, catalog_code, specifications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item.name, item.material_type.value, item.description, item.unit, 
              item.unit_price, item.supplier, item.catalog_code, specs_json))
        
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return item_id
    
    def update_material(self, item: MaterialItem):
        """Malzeme güncelle"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        specs_json = json.dumps(item.specifications)
        
        cursor.execute('''
            UPDATE materials SET name=?, material_type=?, description=?, unit=?, 
                   unit_price=?, supplier=?, catalog_code=?, specifications=?
            WHERE id=?
        ''', (item.name, item.material_type.value, item.description, item.unit,
              item.unit_price, item.supplier, item.catalog_code, specs_json, item.id))
        
        conn.commit()
        conn.close()
    
    def delete_material(self, item_id: int):
        """Malzeme sil"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM materials WHERE id=?", (item_id,))
        conn.commit()
        conn.close()
    
    def search_materials(self, query: str) -> List[MaterialItem]:
        """Malzeme ara"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM materials 
            WHERE name LIKE ? OR description LIKE ? OR catalog_code LIKE ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
        
        items = []
        for row in cursor.fetchall():
            specs = json.loads(row[8]) if row[8] else {}
            item = MaterialItem(
                id=row[0],
                name=row[1],
                material_type=MaterialType(row[2]),
                description=row[3] or "",
                unit=row[4] or "adet",
                unit_price=row[5] or 0.0,
                supplier=row[6] or "",
                catalog_code=row[7] or "",
                specifications=specs
            )
            items.append(item)
        
        conn.close()
        return items


class MaterialEditDialog(tk.Toplevel):
    """Malzeme düzenleme dialogu"""
    
    def __init__(self, parent, item: Optional[MaterialItem] = None):
        super().__init__(parent)
        
        self.item = item
        self.result: Optional[MaterialItem] = None
        
        title = "Malzeme Düzenle" if item else "Yeni Malzeme"
        self.title(title)
        self.geometry("500x550")
        self.resizable(False, False)
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        row = 0
        
        # Malzeme adı
        ttk.Label(main_frame, text="Malzeme Adı:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=self.item.name if self.item else "")
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Malzeme tipi
        ttk.Label(main_frame, text="Malzeme Tipi:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(
            value=self.item.material_type.value if self.item else MaterialType.PIPE.value)
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=37)
        type_combo['values'] = [mt.value for mt in MaterialType]
        type_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Açıklama
        ttk.Label(main_frame, text="Açıklama:").grid(row=row, column=0, sticky=(tk.W, tk.N), pady=5)
        self.description_text = tk.Text(main_frame, height=3, width=40)
        self.description_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        if self.item:
            self.description_text.insert('1.0', self.item.description)
        row += 1
        
        # Birim
        ttk.Label(main_frame, text="Birim:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.unit_var = tk.StringVar(value=self.item.unit if self.item else "adet")
        unit_combo = ttk.Combobox(main_frame, textvariable=self.unit_var, width=37)
        unit_combo['values'] = ["adet", "m", "m²", "m³", "kg", "takım", "paket"]
        unit_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Birim fiyat
        ttk.Label(main_frame, text="Birim Fiyat (TL):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.price_var = tk.DoubleVar(value=self.item.unit_price if self.item else 0.0)
        ttk.Entry(main_frame, textvariable=self.price_var, width=40).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Tedarikçi
        ttk.Label(main_frame, text="Tedarikçi:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.supplier_var = tk.StringVar(value=self.item.supplier if self.item else "")
        ttk.Entry(main_frame, textvariable=self.supplier_var, width=40).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Katalog kodu
        ttk.Label(main_frame, text="Katalog Kodu:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.catalog_var = tk.StringVar(value=self.item.catalog_code if self.item else "")
        ttk.Entry(main_frame, textvariable=self.catalog_var, width=40).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Butonlar
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Kaydet", command=self._save, width=15).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="İptal", command=self.destroy, width=15).pack(
            side=tk.LEFT, padx=5)
    
    def _save(self):
        """Kaydet"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Uyarı", "Malzeme adı boş olamaz!")
            return
        
        if self.item:
            # Güncelle
            self.item.name = name
            self.item.material_type = MaterialType(self.type_var.get())
            self.item.description = self.description_text.get('1.0', tk.END).strip()
            self.item.unit = self.unit_var.get()
            self.item.unit_price = self.price_var.get()
            self.item.supplier = self.supplier_var.get().strip()
            self.item.catalog_code = self.catalog_var.get().strip()
            self.result = self.item
        else:
            # Yeni
            self.result = MaterialItem(
                id=0,  # DB tarafından atanacak
                name=name,
                material_type=MaterialType(self.type_var.get()),
                description=self.description_text.get('1.0', tk.END).strip(),
                unit=self.unit_var.get(),
                unit_price=self.price_var.get(),
                supplier=self.supplier_var.get().strip(),
                catalog_code=self.catalog_var.get().strip()
            )
        
        self.destroy()


class MaterialCostPanel(ttk.Frame):
    """
    Malzeme/Maliyet yönetim paneli
    """
    
    def __init__(self, parent, db: MaterialDatabase):
        super().__init__(parent)
        
        self.db = db
        self.materials: List[MaterialItem] = []
        
        self._create_widgets()
        self._refresh_list()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(toolbar, text="🛒 Malzeme Veritabanı", 
                 font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        
        # Butonlar
        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="➕ Yeni", command=self._add_material, width=10).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="✏️ Düzenle", command=self._edit_material, width=10).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ Sil", command=self._delete_material, width=10).pack(
            side=tk.LEFT, padx=2)
        
        # Arama
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="Ara:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', lambda e: self._search())
        
        # Filtre
        ttk.Label(search_frame, text="Tip:").pack(side=tk.LEFT, padx=(10, 5))
        self.filter_var = tk.StringVar(value="Tümü")
        filter_combo = ttk.Combobox(search_frame, textvariable=self.filter_var, width=15)
        filter_combo['values'] = ["Tümü"] + [mt.value for mt in MaterialType]
        filter_combo.pack(side=tk.LEFT)
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_list())
        
        # Tablo
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        
        # Treeview
        self.tree = ttk.Treeview(table_frame, 
                                 columns=('name', 'type', 'unit', 'price', 'supplier', 'code'),
                                 show='headings',
                                 yscrollcommand=vsb.set,
                                 xscrollcommand=hsb.set)
        
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        # Sütunlar
        self.tree.heading('name', text='Malzeme Adı')
        self.tree.heading('type', text='Tip')
        self.tree.heading('unit', text='Birim')
        self.tree.heading('price', text='Fiyat (TL)')
        self.tree.heading('supplier', text='Tedarikçi')
        self.tree.heading('code', text='Katalog Kodu')
        
        self.tree.column('name', width=200)
        self.tree.column('type', width=80)
        self.tree.column('unit', width=60)
        self.tree.column('price', width=80)
        self.tree.column('supplier', width=120)
        self.tree.column('code', width=100)
        
        # Grid
        self.tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))
        
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        
        # Double-click düzenleme
        self.tree.bind('<Double-Button-1>', lambda e: self._edit_material())
    
    def _refresh_list(self):
        """Listeyi yenile"""
        # Eski verileri temizle
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Filtre
        filter_type = self.filter_var.get()
        if filter_type == "Tümü":
            self.materials = self.db.get_all_materials()
        else:
            self.materials = self.db.get_all_materials(MaterialType(filter_type))
        
        # Ekle
        for item in self.materials:
            self.tree.insert('', tk.END, values=(
                item.name,
                item.material_type.value,
                item.unit,
                f"{item.unit_price:.2f}",
                item.supplier,
                item.catalog_code
            ))
    
    def _search(self):
        """Ara"""
        query = self.search_var.get().strip()
        
        if not query:
            self._refresh_list()
            return
        
        # Eski verileri temizle
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Ara
        self.materials = self.db.search_materials(query)
        
        # Ekle
        for item in self.materials:
            self.tree.insert('', tk.END, values=(
                item.name,
                item.material_type.value,
                item.unit,
                f"{item.unit_price:.2f}",
                item.supplier,
                item.catalog_code
            ))
    
    def _add_material(self):
        """Yeni malzeme ekle"""
        dialog = MaterialEditDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            self.db.add_material(dialog.result)
            self._refresh_list()
            messagebox.showinfo("Başarılı", "Malzeme eklendi.")
    
    def _edit_material(self):
        """Malzeme düzenle"""
        selection = self.tree.selection()
        if not selection:
            return
        
        idx = self.tree.index(selection[0])
        item = self.materials[idx]
        
        dialog = MaterialEditDialog(self, item)
        self.wait_window(dialog)
        
        if dialog.result:
            self.db.update_material(dialog.result)
            self._refresh_list()
            messagebox.showinfo("Başarılı", "Malzeme güncellendi.")
    
    def _delete_material(self):
        """Malzeme sil"""
        selection = self.tree.selection()
        if not selection:
            return
        
        idx = self.tree.index(selection[0])
        item = self.materials[idx]
        
        if messagebox.askyesno("Onay", f"'{item.name}' malzemesini silmek istediğinize emin misiniz?"):
            self.db.delete_material(item.id)
            self._refresh_list()
            messagebox.showinfo("Başarılı", "Malzeme silindi.")


def calculate_project_cost(network, material_db: MaterialDatabase) -> CostEstimate:
    """
    Proje maliyeti hesapla
    
    Args:
        network: PipeNetwork objesi
        material_db: MaterialDatabase objesi
        
    Returns:
        CostEstimate objesi
    """
    estimate = CostEstimate()
    
    # Boruları topla
    pipe_lengths = {}  # diameter -> total_length
    for pipe in network.pipes:
        diameter = pipe.diameter
        length = pipe.length
        
        if diameter not in pipe_lengths:
            pipe_lengths[diameter] = 0
        pipe_lengths[diameter] += length
    
    # Boru maliyetlerini ekle
    pipe_materials = material_db.get_all_materials(MaterialType.PIPE)
    for diameter, total_length in pipe_lengths.items():
        # DN'ye göre malzeme bul (basit eşleştirme)
        matching_pipe = None
        for pm in pipe_materials:
            if f"DN{diameter}" in pm.name or f"{diameter}" in pm.catalog_code:
                matching_pipe = pm
                break
        
        if matching_pipe:
            estimate.add_item(matching_pipe, total_length)
    
    # Sprinklerları say
    sprinkler_count = sum(1 for node in network.nodes.values() 
                         if node.node_type.value == "sprinkler")
    
    if sprinkler_count > 0:
        sprinkler_materials = material_db.get_all_materials(MaterialType.SPRINKLER)
        if sprinkler_materials:
            # İlk sprinkler tipini kullan
            estimate.add_item(sprinkler_materials[0], sprinkler_count)
    
    # İşçilik maliyeti (basit tahmin)
    estimate.labor_cost = estimate.material_cost * 0.4  # Malzemenin %40'ı
    
    return estimate
