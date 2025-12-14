"""
3D Visualization (Basic)

Basit isometric/3D görünüm:
- Z-koordinat desteği (kat yükseklikleri)
- Isometric projection
- Rotate, zoom, pan
- Export PNG
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Tuple, Optional
import math


class Isometric3DView(tk.Canvas):
    """
    Basit isometric 3D görünüm
    
    Koordinat sistemi:
    - X: Sağ (30° açıyla)
    - Y: Sol (30° açıyla)
    - Z: Yukarı (dikey)
    """
    
    def __init__(self, parent, network, **kwargs):
        super().__init__(parent, bg='#1E1E1E', highlightthickness=0, **kwargs)
        
        self.network = network
        
        # Görünüm ayarları
        self.scale = 2.0
        self.rotation_z = 45  # Z ekseni etrafında rotasyon (derece)
        self.offset_x = 0
        self.offset_y = 0
        
        # Isometric açılar (sabit)
        self.iso_angle = 30  # derece
        
        # Drag ayarları
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.dragging = False
        
        # Event bindings
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<MouseWheel>', self._on_mousewheel)
        
        # İlk çizim
        self.after(100, self.redraw)
    
    def world_to_iso(self, x: float, y: float, z: float) -> Tuple[float, float]:
        """
        Dünya koordinatlarını isometric ekran koordinatlarına çevir
        
        Args:
            x, y, z: Dünya koordinatları
            
        Returns:
            (screen_x, screen_y) tuple
        """
        # Z rotasyonu uygula
        angle_rad = math.radians(self.rotation_z)
        x_rot = x * math.cos(angle_rad) - y * math.sin(angle_rad)
        y_rot = x * math.sin(angle_rad) + y * math.cos(angle_rad)
        
        # Isometric projection
        iso_x = (x_rot - y_rot) * math.cos(math.radians(self.iso_angle))
        iso_y = (x_rot + y_rot) * math.sin(math.radians(self.iso_angle)) - z
        
        # Ölçekle ve merkez ofset ekle
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()
        
        screen_x = canvas_width / 2 + iso_x * self.scale + self.offset_x
        screen_y = canvas_height / 2 + iso_y * self.scale + self.offset_y
        
        return (screen_x, screen_y)
    
    def redraw(self):
        """3D görünümü yeniden çiz"""
        self.delete('all')
        
        # Grid çiz (opsiyonel)
        self._draw_grid()
        
        # Boruları çiz
        self._draw_pipes()
        
        # Node'ları çiz
        self._draw_nodes()
        
        # Eksen çiz
        self._draw_axes()
    
    def _draw_grid(self):
        """Zemin grid'i çiz"""
        grid_size = 100  # Dünya birimi
        grid_count = 10
        
        for i in range(-grid_count, grid_count + 1):
            # X doğrultusunda çizgiler
            x1, y1 = self.world_to_iso(i * grid_size, -grid_count * grid_size, 0)
            x2, y2 = self.world_to_iso(i * grid_size, grid_count * grid_size, 0)
            self.create_line(x1, y1, x2, y2, fill='#333333', width=1)
            
            # Y doğrultusunda çizgiler
            x1, y1 = self.world_to_iso(-grid_count * grid_size, i * grid_size, 0)
            x2, y2 = self.world_to_iso(grid_count * grid_size, i * grid_size, 0)
            self.create_line(x1, y1, x2, y2, fill='#333333', width=1)
    
    def _draw_pipes(self):
        """Boruları çiz"""
        for pipe in self.network.pipes:
            node1 = self.network.nodes.get(pipe.node1_id)
            node2 = self.network.nodes.get(pipe.node2_id)
            
            if node1 and node2:
                # Z koordinatı (kat yüksekliği)
                z1 = getattr(node1, 'z_level', 0) * 300  # Her kat 300 birim
                z2 = getattr(node2, 'z_level', 0) * 300
                
                x1, y1 = self.world_to_iso(node1.coordinates.x, node1.coordinates.y, z1)
                x2, y2 = self.world_to_iso(node2.coordinates.x, node2.coordinates.y, z2)
                
                # Boru rengi (basınç/hıza göre)
                color = self._get_pipe_color(pipe)
                
                self.create_line(x1, y1, x2, y2, fill=color, width=3)
    
    def _draw_nodes(self):
        """Node'ları çiz"""
        for node in self.network.nodes.values():
            z = getattr(node, 'z_level', 0) * 300
            x, y = self.world_to_iso(node.coordinates.x, node.coordinates.y, z)
            
            # Node tipi
            if node.node_type.value == 'sprinkler':
                # Sprinkler (yeşil küre)
                r = 6
                self.create_oval(x - r, y - r, x + r, y + r, 
                               fill='#00FF00', outline='#00AA00', width=2)
                # Dikey çizgi (aşağı doğru)
                x_down, y_down = self.world_to_iso(node.coordinates.x, node.coordinates.y, z - 50)
                self.create_line(x, y, x_down, y_down, fill='#00AA00', width=2)
                
            elif node.node_type.value == 'source':
                # Kaynak (kırmızı küp)
                size = 12
                # Basit küp çizimi
                self._draw_cube(node.coordinates.x, node.coordinates.y, z, size, '#FF4444')
                
            else:
                # Junction (mavi nokta)
                r = 4
                self.create_oval(x - r, y - r, x + r, y + r,
                               fill='#4444FF', outline='#0000AA', width=1)
    
    def _draw_cube(self, wx: float, wy: float, wz: float, size: float, color: str):
        """Basit küp çiz"""
        # Küp köşeleri
        corners = [
            (wx - size, wy - size, wz - size),
            (wx + size, wy - size, wz - size),
            (wx + size, wy + size, wz - size),
            (wx - size, wy + size, wz - size),
            (wx - size, wy - size, wz + size),
            (wx + size, wy - size, wz + size),
            (wx + size, wy + size, wz + size),
            (wx - size, wy + size, wz + size),
        ]
        
        # Ekran koordinatlarına çevir
        screen_corners = [self.world_to_iso(x, y, z) for x, y, z in corners]
        
        # Yüzleri çiz (arka yüzler ilk)
        faces = [
            [0, 1, 2, 3],  # Alt
            [4, 5, 6, 7],  # Üst
            [0, 1, 5, 4],  # Ön
            [2, 3, 7, 6],  # Arka
            [0, 3, 7, 4],  # Sol
            [1, 2, 6, 5],  # Sağ
        ]
        
        for face in faces:
            points = []
            for idx in face:
                points.extend(screen_corners[idx])
            
            self.create_polygon(points, fill=color, outline='darkred', width=1)
    
    def _draw_axes(self):
        """Koordinat eksenlerini çiz"""
        origin_x, origin_y = self.world_to_iso(0, 0, 0)
        
        # X ekseni (kırmızı)
        x_end, y_end = self.world_to_iso(200, 0, 0)
        self.create_line(origin_x, origin_y, x_end, y_end, 
                        fill='red', width=2, arrow=tk.LAST)
        self.create_text(x_end + 10, y_end, text='X', fill='red', font=('Arial', 10, 'bold'))
        
        # Y ekseni (yeşil)
        x_end, y_end = self.world_to_iso(0, 200, 0)
        self.create_line(origin_x, origin_y, x_end, y_end,
                        fill='green', width=2, arrow=tk.LAST)
        self.create_text(x_end + 10, y_end, text='Y', fill='green', font=('Arial', 10, 'bold'))
        
        # Z ekseni (mavi)
        x_end, y_end = self.world_to_iso(0, 0, 200)
        self.create_line(origin_x, origin_y, x_end, y_end,
                        fill='blue', width=2, arrow=tk.LAST)
        self.create_text(x_end, y_end - 10, text='Z', fill='blue', font=('Arial', 10, 'bold'))
    
    def _get_pipe_color(self, pipe) -> str:
        """Boru rengi (basınç/hıza göre)"""
        # Basit renklendirme
        if hasattr(pipe, 'velocity'):
            velocity = pipe.velocity
            if velocity > 6:
                return '#FF0000'  # Kırmızı (yüksek hız)
            elif velocity > 3:
                return '#FFA500'  # Turuncu (orta hız)
            else:
                return '#00AAFF'  # Mavi (düşük hız)
        return '#00AAFF'
    
    def rotate(self, delta_angle: float):
        """Z ekseni etrafında döndür"""
        self.rotation_z = (self.rotation_z + delta_angle) % 360
        self.redraw()
    
    def zoom(self, factor: float):
        """Yakınlaştır/uzaklaştır"""
        self.scale *= factor
        self.scale = max(0.1, min(10.0, self.scale))  # Limit
        self.redraw()
    
    def reset_view(self):
        """Görünümü sıfırla"""
        self.scale = 2.0
        self.rotation_z = 45
        self.offset_x = 0
        self.offset_y = 0
        self.redraw()
    
    def _on_press(self, event):
        """Mouse basma"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.dragging = True
    
    def _on_drag(self, event):
        """Mouse sürükleme"""
        if self.dragging:
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            self.offset_x += dx
            self.offset_y += dy
            
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            
            self.redraw()
    
    def _on_release(self, event):
        """Mouse bırakma"""
        self.dragging = False
    
    def _on_mousewheel(self, event):
        """Mouse tekerleği (zoom)"""
        if event.delta > 0:
            self.zoom(1.1)
        else:
            self.zoom(0.9)
    
    def export_png(self, filename: str):
        """PNG olarak dışa aktar (basit - postscript kullanarak)"""
        try:
            # Canvas'ı postscript olarak kaydet
            ps_file = filename.replace('.png', '.ps')
            self.postscript(file=ps_file, colormode='color')
            
            # PIL varsa PNG'ye çevir
            try:
                from PIL import Image
                img = Image.open(ps_file)
                img.save(filename, 'PNG')
                import os
                os.remove(ps_file)
                return True
            except ImportError:
                messagebox.showinfo("Bilgi", 
                    f"PNG export için PIL/Pillow gerekli.\n"
                    f"PostScript dosyası kaydedildi: {ps_file}")
                return False
                
        except Exception as e:
            messagebox.showerror("Hata", f"Export hatası: {e}")
            return False


class View3DWindow(tk.Toplevel):
    """3D görünüm penceresi"""
    
    def __init__(self, parent, network):
        super().__init__(parent)
        
        self.network = network
        
        self.title("3D Görünüm (Isometric)")
        self.geometry("800x600")
        
        self._create_widgets()
        
        self.transient(parent)
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(toolbar, text="🎮 Kontroller:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="↻ Sola Döndür", 
                  command=lambda: self.view_3d.rotate(-15), width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="↺ Sağa Döndür",
                  command=lambda: self.view_3d.rotate(15), width=15).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(toolbar, text="🔍+ Yakınlaştır",
                  command=lambda: self.view_3d.zoom(1.2), width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔍− Uzaklaştır",
                  command=lambda: self.view_3d.zoom(0.8), width=15).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(toolbar, text="🏠 Sıfırla",
                  command=self.view_3d.reset_view, width=12).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(toolbar, text="💾 PNG Export",
                  command=self._export_png, width=12).pack(side=tk.LEFT, padx=2)
        
        # 3D Canvas
        self.view_3d = Isometric3DView(self, self.network)
        self.view_3d.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Bilgi
        info_label = ttk.Label(self, 
            text="💡 Mouse ile sürükle (pan) | Scroll ile zoom | Butonlarla döndür",
            foreground='gray')
        info_label.pack(pady=5)
    
    def _export_png(self):
        """PNG export"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All files", "*.*")]
        )
        
        if filename:
            if self.view_3d.export_png(filename):
                messagebox.showinfo("Başarılı", f"3D görünüm kaydedildi:\n{filename}")
