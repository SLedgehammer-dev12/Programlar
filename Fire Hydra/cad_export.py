"""
CAD Export Module - DXF/PDF Export
FireHydra - Yangın Söndürme Sistemi Hidrolik Hesaplama
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from typing import List, Tuple, Optional
import os
from datetime import datetime

try:
    import ezdxf
    from ezdxf import colors
    from ezdxf.enums import TextEntityAlignment
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False

try:
    from reportlab.lib.pagesizes import A4, A3, A2, A1
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors as pdf_colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


@dataclass
class CADExportSettings:
    """CAD export ayarları"""
    layer_pipes: str = "PIPES"
    layer_nodes: str = "NODES"
    layer_sprinklers: str = "SPRINKLERS"
    layer_text: str = "TEXT"
    layer_dimensions: str = "DIMENSIONS"
    
    color_pipes: int = colors.CYAN if HAS_EZDXF else 4
    color_nodes: int = colors.RED if HAS_EZDXF else 1
    color_sprinklers: int = colors.GREEN if HAS_EZDXF else 3
    color_text: int = colors.WHITE if HAS_EZDXF else 7
    
    text_height: float = 0.5  # metre
    scale: float = 100  # 1:100
    units: str = "Metric"
    
    include_dimensions: bool = True
    include_labels: bool = True
    include_title_block: bool = True
    
    # Title block bilgileri
    project_name: str = "Yangın Söndürme Sistemi"
    project_number: str = ""
    drawn_by: str = ""
    checked_by: str = ""
    company: str = ""


class DXFExporter:
    """DXF dosya export sınıfı"""
    
    def __init__(self, network, settings: CADExportSettings):
        self.network = network
        self.settings = settings
        
        if not HAS_EZDXF:
            raise ImportError("ezdxf kütüphanesi yüklü değil. 'pip install ezdxf' komutunu çalıştırın.")
    
    def export(self, filepath: str) -> bool:
        """Network'ü DXF dosyasına export et"""
        try:
            # Yeni DXF dokümanı oluştur
            doc = ezdxf.new('R2010', setup=True)
            msp = doc.modelspace()
            
            # Layer'ları oluştur
            self._create_layers(doc)
            
            # Network elemanlarını çiz
            self._draw_pipes(msp)
            self._draw_nodes(msp)
            
            if self.settings.include_labels:
                self._draw_labels(msp)
            
            if self.settings.include_dimensions:
                self._draw_dimensions(msp)
            
            if self.settings.include_title_block:
                self._draw_title_block(msp)
            
            # Dosyayı kaydet
            doc.saveas(filepath)
            return True
            
        except Exception as e:
            print(f"DXF export hatası: {e}")
            return False
    
    def _create_layers(self, doc):
        """Layer'ları oluştur"""
        layers = doc.layers
        
        layers.add(self.settings.layer_pipes, color=self.settings.color_pipes)
        layers.add(self.settings.layer_nodes, color=self.settings.color_nodes)
        layers.add(self.settings.layer_sprinklers, color=self.settings.color_sprinklers)
        layers.add(self.settings.layer_text, color=self.settings.color_text)
        layers.add(self.settings.layer_dimensions, color=self.settings.color_text)
    
    def _draw_pipes(self, msp):
        """Boruları çiz"""
        for pipe in self.network.pipes:
            start_node = self.network.get_node(pipe.start_node_id)
            end_node = self.network.get_node(pipe.end_node_id)
            
            if start_node and end_node:
                # Boru çizgisi
                msp.add_line(
                    (start_node.x, start_node.y),
                    (end_node.x, end_node.y),
                    dxfattribs={'layer': self.settings.layer_pipes}
                )
                
                # Boru çapını göster (ortasına)
                mid_x = (start_node.x + end_node.x) / 2
                mid_y = (start_node.y + end_node.y) / 2
                
                diameter_text = f"DN{pipe.diameter_mm:.0f}"
                msp.add_text(
                    diameter_text,
                    dxfattribs={
                        'layer': self.settings.layer_text,
                        'height': self.settings.text_height
                    }
                ).set_placement((mid_x, mid_y), align=TextEntityAlignment.MIDDLE_CENTER)
    
    def _draw_nodes(self, msp):
        """Node'ları çiz"""
        for node in self.network.nodes:
            radius = 0.3  # metre
            
            # Node tipine göre farklı çiz
            if node.node_type == "sprinkler":
                # Sprinkler'ları daire olarak çiz
                msp.add_circle(
                    (node.x, node.y),
                    radius,
                    dxfattribs={'layer': self.settings.layer_sprinklers}
                )
                
                # Sprinkler sembolü (artı işareti)
                msp.add_line(
                    (node.x - radius, node.y),
                    (node.x + radius, node.y),
                    dxfattribs={'layer': self.settings.layer_sprinklers}
                )
                msp.add_line(
                    (node.x, node.y - radius),
                    (node.x, node.y + radius),
                    dxfattribs={'layer': self.settings.layer_sprinklers}
                )
                
            elif node.node_type == "source":
                # Kaynak noktası - kare
                offset = radius
                points = [
                    (node.x - offset, node.y - offset),
                    (node.x + offset, node.y - offset),
                    (node.x + offset, node.y + offset),
                    (node.x - offset, node.y + offset),
                    (node.x - offset, node.y - offset)
                ]
                msp.add_lwpolyline(points, dxfattribs={'layer': self.settings.layer_nodes})
                
            else:
                # Junction - küçük daire
                msp.add_circle(
                    (node.x, node.y),
                    radius * 0.5,
                    dxfattribs={'layer': self.settings.layer_nodes}
                )
    
    def _draw_labels(self, msp):
        """Etiketleri çiz"""
        for node in self.network.nodes:
            # Node ID'sini yaz
            msp.add_text(
                node.id,
                dxfattribs={
                    'layer': self.settings.layer_text,
                    'height': self.settings.text_height * 0.7
                }
            ).set_placement((node.x, node.y - 0.8), align=TextEntityAlignment.MIDDLE_CENTER)
    
    def _draw_dimensions(self, msp):
        """Boyutları çiz"""
        # Basit boyutlandırma - boruların uzunluklarını göster
        for pipe in self.network.pipes:
            start_node = self.network.get_node(pipe.start_node_id)
            end_node = self.network.get_node(pipe.end_node_id)
            
            if start_node and end_node:
                # Uzunluk hesapla
                import math
                dx = end_node.x - start_node.x
                dy = end_node.y - start_node.y
                length = math.sqrt(dx**2 + dy**2)
                
                # Boyut çizgisi ekle
                mid_x = (start_node.x + end_node.x) / 2
                mid_y = (start_node.y + end_node.y) / 2
                
                dim_text = f"{length:.2f}m"
                msp.add_text(
                    dim_text,
                    dxfattribs={
                        'layer': self.settings.layer_dimensions,
                        'height': self.settings.text_height * 0.6,
                        'color': self.settings.color_text
                    }
                ).set_placement((mid_x, mid_y + 0.5), align=TextEntityAlignment.MIDDLE_CENTER)
    
    def _draw_title_block(self, msp):
        """Title block çiz"""
        # Sağ alt köşede title block
        # Network sınırlarını bul
        if not self.network.nodes:
            return
        
        min_x = min(node.x for node in self.network.nodes)
        max_x = max(node.x for node in self.network.nodes)
        min_y = min(node.y for node in self.network.nodes)
        
        # Title block konumu
        block_x = max_x + 5
        block_y = min_y
        block_width = 20
        block_height = 15
        
        # Dış çerçeve
        points = [
            (block_x, block_y),
            (block_x + block_width, block_y),
            (block_x + block_width, block_y + block_height),
            (block_x, block_y + block_height),
            (block_x, block_y)
        ]
        msp.add_lwpolyline(points, dxfattribs={'layer': self.settings.layer_text})
        
        # Başlıklar ve bilgiler
        text_height = 0.5
        y_offset = block_y + block_height - 1
        
        titles = [
            ("Proje:", self.settings.project_name),
            ("Proje No:", self.settings.project_number),
            ("Çizen:", self.settings.drawn_by),
            ("Kontrol:", self.settings.checked_by),
            ("Firma:", self.settings.company),
            ("Tarih:", datetime.now().strftime("%d.%m.%Y")),
            ("Ölçek:", f"1:{self.settings.scale:.0f}")
        ]
        
        for title, value in titles:
            msp.add_text(
                title,
                dxfattribs={'layer': self.settings.layer_text, 'height': text_height}
            ).set_placement((block_x + 0.5, y_offset), align=TextEntityAlignment.MIDDLE_LEFT)
            
            msp.add_text(
                value,
                dxfattribs={'layer': self.settings.layer_text, 'height': text_height}
            ).set_placement((block_x + 6, y_offset), align=TextEntityAlignment.MIDDLE_LEFT)
            
            y_offset -= 2


class PDFExporter:
    """PDF dosya export sınıfı"""
    
    def __init__(self, network, settings: CADExportSettings, results=None):
        self.network = network
        self.settings = settings
        self.results = results
        
        if not HAS_REPORTLAB:
            raise ImportError("reportlab kütüphanesi yüklü değil. 'pip install reportlab' komutunu çalıştırın.")
    
    def export(self, filepath: str, page_size='A3') -> bool:
        """Network'ü PDF dosyasına export et"""
        try:
            # Sayfa boyutunu seç
            if page_size == 'A4':
                size = A4
            elif page_size == 'A3':
                size = A3
            elif page_size == 'A2':
                size = A2
            elif page_size == 'A1':
                size = A1
            else:
                size = A3
            
            # PDF oluştur
            c = canvas.Canvas(filepath, pagesize=size)
            width, height = size
            
            # Title block
            if self.settings.include_title_block:
                self._draw_title_block_pdf(c, width, height)
            
            # Network çizimi
            self._draw_network_pdf(c, width, height)
            
            # Sonuçları ekle (varsa)
            if self.results:
                self._draw_results_pdf(c, width, height)
            
            # Kaydet
            c.save()
            return True
            
        except Exception as e:
            print(f"PDF export hatası: {e}")
            return False
    
    def _draw_title_block_pdf(self, c, width, height):
        """PDF için title block"""
        # Sağ üst köşe
        block_x = width - 200 * mm
        block_y = height - 50 * mm
        block_width = 180 * mm
        block_height = 40 * mm
        
        # Çerçeve
        c.rect(block_x, block_y, block_width, block_height)
        
        # Başlık
        c.setFont("Helvetica-Bold", 14)
        c.drawString(block_x + 5*mm, block_y + block_height - 10*mm, "YANGIN SÖNDÜRME SİSTEMİ")
        
        # Bilgiler
        c.setFont("Helvetica", 10)
        y = block_y + block_height - 20*mm
        
        info = [
            f"Proje: {self.settings.project_name}",
            f"Proje No: {self.settings.project_number}",
            f"Tarih: {datetime.now().strftime('%d.%m.%Y')}",
            f"Ölçek: 1:{self.settings.scale:.0f}"
        ]
        
        for line in info:
            c.drawString(block_x + 5*mm, y, line)
            y -= 5*mm
    
    def _draw_network_pdf(self, c, width, height):
        """Network'ü PDF'e çiz"""
        if not self.network.nodes:
            return
        
        # Koordinat dönüşümü için sınırları bul
        min_x = min(node.x for node in self.network.nodes)
        max_x = max(node.x for node in self.network.nodes)
        min_y = min(node.y for node in self.network.nodes)
        max_y = max(node.y for node in self.network.nodes)
        
        # Çizim alanı (title block için yer bırak)
        margin = 20 * mm
        draw_width = width - 2 * margin
        draw_height = height - 80 * mm  # Title block için yer
        
        # Ölçekleme faktörü
        network_width = max_x - min_x
        network_height = max_y - min_y
        
        if network_width == 0 or network_height == 0:
            return
        
        scale_x = draw_width / network_width
        scale_y = draw_height / network_height
        scale = min(scale_x, scale_y) * 0.9  # %90 kullan, kenar boşluğu için
        
        def transform(x, y):
            """Dünya koordinatlarını PDF koordinatlarına dönüştür"""
            tx = margin + (x - min_x) * scale
            ty = margin + (y - min_y) * scale
            return tx, ty
        
        # Boruları çiz
        c.setStrokeColor(pdf_colors.blue)
        c.setLineWidth(2)
        
        for pipe in self.network.pipes:
            start_node = self.network.get_node(pipe.start_node_id)
            end_node = self.network.get_node(pipe.end_node_id)
            
            if start_node and end_node:
                x1, y1 = transform(start_node.x, start_node.y)
                x2, y2 = transform(end_node.x, end_node.y)
                c.line(x1, y1, x2, y2)
                
                # Boru çapı etiketi
                if self.settings.include_labels:
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    c.setFont("Helvetica", 8)
                    c.setFillColor(pdf_colors.black)
                    c.drawString(mid_x, mid_y, f"DN{pipe.diameter_mm:.0f}")
        
        # Node'ları çiz
        for node in self.network.nodes:
            x, y = transform(node.x, node.y)
            
            if node.node_type == "sprinkler":
                # Sprinkler - yeşil daire
                c.setFillColor(pdf_colors.green)
                c.setStrokeColor(pdf_colors.darkgreen)
                c.circle(x, y, 3*mm, fill=1)
                
            elif node.node_type == "source":
                # Kaynak - kırmızı kare
                c.setFillColor(pdf_colors.red)
                c.setStrokeColor(pdf_colors.darkred)
                c.rect(x - 3*mm, y - 3*mm, 6*mm, 6*mm, fill=1)
                
            else:
                # Junction - küçük daire
                c.setFillColor(pdf_colors.gray)
                c.circle(x, y, 1.5*mm, fill=1)
            
            # Node ID'si
            if self.settings.include_labels:
                c.setFont("Helvetica", 7)
                c.setFillColor(pdf_colors.black)
                c.drawString(x + 4*mm, y - 2*mm, node.id)
    
    def _draw_results_pdf(self, c, width, height):
        """Hesaplama sonuçlarını PDF'e ekle (yeni sayfa)"""
        c.showPage()
        
        # Başlık
        c.setFont("Helvetica-Bold", 16)
        c.drawString(30*mm, height - 30*mm, "HİDROLİK HESAPLAMA SONUÇLARI")
        
        # Sonuçları yaz
        c.setFont("Helvetica", 10)
        y = height - 50*mm
        
        if isinstance(self.results, str):
            # String olarak gelen sonuçları satır satır yaz
            for line in self.results.split('\n'):
                if y < 30*mm:  # Sayfa sonu kontrolü
                    c.showPage()
                    y = height - 30*mm
                c.drawString(30*mm, y, line)
                y -= 4*mm


class CADExportDialog(tk.Toplevel):
    """CAD export dialog"""
    
    def __init__(self, parent, network, results=None):
        super().__init__(parent)
        self.network = network
        self.results = results
        self.result = None
        
        self.title("CAD Export")
        self.geometry("600x700")
        self.resizable(False, False)
        
        # Modal dialog
        self.transient(parent)
        self.grab_set()
        
        self.settings = CADExportSettings()
        self._create_widgets()
        
        # Merkeze al
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Genel ayarlar
        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="Genel")
        self._create_general_tab(general_frame)
        
        # Layer ayarları
        layer_frame = ttk.Frame(notebook, padding=10)
        notebook.add(layer_frame, text="Layer'lar")
        self._create_layer_tab(layer_frame)
        
        # Title block
        title_frame = ttk.Frame(notebook, padding=10)
        notebook.add(title_frame, text="Title Block")
        self._create_title_tab(title_frame)
        
        # Butonlar
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="DXF Export", 
                  command=self._export_dxf).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="PDF Export", 
                  command=self._export_pdf).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="İptal", 
                  command=self.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _create_general_tab(self, parent):
        """Genel ayarlar sekmesi"""
        # Ölçek
        row = 0
        ttk.Label(parent, text="Ölçek (1:):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.scale_var = tk.StringVar(value="100")
        ttk.Entry(parent, textvariable=self.scale_var, width=15).grid(row=row, column=1, sticky=tk.W)
        
        # Metin yüksekliği
        row += 1
        ttk.Label(parent, text="Metin Yüksekliği (m):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.text_height_var = tk.StringVar(value="0.5")
        ttk.Entry(parent, textvariable=self.text_height_var, width=15).grid(row=row, column=1, sticky=tk.W)
        
        # Seçenekler
        row += 1
        self.include_labels_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Etiketleri dahil et", 
                       variable=self.include_labels_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        row += 1
        self.include_dimensions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Boyutları dahil et", 
                       variable=self.include_dimensions_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        row += 1
        self.include_title_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Title block dahil et", 
                       variable=self.include_title_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # PDF sayfa boyutu
        row += 1
        ttk.Label(parent, text="PDF Sayfa Boyutu:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.page_size_var = tk.StringVar(value="A3")
        size_combo = ttk.Combobox(parent, textvariable=self.page_size_var, 
                                 values=["A4", "A3", "A2", "A1"], width=12, state='readonly')
        size_combo.grid(row=row, column=1, sticky=tk.W)
    
    def _create_layer_tab(self, parent):
        """Layer ayarları sekmesi"""
        layers = [
            ("Borular:", "layer_pipes", "PIPES"),
            ("Node'lar:", "layer_nodes", "NODES"),
            ("Sprinkler'lar:", "layer_sprinklers", "SPRINKLERS"),
            ("Metinler:", "layer_text", "TEXT"),
            ("Boyutlar:", "layer_dimensions", "DIMENSIONS")
        ]
        
        self.layer_vars = {}
        
        for row, (label, attr, default) in enumerate(layers):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
            var = tk.StringVar(value=default)
            self.layer_vars[attr] = var
            ttk.Entry(parent, textvariable=var, width=20).grid(row=row, column=1, sticky=tk.W, padx=5)
    
    def _create_title_tab(self, parent):
        """Title block sekmesi"""
        fields = [
            ("Proje Adı:", "project_name", "Yangın Söndürme Sistemi"),
            ("Proje No:", "project_number", ""),
            ("Çizen:", "drawn_by", ""),
            ("Kontrol Eden:", "checked_by", ""),
            ("Firma:", "company", "")
        ]
        
        self.title_vars = {}
        
        for row, (label, attr, default) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
            var = tk.StringVar(value=default)
            self.title_vars[attr] = var
            ttk.Entry(parent, textvariable=var, width=40).grid(row=row, column=1, sticky=tk.W, padx=5)
    
    def _get_settings(self) -> CADExportSettings:
        """Ayarları topla"""
        settings = CADExportSettings()
        
        # Genel ayarlar
        try:
            settings.scale = float(self.scale_var.get())
            settings.text_height = float(self.text_height_var.get())
        except ValueError:
            pass
        
        settings.include_labels = self.include_labels_var.get()
        settings.include_dimensions = self.include_dimensions_var.get()
        settings.include_title_block = self.include_title_var.get()
        
        # Layer'lar
        for attr, var in self.layer_vars.items():
            setattr(settings, attr, var.get())
        
        # Title block
        for attr, var in self.title_vars.items():
            setattr(settings, attr, var.get())
        
        return settings
    
    def _export_dxf(self):
        """DXF export"""
        if not HAS_EZDXF:
            messagebox.showerror("Hata", "ezdxf kütüphanesi yüklü değil!\n\n"
                               "Kurulum için: pip install ezdxf")
            return
        
        # Dosya seç
        filepath = filedialog.asksaveasfilename(
            defaultextension=".dxf",
            filetypes=[("DXF Files", "*.dxf"), ("All Files", "*.*")]
        )
        
        if not filepath:
            return
        
        # Ayarları al
        settings = self._get_settings()
        
        # Export
        try:
            exporter = DXFExporter(self.network, settings)
            success = exporter.export(filepath)
            
            if success:
                messagebox.showinfo("Başarılı", f"DXF dosyası oluşturuldu:\n{filepath}")
                self.result = filepath
            else:
                messagebox.showerror("Hata", "DXF export başarısız!")
                
        except Exception as e:
            messagebox.showerror("Hata", f"DXF export hatası:\n{str(e)}")
    
    def _export_pdf(self):
        """PDF export"""
        if not HAS_REPORTLAB:
            messagebox.showerror("Hata", "reportlab kütüphanesi yüklü değil!\n\n"
                               "Kurulum için: pip install reportlab")
            return
        
        # Dosya seç
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        
        if not filepath:
            return
        
        # Ayarları al
        settings = self._get_settings()
        page_size = self.page_size_var.get()
        
        # Export
        try:
            exporter = PDFExporter(self.network, settings, self.results)
            success = exporter.export(filepath, page_size)
            
            if success:
                messagebox.showinfo("Başarılı", f"PDF dosyası oluşturuldu:\n{filepath}")
                self.result = filepath
            else:
                messagebox.showerror("Hata", "PDF export başarısız!")
                
        except Exception as e:
            messagebox.showerror("Hata", f"PDF export hatası:\n{str(e)}")


def show_cad_export_dialog(parent, network, results=None):
    """CAD export dialog göster"""
    dialog = CADExportDialog(parent, network, results)
    parent.wait_window(dialog)
    return dialog.result
