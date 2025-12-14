"""
FireHydra - Veritabanı Modülü
=============================

Bu modül, hidrolik hesaplamalarda kullanılan referans verilerini
yönetir. SQLite veritabanı kullanarak boru çapları, fitting
eşdeğer uzunlukları ve C faktörlerini saklar.

Referans: NFPA 13 Tablo 28.2.3.1.1
"""

import sqlite3
import os
import json
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class PipeType:
    """Boru tipi veri yapısı"""
    id: int
    name: str
    nominal_diameter: float  # nominal_mm -> nominal_diameter
    internal_diameter: float  # actual_id_mm -> internal_diameter
    c_factor: float  # Hazen-Williams C değeri
    material: str
    wall_thickness: float = 0.0  # Et kalınlığı


@dataclass
class FittingType:
    """Fitting (ek parça) tipi veri yapısı"""
    id: int
    fitting_type: str  # Elbow_90, Elbow_45, Tee, Gate_Valve, etc.
    pipe_size_inch: float
    pipe_size_mm: float
    equivalent_length: float  # Eşdeğer uzunluk (metre)
    description: str = ""


@dataclass 
class HazardClass:
    """Tehlike sınıfı veri yapısı (BYKHY / NFPA)"""
    id: int
    code: str  # LH, OH1, OH2, HHP, etc.
    name_tr: str
    name_en: str
    density_mm_min: float  # mm/dk minimum
    coverage_area_max: float  # m² maksimum
    duration_min: int  # Dakika (su deposu süresi)
    hose_stream_lpm: float  # Hidrant debisi L/dk


class DatabaseManager:
    """
    Veritabanı yönetim sınıfı
    
    Tüm referans tablolarını oluşturur ve yönetir:
    - pipe_types: Boru çapları ve C faktörleri
    - fitting_types: Fitting eşdeğer uzunlukları
    - hazard_classes: Tehlike sınıfları ve parametreleri
    - sprinkler_types: Sprinkler K-faktörleri
    """
    
    def __init__(self, db_path: str = "firehydra.db"):
        """
        Veritabanı bağlantısını başlatır
        
        Args:
            db_path: Veritabanı dosya yolu
        """
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()
        self._populate_default_data()
    
    def _connect(self):
        """SQLite veritabanına bağlan"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
    def _create_tables(self):
        """Veritabanı tablolarını oluştur"""
        cursor = self.conn.cursor()
        
        # Boru Tipleri Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pipe_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                nominal_mm REAL NOT NULL,
                actual_id_mm REAL NOT NULL,
                c_factor REAL NOT NULL DEFAULT 120,
                material TEXT NOT NULL DEFAULT 'Steel'
            )
        ''')
        
        # Fitting Eşdeğer Uzunlukları Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fitting_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fitting_type TEXT NOT NULL,
                pipe_size_inch REAL NOT NULL,
                pipe_size_mm REAL NOT NULL,
                equivalent_length_m REAL NOT NULL
            )
        ''')
        
        # Tehlike Sınıfları Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hazard_classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name_tr TEXT NOT NULL,
                name_en TEXT NOT NULL,
                density_mm_min REAL NOT NULL,
                coverage_area_max REAL NOT NULL,
                duration_min INTEGER NOT NULL,
                hose_stream_lpm REAL NOT NULL DEFAULT 0
            )
        ''')
        
        # Sprinkler Tipleri Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sprinkler_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                k_factor_metric REAL NOT NULL,
                k_factor_imperial REAL,
                response_type TEXT DEFAULT 'Standard',
                min_pressure_bar REAL DEFAULT 0.5,
                max_coverage_m2 REAL DEFAULT 12
            )
        ''')
        
        # Pompa Tipleri Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pump_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT,
                model TEXT NOT NULL,
                nominal_flow_lpm REAL NOT NULL,
                nominal_pressure_bar REAL NOT NULL,
                churn_pressure_bar REAL,
                overload_flow_lpm REAL,
                overload_pressure_bar REAL,
                power_kw REAL
            )
        ''')
        
        self.conn.commit()
    
    def _populate_default_data(self):
        """Varsayılan referans verilerini yükle"""
        cursor = self.conn.cursor()
        
        # Tabloların boş olup olmadığını kontrol et
        cursor.execute("SELECT COUNT(*) FROM pipe_types")
        if cursor.fetchone()[0] == 0:
            self._insert_pipe_types()
            
        cursor.execute("SELECT COUNT(*) FROM fitting_types")
        if cursor.fetchone()[0] == 0:
            self._insert_fitting_types()
            
        cursor.execute("SELECT COUNT(*) FROM hazard_classes")
        if cursor.fetchone()[0] == 0:
            self._insert_hazard_classes()
            
        cursor.execute("SELECT COUNT(*) FROM sprinkler_types")
        if cursor.fetchone()[0] == 0:
            self._insert_sprinkler_types()
            
        self.conn.commit()
    
    def _insert_pipe_types(self):
        """Boru tiplerini ekle (NFPA 13 / Schedule 40)"""
        cursor = self.conn.cursor()
        
        # Steel Schedule 40 Borular
        pipe_data = [
            # (name, nominal_mm, actual_id_mm, c_factor, material)
            ("Steel Schedule 40 - 3/4 inch", 20, 20.9, 120, "Steel"),
            ("Steel Schedule 40 - 1 inch", 25, 26.6, 120, "Steel"),
            ("Steel Schedule 40 - 1-1/4 inch", 32, 35.1, 120, "Steel"),
            ("Steel Schedule 40 - 1-1/2 inch", 40, 40.9, 120, "Steel"),
            ("Steel Schedule 40 - 2 inch", 50, 52.5, 120, "Steel"),
            ("Steel Schedule 40 - 2-1/2 inch", 65, 62.7, 120, "Steel"),
            ("Steel Schedule 40 - 3 inch", 80, 77.9, 120, "Steel"),
            ("Steel Schedule 40 - 4 inch", 100, 102.3, 120, "Steel"),
            ("Steel Schedule 40 - 5 inch", 125, 128.2, 120, "Steel"),
            ("Steel Schedule 40 - 6 inch", 150, 154.1, 120, "Steel"),
            ("Steel Schedule 40 - 8 inch", 200, 202.7, 120, "Steel"),
            
            # CPVC Borular
            ("CPVC - 3/4 inch", 20, 22.5, 150, "CPVC"),
            ("CPVC - 1 inch", 25, 28.1, 150, "CPVC"),
            ("CPVC - 1-1/4 inch", 32, 35.8, 150, "CPVC"),
            ("CPVC - 1-1/2 inch", 40, 41.4, 150, "CPVC"),
            ("CPVC - 2 inch", 50, 54.0, 150, "CPVC"),
            
            # Galvanizli Çelik (Eski/Korozyonlu)
            ("Galvanized Steel - 1 inch", 25, 26.6, 100, "Galvanized"),
            ("Galvanized Steel - 2 inch", 50, 52.5, 100, "Galvanized"),
            ("Galvanized Steel - 3 inch", 80, 77.9, 100, "Galvanized"),
            ("Galvanized Steel - 4 inch", 100, 102.3, 100, "Galvanized"),
        ]
        
        cursor.executemany('''
            INSERT INTO pipe_types (name, nominal_mm, actual_id_mm, c_factor, material)
            VALUES (?, ?, ?, ?, ?)
        ''', pipe_data)
        
    def _insert_fitting_types(self):
        """Fitting eşdeğer uzunluklarını ekle (NFPA 13 Tablo 28.2.3.1.1)"""
        cursor = self.conn.cursor()
        
        # Fitting verileri: (type, inch, mm, eq_length_m)
        fitting_data = [
            # 90° Dirsek (Elbow)
            ("Elbow_90", 0.75, 20, 0.6),
            ("Elbow_90", 1.0, 25, 0.8),
            ("Elbow_90", 1.25, 32, 1.0),
            ("Elbow_90", 1.5, 40, 1.2),
            ("Elbow_90", 2.0, 50, 1.5),
            ("Elbow_90", 2.5, 65, 1.8),
            ("Elbow_90", 3.0, 80, 2.1),
            ("Elbow_90", 4.0, 100, 3.0),
            ("Elbow_90", 5.0, 125, 3.7),
            ("Elbow_90", 6.0, 150, 4.3),
            
            # 45° Dirsek
            ("Elbow_45", 0.75, 20, 0.3),
            ("Elbow_45", 1.0, 25, 0.4),
            ("Elbow_45", 1.25, 32, 0.5),
            ("Elbow_45", 1.5, 40, 0.6),
            ("Elbow_45", 2.0, 50, 0.8),
            ("Elbow_45", 2.5, 65, 0.9),
            ("Elbow_45", 3.0, 80, 1.1),
            ("Elbow_45", 4.0, 100, 1.5),
            ("Elbow_45", 5.0, 125, 1.8),
            ("Elbow_45", 6.0, 150, 2.1),
            
            # T-Parça (Tee) - Akış yön değiştiriyor
            ("Tee_Flow_Turned", 0.75, 20, 1.2),
            ("Tee_Flow_Turned", 1.0, 25, 1.5),
            ("Tee_Flow_Turned", 1.25, 32, 1.8),
            ("Tee_Flow_Turned", 1.5, 40, 2.1),
            ("Tee_Flow_Turned", 2.0, 50, 3.0),
            ("Tee_Flow_Turned", 2.5, 65, 3.7),
            ("Tee_Flow_Turned", 3.0, 80, 4.6),
            ("Tee_Flow_Turned", 4.0, 100, 6.1),
            ("Tee_Flow_Turned", 5.0, 125, 7.6),
            ("Tee_Flow_Turned", 6.0, 150, 9.1),
            
            # T-Parça (Tee) - Akış düz devam
            ("Tee_Flow_Straight", 0.75, 20, 0.0),
            ("Tee_Flow_Straight", 1.0, 25, 0.0),
            ("Tee_Flow_Straight", 1.25, 32, 0.0),
            ("Tee_Flow_Straight", 1.5, 40, 0.0),
            ("Tee_Flow_Straight", 2.0, 50, 0.0),
            ("Tee_Flow_Straight", 2.5, 65, 0.0),
            ("Tee_Flow_Straight", 3.0, 80, 0.0),
            ("Tee_Flow_Straight", 4.0, 100, 0.0),
            ("Tee_Flow_Straight", 5.0, 125, 0.0),
            ("Tee_Flow_Straight", 6.0, 150, 0.0),
            
            # Sürgülü Vana (Gate Valve) - Tam açık
            ("Gate_Valve", 0.75, 20, 0.1),
            ("Gate_Valve", 1.0, 25, 0.1),
            ("Gate_Valve", 1.25, 32, 0.2),
            ("Gate_Valve", 1.5, 40, 0.2),
            ("Gate_Valve", 2.0, 50, 0.2),
            ("Gate_Valve", 2.5, 65, 0.3),
            ("Gate_Valve", 3.0, 80, 0.3),
            ("Gate_Valve", 4.0, 100, 0.4),
            ("Gate_Valve", 5.0, 125, 0.5),
            ("Gate_Valve", 6.0, 150, 0.6),
            
            # Çekvalf (Check Valve) - Swing tipi
            ("Check_Valve_Swing", 0.75, 20, 1.5),
            ("Check_Valve_Swing", 1.0, 25, 1.8),
            ("Check_Valve_Swing", 1.25, 32, 2.4),
            ("Check_Valve_Swing", 1.5, 40, 3.0),
            ("Check_Valve_Swing", 2.0, 50, 3.7),
            ("Check_Valve_Swing", 2.5, 65, 4.6),
            ("Check_Valve_Swing", 3.0, 80, 5.5),
            ("Check_Valve_Swing", 4.0, 100, 7.3),
            ("Check_Valve_Swing", 5.0, 125, 9.1),
            ("Check_Valve_Swing", 6.0, 150, 10.7),
            
            # Kelebek Vana (Butterfly Valve)
            ("Butterfly_Valve", 2.0, 50, 1.8),
            ("Butterfly_Valve", 2.5, 65, 1.8),
            ("Butterfly_Valve", 3.0, 80, 1.5),
            ("Butterfly_Valve", 4.0, 100, 1.8),
            ("Butterfly_Valve", 5.0, 125, 2.4),
            ("Butterfly_Valve", 6.0, 150, 3.0),
            ("Butterfly_Valve", 8.0, 200, 3.7),
            
            # Alarm Vana (Alarm Check Valve)
            ("Alarm_Valve", 3.0, 80, 7.6),
            ("Alarm_Valve", 4.0, 100, 9.1),
            ("Alarm_Valve", 5.0, 125, 10.7),
            ("Alarm_Valve", 6.0, 150, 12.2),
            ("Alarm_Valve", 8.0, 200, 15.2),
        ]
        
        cursor.executemany('''
            INSERT INTO fitting_types (fitting_type, pipe_size_inch, pipe_size_mm, equivalent_length_m)
            VALUES (?, ?, ?, ?)
        ''', fitting_data)
        
    def _insert_hazard_classes(self):
        """Tehlike sınıflarını ekle (NFPA 13 / TS EN 12845 / BYKHY)"""
        cursor = self.conn.cursor()
        
        hazard_data = [
            # (code, name_tr, name_en, density_mm_min, coverage_max, duration, hose_lpm)
            ("LH", "Düşük Tehlike", "Light Hazard", 2.25, 21.0, 30, 250),
            ("OH1", "Orta Tehlike Grup 1", "Ordinary Hazard Group 1", 4.1, 12.0, 60, 500),
            ("OH2", "Orta Tehlike Grup 2", "Ordinary Hazard Group 2", 5.0, 12.0, 60, 500),
            ("HHP", "Yüksek Tehlike - Proses", "High Hazard Process", 7.5, 9.3, 90, 1000),
            ("HHS", "Yüksek Tehlike - Depolama", "High Hazard Storage", 12.5, 9.3, 120, 1000),
            
            # BYKHY özel sınıflar
            ("BYKHY_KONUT", "BYKHY Konut", "BYKHY Residential", 2.25, 12.0, 30, 0),
            ("BYKHY_OFIS", "BYKHY Ofis", "BYKHY Office", 4.1, 12.0, 60, 500),
            ("BYKHY_TICARI", "BYKHY Ticari", "BYKHY Commercial", 5.0, 12.0, 60, 500),
            ("BYKHY_ENDUSTRI", "BYKHY Endüstriyel", "BYKHY Industrial", 7.5, 9.3, 90, 1000),
        ]
        
        cursor.executemany('''
            INSERT INTO hazard_classes (code, name_tr, name_en, density_mm_min, coverage_area_max, duration_min, hose_stream_lpm)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', hazard_data)
        
    def _insert_sprinkler_types(self):
        """Sprinkler tiplerini ekle"""
        cursor = self.conn.cursor()
        
        sprinkler_data = [
            # (name, k_metric, k_imperial, response, min_p_bar, max_m2)
            ("Standard - K80", 80, 5.6, "Standard", 0.5, 12.0),
            ("Standard - K115", 115, 8.0, "Standard", 0.5, 12.0),
            ("Standard - K160", 160, 11.2, "Standard", 0.5, 12.0),
            ("Standard - K200", 200, 14.0, "Standard", 0.35, 12.0),
            ("Quick Response - K80", 80, 5.6, "Quick Response", 0.5, 12.0),
            ("Quick Response - K115", 115, 8.0, "Quick Response", 0.5, 12.0),
            ("Extended Coverage - K160", 160, 11.2, "Extended", 0.5, 37.0),
            ("Extended Coverage - K200", 200, 14.0, "Extended", 0.35, 37.0),
            ("ESFR - K240", 240, 16.8, "ESFR", 3.4, 9.3),
            ("ESFR - K320", 320, 22.4, "ESFR", 3.4, 9.3),
            ("ESFR - K360", 360, 25.2, "ESFR", 1.0, 9.3),
            ("Residential - K80", 80, 5.6, "Residential", 0.5, 18.0),
        ]
        
        cursor.executemany('''
            INSERT INTO sprinkler_types (name, k_factor_metric, k_factor_imperial, response_type, min_pressure_bar, max_coverage_m2)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sprinkler_data)
        
    # ==================== Query Methods ====================
    
    def get_pipe_type_by_id(self, pipe_id: int) -> Optional[PipeType]:
        """ID'ye göre boru tipi getir"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM pipe_types WHERE id = ?", (pipe_id,))
        row = cursor.fetchone()
        if row:
            return PipeType(**dict(row))
        return None
    
    def get_pipe_type_by_nominal(self, nominal_mm: float, material: str = "Steel") -> Optional[PipeType]:
        """Nominal çap ve malzemeye göre boru tipi getir"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM pipe_types 
            WHERE nominal_mm = ? AND material = ?
        ''', (nominal_mm, material))
        row = cursor.fetchone()
        if row:
            return PipeType(**dict(row))
        return None
    
    def get_all_pipe_types(self, material: Optional[str] = None) -> List[PipeType]:
        """Tüm boru tiplerini getir"""
        cursor = self.conn.cursor()
        if material:
            cursor.execute("SELECT * FROM pipe_types WHERE material = ?", (material,))
        else:
            cursor.execute("SELECT * FROM pipe_types")
        
        results = []
        for row in cursor.fetchall():
            # Veritabanı sütun isimlerini PipeType alan isimlerine eşle
            results.append(PipeType(
                id=row['id'],
                name=row['name'],
                nominal_diameter=row['nominal_mm'],
                internal_diameter=row['actual_id_mm'],
                c_factor=row['c_factor'],
                material=row['material'],
                wall_thickness=(row['nominal_mm'] - row['actual_id_mm']) / 2 if row['nominal_mm'] > row['actual_id_mm'] else 0
            ))
        return results
    
    def get_fitting_equivalent_length(self, fitting_type: str, pipe_size_mm: float) -> float:
        """Fitting eşdeğer uzunluğunu getir"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT equivalent_length_m FROM fitting_types 
            WHERE fitting_type = ? AND pipe_size_mm = ?
        ''', (fitting_type, pipe_size_mm))
        row = cursor.fetchone()
        if row:
            return row['equivalent_length_m']
        
        # Tam eşleşme bulunamazsa en yakın çapı bul
        cursor.execute('''
            SELECT equivalent_length_m, pipe_size_mm FROM fitting_types 
            WHERE fitting_type = ?
            ORDER BY ABS(pipe_size_mm - ?)
            LIMIT 1
        ''', (fitting_type, pipe_size_mm))
        row = cursor.fetchone()
        return row['equivalent_length_m'] if row else 0.0
    
    def get_all_fitting_types(self) -> List[str]:
        """Tüm fitting tiplerini getir (unique)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT fitting_type FROM fitting_types")
        return [row['fitting_type'] for row in cursor.fetchall()]
    
    def get_hazard_class(self, code: str) -> Optional[HazardClass]:
        """Tehlike sınıfı getir"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM hazard_classes WHERE code = ?", (code,))
        row = cursor.fetchone()
        if row:
            return HazardClass(**dict(row))
        return None
    
    def get_all_hazard_classes(self) -> List[HazardClass]:
        """Tüm tehlike sınıflarını getir"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM hazard_classes")
        return [HazardClass(**dict(row)) for row in cursor.fetchall()]
    
    def get_sprinkler_k_factor(self, name: str) -> Tuple[float, float]:
        """Sprinkler K faktörünü getir (metric, min_pressure)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT k_factor_metric, min_pressure_bar FROM sprinkler_types WHERE name = ?
        ''', (name,))
        row = cursor.fetchone()
        if row:
            return (row['k_factor_metric'], row['min_pressure_bar'])
        return (80.0, 0.5)  # Varsayılan K80
    
    def get_fittings_by_diameter(self, diameter_mm: float) -> List[FittingType]:
        """Belirli bir çap için tüm fitting tiplerini getir"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, fitting_type, pipe_size_inch, pipe_size_mm, equivalent_length_m, '' as description
            FROM fitting_types 
            WHERE pipe_size_mm = ?
            ORDER BY fitting_type
        ''', (diameter_mm,))
        
        results = []
        for row in cursor.fetchall():
            results.append(FittingType(
                id=row['id'],
                fitting_type=row['fitting_type'],
                pipe_size_inch=row['pipe_size_inch'],
                pipe_size_mm=row['pipe_size_mm'],
                equivalent_length=row['equivalent_length_m'],
                description=row['description']
            ))
        return results
    
    def close(self):
        """Veritabanı bağlantısını kapat"""
        if self.conn:
            self.conn.close()
            
    def __del__(self):
        self.close()


# ==================== Test / Demo ====================
if __name__ == "__main__":
    # Test veritabanı
    db = DatabaseManager("test_firehydra.db")
    
    print("=" * 50)
    print("FireHydra Veritabanı Testi")
    print("=" * 50)
    
    # Boru tipleri
    print("\n--- Boru Tipleri ---")
    pipes = db.get_all_pipe_types("Steel")
    for p in pipes[:5]:
        print(f"  {p.name}: ID={p.actual_id_mm}mm, C={p.c_factor}")
    
    # Fitting eşdeğer uzunlukları
    print("\n--- Fitting Eşdeğer Uzunlukları (2 inç) ---")
    for ft in ["Elbow_90", "Tee_Flow_Turned", "Gate_Valve"]:
        eq_len = db.get_fitting_equivalent_length(ft, 50)
        print(f"  {ft}: {eq_len} m")
    
    # Tehlike sınıfları
    print("\n--- Tehlike Sınıfları ---")
    hazards = db.get_all_hazard_classes()
    for h in hazards[:5]:
        print(f"  {h.code}: {h.name_tr}, Density={h.density_mm_min} mm/dk, Süre={h.duration_min} dk")
    
    db.close()
    print("\nTest tamamlandı!")
