"""
Network Templates

Hazır network şablonları:
- Grid pattern
- Tree pattern
- Loop pattern
- Parametrik şablon oluşturma
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Tuple, Dict
from dataclasses import dataclass
import json
import math

from models import Node, Pipe, NodeType, Coordinates


class TemplatePattern:
    """Şablon pattern enum"""
    GRID = "grid"
    TREE = "tree"
    LOOP = "loop"
    CUSTOM = "custom"


@dataclass
class TemplateConfig:
    """Şablon konfigürasyonu"""
    pattern: str
    rows: int = 3
    cols: int = 4
    spacing_x: float = 400.0  # cm
    spacing_y: float = 400.0  # cm
    pipe_diameter: int = 50  # mm
    sprinkler_k_factor: int = 80
    include_source: bool = True
    center_x: float = 0.0
    center_y: float = 0.0


class NetworkTemplateGenerator:
    """Network şablon oluşturucu"""
    
    @staticmethod
    def generate_grid(config: TemplateConfig) -> Tuple[List[Node], List[Pipe]]:
        """
        Grid pattern şablon
        
        Düzenli grid üzerinde sprinklerlar
        """
        nodes = []
        pipes = []
        
        node_id = 1
        pipe_id = 1
        
        # Grid node'ları oluştur
        node_grid = {}  # (row, col) -> node_id
        
        for row in range(config.rows):
            for col in range(config.cols):
                x = config.center_x + (col - config.cols/2) * config.spacing_x
                y = config.center_y + (row - config.rows/2) * config.spacing_y
                
                # Sprinkler node
                node = Node(
                    id=f"N{node_id}",
                    node_type=NodeType.SPRINKLER,
                    coordinates=Coordinates(x, y)
                )
                
                # Özellikler
                node.k_factor = config.sprinkler_k_factor
                node.flow_rate = 80.0  # L/min varsayılan
                
                nodes.append(node)
                node_grid[(row, col)] = node.id
                node_id += 1
        
        # Yatay borular
        for row in range(config.rows):
            for col in range(config.cols - 1):
                node1_id = node_grid[(row, col)]
                node2_id = node_grid[(row, col + 1)]
                
                length = config.spacing_x / 10  # cm -> m
                
                pipe = Pipe(
                    id=f"P{pipe_id}",
                    node1_id=node1_id,
                    node2_id=node2_id,
                    diameter=config.pipe_diameter,
                    length=length
                )
                pipes.append(pipe)
                pipe_id += 1
        
        # Dikey borular
        for row in range(config.rows - 1):
            for col in range(config.cols):
                node1_id = node_grid[(row, col)]
                node2_id = node_grid[(row + 1, col)]
                
                length = config.spacing_y / 10  # cm -> m
                
                pipe = Pipe(
                    id=f"P{pipe_id}",
                    node1_id=node1_id,
                    node2_id=node2_id,
                    diameter=config.pipe_diameter,
                    length=length
                )
                pipes.append(pipe)
                pipe_id += 1
        
        # Kaynak node ekle
        if config.include_source:
            source_x = config.center_x - (config.cols/2 + 1) * config.spacing_x
            source_y = config.center_y
            
            source = Node(
                id=f"SOURCE",
                node_type=NodeType.SOURCE,
                coordinates=Coordinates(source_x, source_y)
            )
            source.pressure = 5.0  # bar
            nodes.append(source)
            
            # Kaynağı en soldaki node'a bağla
            first_node_id = node_grid[(config.rows // 2, 0)]
            
            pipe = Pipe(
                id=f"P{pipe_id}",
                node1_id="SOURCE",
                node2_id=first_node_id,
                diameter=config.pipe_diameter + 15,  # Ana hat daha büyük
                length=config.spacing_x / 10
            )
            pipes.append(pipe)
        
        return nodes, pipes
    
    @staticmethod
    def generate_tree(config: TemplateConfig) -> Tuple[List[Node], List[Pipe]]:
        """
        Tree pattern şablon
        
        Merkezi ana hat, dallara ayrılan sprinklerlar
        """
        nodes = []
        pipes = []
        
        node_id = 1
        pipe_id = 1
        
        # Ana hat node'ları (dikey)
        main_nodes = []
        main_node_ids = []
        
        for i in range(config.rows):
            y = config.center_y + (i - config.rows/2) * config.spacing_y
            
            main_node = Node(
                id=f"M{node_id}",
                node_type=NodeType.JUNCTION,
                coordinates=Coordinates(config.center_x, y)
            )
            nodes.append(main_node)
            main_nodes.append(main_node)
            main_node_ids.append(main_node.id)
            node_id += 1
        
        # Ana hat boruları
        for i in range(len(main_nodes) - 1):
            pipe = Pipe(
                id=f"P{pipe_id}",
                node1_id=main_node_ids[i],
                node2_id=main_node_ids[i + 1],
                diameter=config.pipe_diameter + 15,
                length=config.spacing_y / 10
            )
            pipes.append(pipe)
            pipe_id += 1
        
        # Her ana node'dan dallar
        for i, main_node in enumerate(main_nodes):
            # Sol dal
            for j in range(config.cols // 2):
                x = config.center_x - (j + 1) * config.spacing_x
                
                sprinkler = Node(
                    id=f"N{node_id}",
                    node_type=NodeType.SPRINKLER,
                    coordinates=Coordinates(x, main_node.coordinates.y)
                )
                sprinkler.k_factor = config.sprinkler_k_factor
                sprinkler.flow_rate = 80.0
                nodes.append(sprinkler)
                
                # Bağlantı
                prev_id = main_node.id if j == 0 else f"N{node_id - 1}"
                
                pipe = Pipe(
                    id=f"P{pipe_id}",
                    node1_id=prev_id,
                    node2_id=sprinkler.id,
                    diameter=config.pipe_diameter,
                    length=config.spacing_x / 10
                )
                pipes.append(pipe)
                pipe_id += 1
                node_id += 1
            
            # Sağ dal
            for j in range(config.cols // 2):
                x = config.center_x + (j + 1) * config.spacing_x
                
                sprinkler = Node(
                    id=f"N{node_id}",
                    node_type=NodeType.SPRINKLER,
                    coordinates=Coordinates(x, main_node.coordinates.y)
                )
                sprinkler.k_factor = config.sprinkler_k_factor
                sprinkler.flow_rate = 80.0
                nodes.append(sprinkler)
                
                # Bağlantı
                prev_id = main_node.id if j == 0 else f"N{node_id - 1}"
                
                pipe = Pipe(
                    id=f"P{pipe_id}",
                    node1_id=prev_id,
                    node2_id=sprinkler.id,
                    diameter=config.pipe_diameter,
                    length=config.spacing_x / 10
                )
                pipes.append(pipe)
                pipe_id += 1
                node_id += 1
        
        # Kaynak
        if config.include_source:
            source = Node(
                id="SOURCE",
                node_type=NodeType.SOURCE,
                coordinates=Coordinates(config.center_x, 
                                      config.center_y - (config.rows/2 + 1) * config.spacing_y)
            )
            source.pressure = 5.0
            nodes.append(source)
            
            pipe = Pipe(
                id=f"P{pipe_id}",
                node1_id="SOURCE",
                node2_id=main_node_ids[0],
                diameter=config.pipe_diameter + 20,
                length=config.spacing_y / 10
            )
            pipes.append(pipe)
        
        return nodes, pipes
    
    @staticmethod
    def generate_loop(config: TemplateConfig) -> Tuple[List[Node], List[Pipe]]:
        """
        Loop pattern şablon
        
        Kapalı döngüler ile redundant sistem
        """
        nodes = []
        pipes = []
        
        node_id = 1
        pipe_id = 1
        
        # Çift grid oluştur (loop için)
        node_grid = {}
        
        for row in range(config.rows):
            for col in range(config.cols):
                x = config.center_x + (col - config.cols/2) * config.spacing_x
                y = config.center_y + (row - config.rows/2) * config.spacing_y
                
                node_type = NodeType.SPRINKLER if (row + col) % 2 == 0 else NodeType.JUNCTION
                
                node = Node(
                    id=f"N{node_id}",
                    node_type=node_type,
                    coordinates=Coordinates(x, y)
                )
                
                if node_type == NodeType.SPRINKLER:
                    node.k_factor = config.sprinkler_k_factor
                    node.flow_rate = 80.0
                
                nodes.append(node)
                node_grid[(row, col)] = node.id
                node_id += 1
        
        # Yatay ve dikey borular (tam grid)
        for row in range(config.rows):
            for col in range(config.cols - 1):
                pipe = Pipe(
                    id=f"P{pipe_id}",
                    node1_id=node_grid[(row, col)],
                    node2_id=node_grid[(row, col + 1)],
                    diameter=config.pipe_diameter,
                    length=config.spacing_x / 10
                )
                pipes.append(pipe)
                pipe_id += 1
        
        for row in range(config.rows - 1):
            for col in range(config.cols):
                pipe = Pipe(
                    id=f"P{pipe_id}",
                    node1_id=node_grid[(row, col)],
                    node2_id=node_grid[(row + 1, col)],
                    diameter=config.pipe_diameter,
                    length=config.spacing_y / 10
                )
                pipes.append(pipe)
                pipe_id += 1
        
        # Kaynak
        if config.include_source:
            source = Node(
                id="SOURCE",
                node_type=NodeType.SOURCE,
                coordinates=Coordinates(
                    config.center_x - (config.cols/2 + 1) * config.spacing_x,
                    config.center_y
                )
            )
            source.pressure = 5.0
            nodes.append(source)
            
            # Kaynağı iki noktaya bağla (redundancy)
            first_node_id = node_grid[(config.rows // 2, 0)]
            
            pipe = Pipe(
                id=f"P{pipe_id}",
                node1_id="SOURCE",
                node2_id=first_node_id,
                diameter=config.pipe_diameter + 20,
                length=config.spacing_x / 10
            )
            pipes.append(pipe)
        
        return nodes, pipes


class NetworkTemplateDialog(tk.Toplevel):
    """Network şablon seçim dialogu"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.result = None
        
        self.title("Network Şablonları")
        self.geometry("600x700")
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        ttk.Label(main_frame, text="📐 Network Şablon Oluşturucu",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Pattern seçimi
        pattern_frame = ttk.LabelFrame(main_frame, text="Şablon Tipi", padding=10)
        pattern_frame.pack(fill=tk.X, pady=10)
        
        self.pattern_var = tk.StringVar(value=TemplatePattern.GRID)
        
        patterns = [
            (TemplatePattern.GRID, "🔲 Grid Pattern", "Düzenli grid üzerinde sprinklerlar"),
            (TemplatePattern.TREE, "🌳 Tree Pattern", "Merkezi ana hat, dallanan sprinklerlar"),
            (TemplatePattern.LOOP, "🔄 Loop Pattern", "Kapalı döngüler, redundant sistem"),
        ]
        
        for value, label, desc in patterns:
            frame = ttk.Frame(pattern_frame)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Radiobutton(frame, text=label, variable=self.pattern_var, 
                          value=value).pack(side=tk.LEFT)
            ttk.Label(frame, text=f"  ({desc})", foreground='gray').pack(side=tk.LEFT)
        
        # Parametreler
        param_frame = ttk.LabelFrame(main_frame, text="Parametreler", padding=10)
        param_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        row = 0
        
        # Satır sayısı
        ttk.Label(param_frame, text="Satır Sayısı:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.rows_var = tk.IntVar(value=3)
        ttk.Spinbox(param_frame, from_=1, to=10, textvariable=self.rows_var, 
                   width=15).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Sütun sayısı
        ttk.Label(param_frame, text="Sütun Sayısı:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.cols_var = tk.IntVar(value=4)
        ttk.Spinbox(param_frame, from_=1, to=10, textvariable=self.cols_var,
                   width=15).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # X aralığı
        ttk.Label(param_frame, text="X Aralığı (cm):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.spacing_x_var = tk.DoubleVar(value=400.0)
        ttk.Entry(param_frame, textvariable=self.spacing_x_var, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Y aralığı
        ttk.Label(param_frame, text="Y Aralığı (cm):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.spacing_y_var = tk.DoubleVar(value=400.0)
        ttk.Entry(param_frame, textvariable=self.spacing_y_var, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Boru çapı
        ttk.Label(param_frame, text="Boru Çapı (mm):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.diameter_var = tk.IntVar(value=50)
        diameter_combo = ttk.Combobox(param_frame, textvariable=self.diameter_var, width=13)
        diameter_combo['values'] = [25, 32, 40, 50, 65, 80, 100]
        diameter_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # K-faktör
        ttk.Label(param_frame, text="Sprinkler K:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.k_factor_var = tk.IntVar(value=80)
        k_combo = ttk.Combobox(param_frame, textvariable=self.k_factor_var, width=13)
        k_combo['values'] = [57, 80, 115, 160]
        k_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Kaynak dahil et
        self.include_source_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(param_frame, text="Kaynak node ekle", 
                       variable=self.include_source_var).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=10)
        row += 1
        
        # Önizleme bilgisi
        info_frame = ttk.Frame(param_frame)
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.info_label = ttk.Label(info_frame, text="", foreground='blue')
        self.info_label.pack()
        
        # Değişiklikleri izle
        for var in [self.rows_var, self.cols_var, self.pattern_var]:
            var.trace_add('write', lambda *args: self._update_info())
        
        self._update_info()
        
        # Butonlar
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        ttk.Button(button_frame, text="✅ Oluştur", command=self._create_template,
                  width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="İptal", command=self.destroy,
                  width=15).pack(side=tk.RIGHT, padx=5)
    
    def _update_info(self):
        """Bilgi etiketini güncelle"""
        rows = self.rows_var.get()
        cols = self.cols_var.get()
        pattern = self.pattern_var.get()
        
        if pattern == TemplatePattern.GRID:
            node_count = rows * cols + 1  # +1 kaynak
            pipe_count = (rows * (cols - 1)) + ((rows - 1) * cols) + 1
        elif pattern == TemplatePattern.TREE:
            node_count = rows + (rows * cols) + 1
            pipe_count = (rows - 1) + (rows * cols) + 1
        else:  # LOOP
            node_count = rows * cols + 1
            pipe_count = (rows * (cols - 1)) + ((rows - 1) * cols) + 1
        
        self.info_label.config(
            text=f"📊 Tahmini: {node_count} node, {pipe_count} boru")
    
    def _create_template(self):
        """Şablonu oluştur"""
        config = TemplateConfig(
            pattern=self.pattern_var.get(),
            rows=self.rows_var.get(),
            cols=self.cols_var.get(),
            spacing_x=self.spacing_x_var.get(),
            spacing_y=self.spacing_y_var.get(),
            pipe_diameter=self.diameter_var.get(),
            sprinkler_k_factor=self.k_factor_var.get(),
            include_source=self.include_source_var.get()
        )
        
        try:
            generator = NetworkTemplateGenerator()
            
            if config.pattern == TemplatePattern.GRID:
                nodes, pipes = generator.generate_grid(config)
            elif config.pattern == TemplatePattern.TREE:
                nodes, pipes = generator.generate_tree(config)
            elif config.pattern == TemplatePattern.LOOP:
                nodes, pipes = generator.generate_loop(config)
            else:
                messagebox.showerror("Hata", "Bilinmeyen şablon tipi!")
                return
            
            self.result = (nodes, pipes)
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Şablon oluşturma hatası:\n{e}")
