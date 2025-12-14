"""
FireHydra - GUI Modülü (Tkinter Canvas)
=======================================

Bu modül, 2D çizim tabanlı kullanıcı arayüzünü sağlar:
- Grid tabanlı sonsuz Canvas (Zoom/Pan)
- Akıllı boru çizimi (Snap, Auto-Split)
- Node ve Pipe görselleştirme
- Z-Ekseni (Elevation) yönetimi
- Özellikler paneli ve araç çubuğu

Teknoloji: Tkinter + Canvas
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import math
from typing import Optional, Tuple, List, Dict, Callable
from dataclasses import dataclass
import json

from models import Node, Pipe, PipeNetwork, NodeType, Coordinates, Fitting, FittingCategory
from database import DatabaseManager
from commands import (
    CommandManager, AddNodeCommand, RemoveNodeCommand, 
    AddPipeCommand, RemovePipeCommand, MoveNodeCommand, CompoundCommand
)


@dataclass
class CanvasItem:
    """Canvas üzerindeki öğe"""
    item_id: int  # Tkinter canvas item ID
    object_id: str  # Model ID (Node veya Pipe)
    item_type: str  # 'node', 'pipe', 'label'


class DrawingTool:
    """Çizim aracı enum'u"""
    SELECT = "select"
    PAN = "pan"
    PIPE = "pipe"
    SPRINKLER = "sprinkler"
    SOURCE = "source"
    FITTING = "fitting"


class FireHydraCanvas(tk.Canvas):
    """
    Ana Çizim Canvas'ı
    
    Özellikler:
    - Zoom/Pan desteği
    - Grid çizimi
    - Snap-to-grid
    - Akıllı boru bağlantısı
    """
    
    # Görsel ayarlar
    GRID_SIZE = 50  # Piksel
    SNAP_TOLERANCE = 15  # Piksel
    
    NODE_RADIUS = 8
    SPRINKLER_RADIUS = 12
    SOURCE_RADIUS = 15
    
    # Renkler
    COLORS = {
        'background': '#2B2B2B',
        'grid_major': '#404040',
        'grid_minor': '#353535',
        'node_default': '#FFFFFF',
        'node_selected': '#FFD700',
        'sprinkler': '#00FF00',
        'source': '#FF4444',
        'junction': '#4444FF',
        'pipe_default': '#00AAFF',
        'pipe_selected': '#FFD700',
        'pipe_calculated': '#00FF00',
        'text': '#FFFFFF',
    }
    
    def __init__(self, parent, network: PipeNetwork, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.network = network
        self.configure(bg=self.COLORS['background'], highlightthickness=0)
        
        # Command Manager (Undo/Redo)
        self.command_manager = CommandManager(max_history=50)
        
        # Görünüm durumu
        self.offset_x = 0
        self.offset_y = 0
        self.scale = 1.0
        
        # Grid görünürlüğü
        self.show_grid = True
        
        # Çizim durumu
        self.current_tool = DrawingTool.SELECT
        self.drawing_pipe = False
        self.pipe_start_node: Optional[str] = None
        self.temp_line: Optional[int] = None
        
        # Seçim durumu
        self.selected_items: List[str] = []
        
        # Sürükleme durumu
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_node_id: Optional[str] = None
        self.drag_start_coords: Dict[str, Tuple[float, float]] = {}  # node_id -> (x, y)
        
        # Canvas öğeleri takibi
        self.canvas_items: Dict[str, List[CanvasItem]] = {}  # object_id -> [CanvasItem]
        
        # Olay bağlantıları
        self._bind_events()
        
        # İlk çizim
        self.after(100, self.redraw)
        
        # DXF arka plan verisi
        self.dxf_background = {
            'geometries': [],
            'color': '#808080',
            'opacity': 0.3,
        }
    
    def _bind_events(self):
        """Olay bağlantılarını kur"""
        # Mouse olayları
        self.bind("<Button-1>", self._on_left_click)
        self.bind("<B1-Motion>", self._on_left_drag)
        self.bind("<ButtonRelease-1>", self._on_left_release)
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Motion>", self._on_mouse_move)
        
        # Pan için orta tuş
        self.bind("<Button-2>", self._on_middle_click)
        self.bind("<B2-Motion>", self._on_middle_drag)
        
        # Zoom için fare tekerleği
        self.bind("<MouseWheel>", self._on_mousewheel)
        
        # Klavye
        self.bind("<Escape>", self._on_escape)
        self.bind("<Delete>", self._on_delete)
        self.bind("<Control-z>", self._on_undo)
        self.bind("<Control-y>", self._on_redo)
        self.bind("<Control-Shift-z>", self._on_redo)
        
        # Focus için
        self.bind("<Enter>", lambda e: self.focus_set())
    
    def set_tool(self, tool: str):
        """Aktif aracı değiştir"""
        self.current_tool = tool
        self.drawing_pipe = False
        self.pipe_start_node = None
        
        if self.temp_line:
            self.delete(self.temp_line)
            self.temp_line = None
        
        # İmleç değiştir
        cursors = {
            DrawingTool.SELECT: "arrow",
            DrawingTool.PAN: "fleur",
            DrawingTool.PIPE: "crosshair",
            DrawingTool.SPRINKLER: "cross",
            DrawingTool.SOURCE: "cross",
        }
        self.configure(cursor=cursors.get(tool, "arrow"))
    
    # ==================== Koordinat Dönüşümleri ====================
    
    def screen_to_world(self, x: int, y: int) -> Tuple[float, float]:
        """Ekran koordinatlarını dünya koordinatlarına çevir"""
        wx = (x - self.offset_x) / self.scale
        wy = (y - self.offset_y) / self.scale
        return (wx, wy)
    
    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """Dünya koordinatlarını ekran koordinatlarına çevir"""
        sx = int(x * self.scale + self.offset_x)
        sy = int(y * self.scale + self.offset_y)
        return (sx, sy)
    
    def snap_to_grid(self, x: float, y: float) -> Tuple[float, float]:
        """Grid'e yapıştır"""
        grid = self.GRID_SIZE / self.scale
        snapped_x = round(x / grid) * grid
        snapped_y = round(y / grid) * grid
        return (snapped_x, snapped_y)
    
    # ==================== Çizim Fonksiyonları ====================
    
    def redraw(self):
        """Tüm canvas'ı yeniden çiz"""
        self.delete("all")
        self.canvas_items.clear()
        
        self._draw_grid()
        self._draw_dxf_background()
        self._draw_pipes()
        self._draw_nodes()

    def set_dxf_background(self, geometries, color="#808080", opacity=0.3):
        """DXF arka plan verisini ayarla ve yeniden çiz"""
        self.dxf_background['geometries'] = geometries or []
        self.dxf_background['color'] = color
        self.dxf_background['opacity'] = max(0.1, min(1.0, opacity))
        self.redraw()

    def _draw_dxf_background(self):
        """DXF arka planı çiz"""
        geoms = self.dxf_background.get('geometries', [])
        if not geoms:
            return
        color = self.dxf_background.get('color', '#808080')
        opacity = self.dxf_background.get('opacity', 0.3)
        
        # Tkinter Canvas alpha desteği sınırlı; stipple ile yaklaşım
        stipple = None
        if opacity < 0.35:
            stipple = 'gray50'
        elif opacity < 0.7:
            stipple = 'gray25'
        
        for geom in geoms:
            etype = getattr(geom, 'entity_type', None)
            points = getattr(geom, 'points', [])
            center = getattr(geom, 'center', None)
            radius = getattr(geom, 'radius', None)
            start_angle = getattr(geom, 'start_angle', None)
            end_angle = getattr(geom, 'end_angle', None)
            
            if etype and hasattr(etype, 'value'):
                etype = etype.value
            
            if etype == 'LINE' and len(points) == 2:
                x1, y1 = points[0]
                x2, y2 = points[1]
                self.create_line(x1, y1, x2, y2, fill=color, width=1, stipple=stipple)
            elif etype in ('POLYLINE', 'LWPOLYLINE') and len(points) >= 2:
                flat = []
                for x, y in points:
                    flat.extend([x, y])
                self.create_line(*flat, fill=color, width=1, stipple=stipple)
            elif etype == 'CIRCLE' and center and radius:
                cx, cy = center
                x1 = cx - radius
                y1 = cy - radius
                x2 = cx + radius
                y2 = cy + radius
                self.create_oval(x1, y1, x2, y2, outline=color, width=1, stipple=stipple)
            elif etype == 'ARC' and center and radius is not None and start_angle is not None and end_angle is not None:
                # Tkinter arc angles: start is degrees from 3 o'clock, extent is sweep
                cx, cy = center
                x1 = cx - radius
                y1 = cy - radius
                x2 = cx + radius
                y2 = cy + radius
                extent = (end_angle - start_angle) % 360
                self.create_arc(x1, y1, x2, y2, start=start_angle, extent=extent, style=tk.ARC, outline=color, width=1)
        self._draw_labels()
    
    def _draw_grid(self):
        """Grid çiz"""
        if not self.show_grid:
            return
            
        width = self.winfo_width()
        height = self.winfo_height()
        
        # Grid aralığı (ekran koordinatlarında)
        grid_screen = self.GRID_SIZE * self.scale
        
        if grid_screen < 10:
            return  # Çok küçükse çizme
        
        # Başlangıç noktaları
        start_x = self.offset_x % grid_screen
        start_y = self.offset_y % grid_screen
        
        # Dikey çizgiler
        x = start_x
        while x < width:
            self.create_line(x, 0, x, height, fill=self.COLORS['grid_minor'], tags="grid")
            x += grid_screen
        
        # Yatay çizgiler
        y = start_y
        while y < height:
            self.create_line(0, y, width, y, fill=self.COLORS['grid_minor'], tags="grid")
            y += grid_screen
        
        # Orijin çizgileri
        ox, oy = self.world_to_screen(0, 0)
        self.create_line(ox, 0, ox, height, fill=self.COLORS['grid_major'], width=2, tags="grid")
        self.create_line(0, oy, width, oy, fill=self.COLORS['grid_major'], width=2, tags="grid")
    
    def _draw_nodes(self):
        """Düğümleri çiz"""
        for node in self.network.nodes.values():
            self._draw_node(node)
    
    def _draw_node(self, node: Node):
        """Tek bir düğüm çiz"""
        sx, sy = self.world_to_screen(node.coordinates.x, node.coordinates.y)
        
        # Düğüm tipine göre ayarlar
        if node.node_type == NodeType.SPRINKLER:
            radius = self.SPRINKLER_RADIUS
            color = self.COLORS['sprinkler']
            # Sprinkler sembolü (daire + çizgiler)
            item = self.create_oval(
                sx - radius, sy - radius,
                sx + radius, sy + radius,
                outline=color, width=2, fill=self.COLORS['background'],
                tags=("node", node.id)
            )
            # Çapraz çizgiler
            self.create_line(sx - radius, sy, sx + radius, sy, fill=color, tags=("node", node.id))
            self.create_line(sx, sy - radius, sx, sy + radius, fill=color, tags=("node", node.id))
            
        elif node.node_type == NodeType.SOURCE:
            radius = self.SOURCE_RADIUS
            color = self.COLORS['source']
            # Kaynak sembolü (çift daire)
            item = self.create_oval(
                sx - radius, sy - radius,
                sx + radius, sy + radius,
                outline=color, width=3, fill=self.COLORS['background'],
                tags=("node", node.id)
            )
            self.create_oval(
                sx - radius//2, sy - radius//2,
                sx + radius//2, sy + radius//2,
                fill=color, outline=color,
                tags=("node", node.id)
            )
            
        elif node.node_type == NodeType.JUNCTION:
            radius = self.NODE_RADIUS
            color = self.COLORS['junction']
            # Junction sembolü (dolu daire)
            item = self.create_oval(
                sx - radius, sy - radius,
                sx + radius, sy + radius,
                fill=color, outline=color,
                tags=("node", node.id)
            )
        else:
            # Varsayılan düğüm
            radius = self.NODE_RADIUS
            color = self.COLORS['node_default']
            item = self.create_oval(
                sx - radius, sy - radius,
                sx + radius, sy + radius,
                fill=color, outline=color,
                tags=("node", node.id)
            )
        
        # Seçili ise vurgula
        if node.id in self.selected_items:
            highlight = self.create_oval(
                sx - radius - 4, sy - radius - 4,
                sx + radius + 4, sy + radius + 4,
                outline=self.COLORS['node_selected'], width=2,
                tags=("selection", node.id)
            )
        
        # Canvas item takibi
        if node.id not in self.canvas_items:
            self.canvas_items[node.id] = []
        self.canvas_items[node.id].append(CanvasItem(item, node.id, 'node'))
    
    def _draw_pipes(self):
        """Boruları çiz"""
        for pipe in self.network.pipes.values():
            self._draw_pipe(pipe)
    
    def _draw_pipe(self, pipe: Pipe):
        """Tek bir boru çiz"""
        start_node = self.network.get_node(pipe.start_node_id)
        end_node = self.network.get_node(pipe.end_node_id)
        
        if not start_node or not end_node:
            return
        
        sx1, sy1 = self.world_to_screen(start_node.coordinates.x, start_node.coordinates.y)
        sx2, sy2 = self.world_to_screen(end_node.coordinates.x, end_node.coordinates.y)
        
        # Renk seçimi
        if pipe.id in self.selected_items:
            color = self.COLORS['pipe_selected']
            width = 4
        elif pipe.flow is not None:
            color = self.COLORS['pipe_calculated']
            width = 3
        else:
            color = self.COLORS['pipe_default']
            width = 2
        
        # Boru çizgisi
        item = self.create_line(
            sx1, sy1, sx2, sy2,
            fill=color, width=width,
            tags=("pipe", pipe.id)
        )
        
        # Canvas item takibi
        if pipe.id not in self.canvas_items:
            self.canvas_items[pipe.id] = []
        self.canvas_items[pipe.id].append(CanvasItem(item, pipe.id, 'pipe'))
    
    def _draw_labels(self):
        """Etiketleri çiz"""
        for node in self.network.nodes.values():
            if node.is_calculated and node.pressure is not None:
                sx, sy = self.world_to_screen(node.coordinates.x, node.coordinates.y)
                
                # Basınç ve debi etiketi
                label_text = f"P:{node.pressure:.2f}\nQ:{node.total_flow:.0f}" if node.total_flow else f"P:{node.pressure:.2f}"
                
                self.create_text(
                    sx, sy - 25,
                    text=label_text,
                    fill=self.COLORS['text'],
                    font=("Arial", 8),
                    tags=("label", node.id)
                )
    
    # ==================== Olay İşleyicileri ====================
    
    def _on_left_click(self, event):
        """Sol tıklama"""
        wx, wy = self.screen_to_world(event.x, event.y)
        
        if self.current_tool == DrawingTool.SELECT:
            self._handle_select(event.x, event.y)
            
            # Sürükleme başlat (seçili node varsa)
            if self.selected_items:
                # Node seçili mi kontrol et
                for item_id in self.selected_items:
                    if item_id in self.network.nodes:
                        self.dragging = True
                        self.drag_start_x = event.x
                        self.drag_start_y = event.y
                        # Tüm seçili node'ların başlangıç koordinatlarını sakla
                        self.drag_start_coords = {}
                        for node_id in self.selected_items:
                            if node_id in self.network.nodes:
                                node = self.network.get_node(node_id)
                                if node:
                                    self.drag_start_coords[node_id] = (node.coordinates.x, node.coordinates.y)
                        break
            
        elif self.current_tool == DrawingTool.PIPE:
            self._handle_pipe_click(wx, wy)
            
        elif self.current_tool == DrawingTool.SPRINKLER:
            self._add_sprinkler(wx, wy)
            
        elif self.current_tool == DrawingTool.SOURCE:
            self._add_source(wx, wy)
    
    def _on_left_drag(self, event):
        """Sol tıklama sürükleme"""
        if self.current_tool == DrawingTool.SELECT and self.dragging and self.drag_start_coords:
            # Mouse hareketi (ekran koordinatları)
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            # Dünya koordinatlarına çevir
            world_dx = dx / self.scale
            world_dy = dy / self.scale
            
            # Seçili node'ları taşı
            for node_id, (start_x, start_y) in self.drag_start_coords.items():
                node = self.network.get_node(node_id)
                if node:
                    node.coordinates.x = start_x + world_dx
                    node.coordinates.y = start_y + world_dy
                    
                    # Bağlı boruların uzunluklarını güncelle
                    for pipe in self.network.get_connected_pipes(node_id):
                        start = self.network.get_node(pipe.start_node_id)
                        end = self.network.get_node(pipe.end_node_id)
                        if start and end:
                            pipe.length = start.coordinates.distance_2d(end.coordinates) / 1000
            
            self.redraw()
    
    def _on_left_release(self, event):
        """Sol tıklama bırakma"""
        if self.dragging and self.drag_start_coords:
            # Mouse hareketi (ekran koordinatları)
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            # Hareket oldu mu kontrol et
            if abs(dx) > 3 or abs(dy) > 3:
                # Dünya koordinatlarına çevir
                world_dx = dx / self.scale
                world_dy = dy / self.scale
                
                # Compound command oluştur (çoklu node taşıma için)
                if len(self.drag_start_coords) > 1:
                    compound = CompoundCommand("Çoklu düğüm taşı")
                    for node_id, (start_x, start_y) in self.drag_start_coords.items():
                        cmd = MoveNodeCommand(
                            self.network, node_id,
                            start_x + world_dx,
                            start_y + world_dy
                        )
                        # Koordinatları zaten güncelledik, sadece undo için kaydet
                        cmd.old_x = start_x
                        cmd.old_y = start_y
                        node = self.network.get_node(node_id)
                        if node:
                            cmd.old_z = node.coordinates.z
                        compound.add_command(cmd)
                    # Stack'e ekle (execute çağırmadan)
                    self.command_manager.undo_stack.append(compound)
                    self.command_manager.redo_stack.clear()
                else:
                    # Tek node
                    for node_id, (start_x, start_y) in self.drag_start_coords.items():
                        cmd = MoveNodeCommand(
                            self.network, node_id,
                            start_x + world_dx,
                            start_y + world_dy
                        )
                        cmd.old_x = start_x
                        cmd.old_y = start_y
                        node = self.network.get_node(node_id)
                        if node:
                            cmd.old_z = node.coordinates.z
                        self.command_manager.undo_stack.append(cmd)
                        self.command_manager.redo_stack.clear()
        
        # Sürükleme durumunu sıfırla
        self.dragging = False
        self.drag_start_coords = {}
    
    def _on_right_click(self, event):
        """Sağ tıklama (bağlam menüsü)"""
        wx, wy = self.screen_to_world(event.x, event.y)
        
        # Tıklanan öğeyi bul
        item = self.find_closest(event.x, event.y)
        if item:
            tags = self.gettags(item)
            if "node" in tags:
                self._show_node_menu(event, tags[-1])
            elif "pipe" in tags:
                self._show_pipe_menu(event, tags[-1])
    
    def _on_mouse_move(self, event):
        """Mouse hareketi"""
        if self.drawing_pipe and self.pipe_start_node:
            # Geçici boru çizgisi güncelle
            start_node = self.network.get_node(self.pipe_start_node)
            if start_node:
                sx1, sy1 = self.world_to_screen(start_node.coordinates.x, start_node.coordinates.y)
                
                if self.temp_line:
                    self.delete(self.temp_line)
                
                self.temp_line = self.create_line(
                    sx1, sy1, event.x, event.y,
                    fill=self.COLORS['pipe_default'], width=2, dash=(5, 3)
                )
    
    def _on_middle_click(self, event):
        """Orta tıklama (pan başlat)"""
        self._pan_start_x = event.x
        self._pan_start_y = event.y
    
    def _on_middle_drag(self, event):
        """Orta tıklama sürükleme (pan)"""
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        
        self.offset_x += dx
        self.offset_y += dy
        
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        
        self.redraw()
    
    def _on_mousewheel(self, event):
        """Mouse tekerleği (zoom)"""
        # Zoom merkezi
        wx, wy = self.screen_to_world(event.x, event.y)
        
        # Zoom faktörü
        if event.delta > 0:
            factor = 1.1
        else:
            factor = 0.9
        
        # Yeni ölçek
        new_scale = self.scale * factor
        new_scale = max(0.1, min(5.0, new_scale))  # Limit
        
        # Offset ayarla (zoom merkezi sabit kalsın)
        self.offset_x = event.x - wx * new_scale
        self.offset_y = event.y - wy * new_scale
        
        self.scale = new_scale
        self.redraw()
    
    def _on_escape(self, event):
        """Escape tuşu"""
        self.drawing_pipe = False
        self.pipe_start_node = None
        self.selected_items.clear()
        self.dragging = False
        self.drag_start_coords = {}
        
        if self.temp_line:
            self.delete(self.temp_line)
            self.temp_line = None
        
        self.redraw()
    
    def _on_delete(self, event):
        """Delete tuşu"""
        if not self.selected_items:
            return
        
        # Çoklu silme için compound command
        if len(self.selected_items) > 1:
            compound = CompoundCommand("Çoklu silme")
            
            # Önce boruları sil
            for item_id in list(self.selected_items):
                if item_id in self.network.pipes:
                    cmd = RemovePipeCommand(self.network, item_id)
                    compound.add_command(cmd)
            
            # Sonra node'ları sil
            for item_id in list(self.selected_items):
                if item_id in self.network.nodes:
                    cmd = RemoveNodeCommand(self.network, item_id)
                    compound.add_command(cmd)
            
            self.command_manager.execute(compound)
        else:
            # Tek öğe silme
            item_id = self.selected_items[0]
            if item_id in self.network.nodes:
                cmd = RemoveNodeCommand(self.network, item_id)
                self.command_manager.execute(cmd)
            elif item_id in self.network.pipes:
                cmd = RemovePipeCommand(self.network, item_id)
                self.command_manager.execute(cmd)
        
        self.selected_items.clear()
        self.redraw()
    
    def _on_undo(self, event):
        """Ctrl+Z - Geri Al"""
        if self.command_manager.can_undo():
            desc = self.command_manager.get_undo_description()
            self.command_manager.undo()
            self.redraw()
            # print(f"Geri alındı: {desc}")  # Debug
    
    def _on_redo(self, event):
        """Ctrl+Y veya Ctrl+Shift+Z - Yinele"""
        if self.command_manager.can_redo():
            desc = self.command_manager.get_redo_description()
            self.command_manager.redo()
            self.redraw()
            # print(f"Yinelendi: {desc}")  # Debug
    
    def toggle_grid(self):
        """Grid göster/gizle"""
        self.show_grid = not self.show_grid
        self.redraw()
    
    def fit_to_view(self):
        """Tüm ağı görünüme sığdır"""
        if not self.network.nodes:
            return
        
        # Bounding box hesapla
        min_x = min(n.coordinates.x for n in self.network.nodes.values())
        max_x = max(n.coordinates.x for n in self.network.nodes.values())
        min_y = min(n.coordinates.y for n in self.network.nodes.values())
        max_y = max(n.coordinates.y for n in self.network.nodes.values())
        
        # Canvas boyutları
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        # Marj ekle
        margin = 50
        content_width = max_x - min_x
        content_height = max_y - min_y
        
        if content_width <= 0:
            content_width = 100
        if content_height <= 0:
            content_height = 100
        
        # Ölçek hesapla
        scale_x = (canvas_width - 2 * margin) / content_width
        scale_y = (canvas_height - 2 * margin) / content_height
        self.scale = min(scale_x, scale_y, 2.0)  # Max 2x zoom
        self.scale = max(self.scale, 0.1)  # Min 0.1x zoom
        
        # Offset hesapla (ortala)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        self.offset_x = canvas_width / 2 - center_x * self.scale
        self.offset_y = canvas_height / 2 - center_y * self.scale
        
        self.redraw()
    
    # ==================== İşlem Fonksiyonları ====================
    
    def _handle_select(self, sx, sy):
        """Seçim işlemi"""
        # Tıklanan öğeyi bul
        items = self.find_overlapping(sx - 5, sy - 5, sx + 5, sy + 5)
        
        selected = None
        for item in items:
            tags = self.gettags(item)
            if "node" in tags or "pipe" in tags:
                selected = tags[-1]  # Object ID son tag
                break
        
        # Seçimi güncelle
        if selected:
            if selected in self.selected_items:
                self.selected_items.remove(selected)
            else:
                self.selected_items.append(selected)
        else:
            self.selected_items.clear()
        
        self.redraw()
    
    def _handle_pipe_click(self, wx, wy):
        """Boru çizim tıklaması - Command pattern ile"""
        # Grid'e snap
        wx, wy = self.snap_to_grid(wx, wy)
        
        # En yakın node'u bul
        nearest_node = self._find_nearest_node(wx, wy)
        
        if not self.drawing_pipe:
            # Boru çizimi başlat
            if nearest_node:
                self.pipe_start_node = nearest_node.id
            else:
                # Yeni fitting node oluştur
                new_node = Node(
                    node_type=NodeType.FITTING,
                    coordinates=Coordinates(wx, wy, 0)
                )
                # Command ile ekle
                cmd = AddNodeCommand(self.network, new_node)
                self.command_manager.execute(cmd)
                self.pipe_start_node = new_node.id
            
            self.drawing_pipe = True
            self.redraw()
            
        else:
            # Boru çizimi bitir
            if nearest_node and nearest_node.id != self.pipe_start_node:
                end_node_id = nearest_node.id
            else:
                # Yeni fitting node oluştur
                new_node = Node(
                    node_type=NodeType.FITTING,
                    coordinates=Coordinates(wx, wy, 0)
                )
                # Command ile ekle
                cmd = AddNodeCommand(self.network, new_node)
                self.command_manager.execute(cmd)
                end_node_id = new_node.id
            
            # Boru oluştur
            start_node = self.network.get_node(self.pipe_start_node)
            end_node = self.network.get_node(end_node_id)
            
            if start_node and end_node:
                length = start_node.coordinates.distance_2d(end_node.coordinates) / 1000  # mm -> m
                
                pipe = Pipe(
                    start_node_id=self.pipe_start_node,
                    end_node_id=end_node_id,
                    length=length,
                    internal_diameter=52.5,  # Varsayılan 2"
                    nominal_diameter=50,
                    c_factor=120
                )
                # Command ile ekle
                cmd = AddPipeCommand(self.network, pipe)
                self.command_manager.execute(cmd)
            
            # Sıfırla
            self.drawing_pipe = False
            self.pipe_start_node = None
            
            if self.temp_line:
                self.delete(self.temp_line)
                self.temp_line = None
            
            self.redraw()
    
    def _add_sprinkler(self, wx, wy):
        """Sprinkler ekle - Command pattern ile"""
        wx, wy = self.snap_to_grid(wx, wy)
        
        node = Node(
            node_type=NodeType.SPRINKLER,
            coordinates=Coordinates(wx, wy, 0),
            k_factor=80,
            min_pressure_required=0.5,
            coverage_area=12.0
        )
        
        # Command ile ekle (undo/redo desteği)
        cmd = AddNodeCommand(self.network, node)
        self.command_manager.execute(cmd)
        self.redraw()
    
    def _add_source(self, wx, wy):
        """Kaynak (pompa) ekle - Command pattern ile"""
        wx, wy = self.snap_to_grid(wx, wy)
        
        node = Node(
            node_type=NodeType.SOURCE,
            coordinates=Coordinates(wx, wy, 0)
        )
        
        # Command ile ekle (undo/redo desteği)
        cmd = AddNodeCommand(self.network, node)
        self.command_manager.execute(cmd)
        self.redraw()
    
    def _find_nearest_node(self, wx, wy, tolerance=None) -> Optional[Node]:
        """En yakın node'u bul"""
        if tolerance is None:
            tolerance = self.SNAP_TOLERANCE / self.scale
        
        nearest = None
        min_dist = float('inf')
        
        for node in self.network.nodes.values():
            dist = math.sqrt(
                (node.coordinates.x - wx) ** 2 +
                (node.coordinates.y - wy) ** 2
            )
            if dist < min_dist and dist < tolerance:
                min_dist = dist
                nearest = node
        
        return nearest
    
    def _show_node_menu(self, event, node_id: str):
        """Node bağlam menüsü"""
        node = self.network.get_node(node_id)
        if not node:
            return
        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"Node: {node_id}", state="disabled")
        menu.add_separator()
        menu.add_command(label="Özellikler...", command=lambda: self._show_node_properties(node_id))
        menu.add_command(label="Kot Değiştir...", command=lambda: self._change_elevation(node_id))
        menu.add_separator()
        menu.add_command(label="Sil", command=lambda: self._delete_node(node_id))
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _show_pipe_menu(self, event, pipe_id: str):
        """Pipe bağlam menüsü"""
        pipe = self.network.get_pipe(pipe_id)
        if not pipe:
            return
        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"Boru: {pipe_id}", state="disabled")
        menu.add_separator()
        menu.add_command(label="Özellikler...", command=lambda: self._show_pipe_properties(pipe_id))
        menu.add_command(label="Çap Değiştir...", command=lambda: self._change_diameter(pipe_id))
        menu.add_command(label="Fitting Ekle...", command=lambda: self._add_fitting_to_pipe(pipe_id))
        menu.add_separator()
        menu.add_command(label="Sil", command=lambda: self._delete_pipe(pipe_id))
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _show_node_properties(self, node_id: str):
        """Node özellikler dialogu"""
        node = self.network.get_node(node_id)
        if not node:
            return
        
        dialog = NodePropertiesDialog(self, node)
        self.wait_window(dialog)
        self.redraw()
    
    def _show_pipe_properties(self, pipe_id: str):
        """Pipe özellikler dialogu"""
        pipe = self.network.get_pipe(pipe_id)
        if not pipe:
            return
        
        dialog = PipePropertiesDialog(self, pipe)
        self.wait_window(dialog)
        self.redraw()
    
    def _change_elevation(self, node_id: str):
        """Kot değiştir"""
        node = self.network.get_node(node_id)
        if not node:
            return
        
        result = simpledialog.askfloat(
            "Kot Değiştir",
            f"Mevcut kot: {node.get_elevation():.2f} m\nYeni kot (m):",
            initialvalue=node.get_elevation()
        )
        
        if result is not None:
            node.set_elevation(result)
            self.redraw()
    
    def _change_diameter(self, pipe_id: str):
        """Çap değiştir"""
        pipe = self.network.get_pipe(pipe_id)
        if not pipe:
            return
        
        result = simpledialog.askfloat(
            "Çap Değiştir",
            f"Mevcut iç çap: {pipe.internal_diameter:.1f} mm\nYeni iç çap (mm):",
            initialvalue=pipe.internal_diameter
        )
        
        if result is not None:
            pipe.internal_diameter = result
            self.redraw()
    
    def _add_fitting_to_pipe(self, pipe_id: str):
        """Boruya fitting ekle"""
        pipe = self.network.get_pipe(pipe_id)
        if not pipe:
            return
        
        dialog = AddFittingDialog(self, pipe)
        self.wait_window(dialog)
        self.redraw()
    
    def _delete_node(self, node_id: str):
        """Node sil - Command pattern ile"""
        if messagebox.askyesno("Sil", f"'{node_id}' düğümünü silmek istiyor musunuz?"):
            cmd = RemoveNodeCommand(self.network, node_id)
            self.command_manager.execute(cmd)
            self.redraw()
    
    def _delete_pipe(self, pipe_id: str):
        """Pipe sil - Command pattern ile"""
        if messagebox.askyesno("Sil", f"'{pipe_id}' borusunu silmek istiyor musunuz?"):
            cmd = RemovePipeCommand(self.network, pipe_id)
            self.command_manager.execute(cmd)
            self.redraw()


class NodePropertiesDialog(tk.Toplevel):
    """Node özellikler dialogu"""
    
    def __init__(self, parent, node: Node):
        super().__init__(parent)
        self.node = node
        
        self.title(f"Node Özellikleri - {node.id}")
        self.geometry("350x400")
        self.resizable(False, False)
        
        self._create_widgets()
        
        # Modal yap
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # ID
        ttk.Label(frame, text="ID:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(frame, text=self.node.id).grid(row=0, column=1, sticky="w", pady=2)
        
        # Tip
        ttk.Label(frame, text="Tip:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(frame, text=self.node.node_type.value).grid(row=1, column=1, sticky="w", pady=2)
        
        # Koordinatlar
        ttk.Label(frame, text="X (mm):").grid(row=2, column=0, sticky="w", pady=2)
        self.x_var = tk.DoubleVar(value=self.node.coordinates.x)
        ttk.Entry(frame, textvariable=self.x_var, width=15).grid(row=2, column=1, pady=2)
        
        ttk.Label(frame, text="Y (mm):").grid(row=3, column=0, sticky="w", pady=2)
        self.y_var = tk.DoubleVar(value=self.node.coordinates.y)
        ttk.Entry(frame, textvariable=self.y_var, width=15).grid(row=3, column=1, pady=2)
        
        ttk.Label(frame, text="Z / Kot (m):").grid(row=4, column=0, sticky="w", pady=2)
        self.z_var = tk.DoubleVar(value=self.node.coordinates.z)
        ttk.Entry(frame, textvariable=self.z_var, width=15).grid(row=4, column=1, pady=2)
        
        # Sprinkler özellikleri
        if self.node.node_type == NodeType.SPRINKLER:
            ttk.Separator(frame, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
            ttk.Label(frame, text="--- Sprinkler ---", font=("Arial", 9, "bold")).grid(row=6, column=0, columnspan=2)
            
            ttk.Label(frame, text="K-Faktör:").grid(row=7, column=0, sticky="w", pady=2)
            self.k_var = tk.DoubleVar(value=self.node.k_factor)
            ttk.Entry(frame, textvariable=self.k_var, width=15).grid(row=7, column=1, pady=2)
            
            ttk.Label(frame, text="Min. Basınç (bar):").grid(row=8, column=0, sticky="w", pady=2)
            self.p_var = tk.DoubleVar(value=self.node.min_pressure_required)
            ttk.Entry(frame, textvariable=self.p_var, width=15).grid(row=8, column=1, pady=2)
            
            ttk.Label(frame, text="Koruma Alanı (m²):").grid(row=9, column=0, sticky="w", pady=2)
            self.area_var = tk.DoubleVar(value=self.node.coverage_area)
            ttk.Entry(frame, textvariable=self.area_var, width=15).grid(row=9, column=1, pady=2)
        
        # Hesaplama sonuçları
        if self.node.is_calculated:
            ttk.Separator(frame, orient="horizontal").grid(row=10, column=0, columnspan=2, sticky="ew", pady=10)
            ttk.Label(frame, text="--- Hesaplama Sonuçları ---", font=("Arial", 9, "bold")).grid(row=11, column=0, columnspan=2)
            
            ttk.Label(frame, text="Basınç (bar):").grid(row=12, column=0, sticky="w", pady=2)
            ttk.Label(frame, text=f"{self.node.pressure:.3f}" if self.node.pressure else "N/A").grid(row=12, column=1, sticky="w", pady=2)
            
            ttk.Label(frame, text="Debi (L/dk):").grid(row=13, column=0, sticky="w", pady=2)
            ttk.Label(frame, text=f"{self.node.total_flow:.1f}" if self.node.total_flow else "N/A").grid(row=13, column=1, sticky="w", pady=2)
        
        # Butonlar
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=20, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Kaydet", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="İptal", command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def _save(self):
        """Değişiklikleri kaydet"""
        self.node.coordinates.x = self.x_var.get()
        self.node.coordinates.y = self.y_var.get()
        self.node.coordinates.z = self.z_var.get()
        
        if self.node.node_type == NodeType.SPRINKLER:
            self.node.k_factor = self.k_var.get()
            self.node.min_pressure_required = self.p_var.get()
            self.node.coverage_area = self.area_var.get()
        
        self.destroy()


class PipePropertiesDialog(tk.Toplevel):
    """Pipe özellikler dialogu"""
    
    def __init__(self, parent, pipe: Pipe):
        super().__init__(parent)
        self.pipe = pipe
        
        self.title(f"Boru Özellikleri - {pipe.id}")
        self.geometry("400x500")
        self.resizable(False, False)
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # ID
        ttk.Label(frame, text="ID:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(frame, text=self.pipe.id).grid(row=0, column=1, sticky="w", pady=2)
        
        # Başlangıç-Bitiş
        ttk.Label(frame, text="Başlangıç:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(frame, text=self.pipe.start_node_id).grid(row=1, column=1, sticky="w", pady=2)
        
        ttk.Label(frame, text="Bitiş:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(frame, text=self.pipe.end_node_id).grid(row=2, column=1, sticky="w", pady=2)
        
        # Fiziksel özellikler
        ttk.Separator(frame, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Label(frame, text="Uzunluk (m):").grid(row=4, column=0, sticky="w", pady=2)
        self.length_var = tk.DoubleVar(value=self.pipe.length)
        ttk.Entry(frame, textvariable=self.length_var, width=15).grid(row=4, column=1, pady=2)
        
        ttk.Label(frame, text="İç Çap (mm):").grid(row=5, column=0, sticky="w", pady=2)
        self.diameter_var = tk.DoubleVar(value=self.pipe.internal_diameter)
        ttk.Entry(frame, textvariable=self.diameter_var, width=15).grid(row=5, column=1, pady=2)
        
        ttk.Label(frame, text="C Faktörü:").grid(row=6, column=0, sticky="w", pady=2)
        self.c_var = tk.DoubleVar(value=self.pipe.c_factor)
        ttk.Entry(frame, textvariable=self.c_var, width=15).grid(row=6, column=1, pady=2)
        
        ttk.Label(frame, text="Malzeme:").grid(row=7, column=0, sticky="w", pady=2)
        self.material_var = tk.StringVar(value=self.pipe.material)
        ttk.Combobox(frame, textvariable=self.material_var, 
                     values=["Steel", "CPVC", "Galvanized"], width=12).grid(row=7, column=1, pady=2)
        
        # Fittings
        ttk.Separator(frame, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(frame, text=f"Fittings ({len(self.pipe.fittings)}):").grid(row=9, column=0, sticky="nw", pady=2)
        
        fitting_frame = ttk.Frame(frame)
        fitting_frame.grid(row=9, column=1, sticky="w", pady=2)
        
        for f in self.pipe.fittings:
            ttk.Label(fitting_frame, text=f"• {f.category.value}: {f.equivalent_length}m").pack(anchor="w")
        
        # Eşdeğer uzunluk
        ttk.Label(frame, text="Toplam Eq.L (m):").grid(row=10, column=0, sticky="w", pady=2)
        ttk.Label(frame, text=f"{self.pipe.get_total_equivalent_length():.2f}").grid(row=10, column=1, sticky="w", pady=2)
        
        # Hesaplama sonuçları
        if self.pipe.flow is not None:
            ttk.Separator(frame, orient="horizontal").grid(row=11, column=0, columnspan=2, sticky="ew", pady=10)
            ttk.Label(frame, text="--- Hesaplama Sonuçları ---", font=("Arial", 9, "bold")).grid(row=12, column=0, columnspan=2)
            
            ttk.Label(frame, text="Debi (L/dk):").grid(row=13, column=0, sticky="w", pady=2)
            ttk.Label(frame, text=f"{self.pipe.flow:.1f}").grid(row=13, column=1, sticky="w", pady=2)
            
            ttk.Label(frame, text="Hız (m/s):").grid(row=14, column=0, sticky="w", pady=2)
            ttk.Label(frame, text=f"{self.pipe.velocity:.2f}").grid(row=14, column=1, sticky="w", pady=2)
            
            ttk.Label(frame, text="Sürtünme Kaybı (bar):").grid(row=15, column=0, sticky="w", pady=2)
            ttk.Label(frame, text=f"{self.pipe.friction_loss:.4f}").grid(row=15, column=1, sticky="w", pady=2)
        
        # Butonlar
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=20, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Kaydet", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="İptal", command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def _save(self):
        """Değişiklikleri kaydet"""
        self.pipe.length = self.length_var.get()
        self.pipe.internal_diameter = self.diameter_var.get()
        self.pipe.c_factor = self.c_var.get()
        self.pipe.material = self.material_var.get()
        
        self.destroy()


class AddFittingDialog(tk.Toplevel):
    """Fitting ekleme dialogu"""
    
    def __init__(self, parent, pipe: Pipe):
        super().__init__(parent)
        self.pipe = pipe
        
        self.title("Fitting Ekle")
        self.geometry("300x200")
        self.resizable(False, False)
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Fitting Tipi:").grid(row=0, column=0, sticky="w", pady=5)
        
        self.fitting_var = tk.StringVar()
        fitting_types = [f.value for f in FittingCategory]
        combo = ttk.Combobox(frame, textvariable=self.fitting_var, values=fitting_types, width=25)
        combo.grid(row=0, column=1, pady=5)
        combo.set(FittingCategory.ELBOW_90.value)
        
        ttk.Label(frame, text="Eşdeğer Uzunluk (m):").grid(row=1, column=0, sticky="w", pady=5)
        self.eq_length_var = tk.DoubleVar(value=1.5)
        ttk.Entry(frame, textvariable=self.eq_length_var, width=10).grid(row=1, column=1, sticky="w", pady=5)
        
        # Butonlar
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Ekle", command=self._add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="İptal", command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def _add(self):
        """Fitting ekle"""
        try:
            category = FittingCategory(self.fitting_var.get())
        except ValueError:
            category = FittingCategory.ELBOW_90
        
        fitting = Fitting(
            category=category,
            equivalent_length=self.eq_length_var.get()
        )
        self.pipe.add_fitting(fitting)
        self.destroy()


# Ana uygulama sınıfını ayrı modülde tutacağız (main_app.py)
