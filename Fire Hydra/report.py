"""
FireHydra - Raporlama Modülü
============================

Bu modül, hidrolik hesaplama sonuçlarını PDF ve Excel
formatında raporlamayı sağlar.

Rapor İçeriği:
- Kapak sayfası (Proje adı, tarih, standart)
- Yoğunluk/Alan grafiği
- Düğüm tablosu
- Boru tablosu
- Pompa analizi
- Su deposu hesabı
"""

import os
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass

# PDF için reportlab (opsiyonel)
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Excel için openpyxl (opsiyonel)
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, Reference, LineChart
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from models import PipeNetwork
from solver import SolverResult
from enum import Enum


class ReportTemplate(Enum):
    """Rapor şablonları"""
    NFPA_STANDARD = "nfpa_standard"  # NFPA 13 standart format
    TSEN_STANDARD = "tsen_standard"  # TS EN 12845 format
    DETAILED = "detailed"  # Detaylı teknik rapor
    SUMMARY = "summary"  # Özet rapor
    CONTRACTOR = "contractor"  # Yüklenici raporu


@dataclass
class ReportSettings:
    """Rapor ayarları"""
    project_name: str = "FireHydra Projesi"
    project_number: str = ""
    client_name: str = ""
    engineer_name: str = ""
    standard: str = "NFPA 13 / TS EN 12845"
    date: str = ""
    notes: str = ""
    template: ReportTemplate = ReportTemplate.NFPA_STANDARD
    include_charts: bool = True
    include_calculation_steps: bool = True
    include_warnings: bool = True
    company_logo_path: str = ""
    
    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().strftime("%d.%m.%Y")


class ReportGenerator:
    """
    Rapor Üretici Sınıfı
    
    PDF ve Excel formatında hidrolik hesap raporları üretir.
    """
    
    def __init__(self, network: PipeNetwork, result: SolverResult, 
                 settings: Optional[ReportSettings] = None):
        self.network = network
        self.result = result
        self.settings = settings or ReportSettings()
    
    def generate_pdf(self, filepath: str) -> bool:
        """
        PDF raporu oluştur
        
        Args:
            filepath: PDF dosya yolu
            
        Returns:
            Başarılı ise True
        """
        if not HAS_REPORTLAB:
            print("HATA: reportlab kütüphanesi yüklü değil. 'pip install reportlab' ile yükleyin.")
            return False
        
        try:
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=20*mm,
                leftMargin=20*mm,
                topMargin=20*mm,
                bottomMargin=20*mm
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            # Başlık stili
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1  # Center
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=20,
                alignment=1
            )
            
            # Kapak
            story.append(Spacer(1, 50*mm))
            story.append(Paragraph("YANGIN SÖNDÜRME SİSTEMİ", title_style))
            story.append(Paragraph("HİDROLİK HESAP RAPORU", title_style))
            story.append(Spacer(1, 20*mm))
            story.append(Paragraph(self.settings.project_name, subtitle_style))
            story.append(Spacer(1, 10*mm))
            
            # Proje bilgileri tablosu
            cover_data = [
                ["Proje No:", self.settings.project_number or "-"],
                ["Müşteri:", self.settings.client_name or "-"],
                ["Mühendis:", self.settings.engineer_name or "-"],
                ["Standart:", self.settings.standard],
                ["Tarih:", self.settings.date],
            ]
            
            cover_table = Table(cover_data, colWidths=[60*mm, 80*mm])
            cover_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(cover_table)
            
            # Sayfa sonu
            story.append(Spacer(1, 50*mm))
            
            # Sistem Özeti
            story.append(Paragraph("1. SİSTEM ÖZETİ", styles['Heading1']))
            story.append(Spacer(1, 5*mm))
            
            summary_data = [
                ["Parametre", "Değer", "Birim"],
                ["Toplam Sistem Debisi", f"{self.result.total_flow:.1f}", "L/dk"],
                ["Toplam Sistem Basıncı", f"{self.result.total_pressure:.2f}", "Bar"],
                ["Sprinkler Sayısı", f"{self.result.sprinkler_count}", "adet"],
                ["Tasarım Yoğunluğu", f"{self.result.density_mmpm:.2f}", "mm/dk"],
                ["Tasarım Alanı", f"{self.result.operating_area_m2:.1f}", "m²"],
                ["Maksimum Hız", f"{self.result.max_velocity:.2f}", "m/s"],
            ]
            
            summary_table = Table(summary_data, colWidths=[70*mm, 40*mm, 30*mm])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 10*mm))
            
            # Düğüm Tablosu
            story.append(Paragraph("2. DÜĞÜM TABLOSU", styles['Heading1']))
            story.append(Spacer(1, 5*mm))
            
            node_data = [["No", "Tip", "Kot (m)", "K-Faktör", "Basınç (bar)", "Debi (L/dk)"]]
            
            for node in self.network.nodes.values():
                k_factor = f"{node.k_factor:.0f}" if node.is_sprinkler() else "-"
                pressure = f"{node.pressure:.3f}" if node.pressure else "-"
                flow = f"{node.total_flow:.1f}" if node.total_flow else "-"
                
                node_data.append([
                    node.id,
                    node.node_type.value,
                    f"{node.get_elevation():.2f}",
                    k_factor,
                    pressure,
                    flow
                ])
            
            node_table = Table(node_data, colWidths=[25*mm, 25*mm, 20*mm, 20*mm, 25*mm, 25*mm])
            node_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(node_table)
            story.append(Spacer(1, 10*mm))
            
            # Boru Tablosu
            story.append(Paragraph("3. BORU TABLOSU", styles['Heading1']))
            story.append(Spacer(1, 5*mm))
            
            pipe_data = [["No", "Başlangıç", "Bitiş", "Çap (mm)", "Uzunluk (m)", "Eq.L (m)", "ΔP (bar)", "Hız (m/s)"]]
            
            for pipe in self.network.pipes.values():
                friction = f"{pipe.friction_loss:.4f}" if pipe.friction_loss else "-"
                velocity = f"{pipe.velocity:.2f}" if pipe.velocity else "-"
                
                pipe_data.append([
                    pipe.id,
                    pipe.start_node_id,
                    pipe.end_node_id,
                    f"{pipe.internal_diameter:.1f}",
                    f"{pipe.length:.2f}",
                    f"{pipe.get_total_equivalent_length():.2f}",
                    friction,
                    velocity
                ])
            
            pipe_table = Table(pipe_data, colWidths=[20*mm, 22*mm, 22*mm, 18*mm, 20*mm, 18*mm, 20*mm, 20*mm])
            pipe_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(pipe_table)
            story.append(Spacer(1, 10*mm))
            
            # Hesaplama Adımları
            if self.result.calculation_steps:
                story.append(Paragraph("4. HESAPLAMA ADIMLARI", styles['Heading1']))
                story.append(Spacer(1, 5*mm))
                
                step_data = [["#", "Düğüm", "P_in (bar)", "P_out (bar)", "ΔP_f (bar)", "ΔP_z (bar)", "Q (L/dk)"]]
                
                for step in self.result.calculation_steps:
                    step_data.append([
                        str(step.step_number),
                        step.node_id,
                        f"{step.pressure_in:.3f}",
                        f"{step.pressure_out:.3f}",
                        f"{step.friction_loss:.4f}",
                        f"{step.elevation_loss:.4f}",
                        f"{step.flow:.1f}"
                    ])
                
                step_table = Table(step_data, colWidths=[15*mm, 25*mm, 22*mm, 22*mm, 22*mm, 22*mm, 22*mm])
                step_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(step_table)
            
            # Uyarılar
            if self.result.warnings:
                story.append(Spacer(1, 10*mm))
                story.append(Paragraph("5. UYARILAR", styles['Heading1']))
                story.append(Spacer(1, 5*mm))
                
                for warning in self.result.warnings:
                    story.append(Paragraph(f"• {warning}", styles['Normal']))
            
            # Notlar
            if self.settings.notes:
                story.append(Spacer(1, 10*mm))
                story.append(Paragraph("NOTLAR", styles['Heading1']))
                story.append(Spacer(1, 5*mm))
                story.append(Paragraph(self.settings.notes, styles['Normal']))
            
            # Footer
            story.append(Spacer(1, 20*mm))
            story.append(Paragraph(
                f"Bu rapor FireHydra v1.0 tarafından {self.settings.date} tarihinde oluşturulmuştur.",
                ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1)
            ))
            
            # PDF oluştur
            doc.build(story)
            
            return True
            
        except Exception as e:
            print(f"PDF oluşturma hatası: {e}")
            return False
    
    def generate_excel(self, filepath: str) -> bool:
        """
        Excel raporu oluştur
        
        Args:
            filepath: Excel dosya yolu
            
        Returns:
            Başarılı ise True
        """
        if not HAS_OPENPYXL:
            print("HATA: openpyxl kütüphanesi yüklü değil. 'pip install openpyxl' ile yükleyin.")
            return False
        
        try:
            wb = Workbook()
            
            # Stiller
            header_font = Font(bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
            subheader_font = Font(bold=True, size=10)
            subheader_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            center_align = Alignment(horizontal='center', vertical='center')
            
            # ========== KAPAK SAYFASI ==========
            ws_cover = wb.active
            ws_cover.title = "Kapak"
            
            # Logo (varsa)
            if self.settings.company_logo_path and os.path.exists(self.settings.company_logo_path):
                try:
                    from openpyxl.drawing.image import Image as ExcelImage
                    img = ExcelImage(self.settings.company_logo_path)
                    img.width = 150
                    img.height = 50
                    ws_cover.add_image(img, 'A1')
                except:
                    pass
            
            # Başlık
            ws_cover['A5'] = "YANGIN SÖNDÜRME SİSTEMİ"
            ws_cover['A5'].font = Font(bold=True, size=18, color="003366")
            ws_cover['A5'].alignment = center_align
            ws_cover.merge_cells('A5:E5')
            
            ws_cover['A6'] = "HİDROLİK HESAP RAPORU"
            ws_cover['A6'].font = Font(bold=True, size=16, color="003366")
            ws_cover['A6'].alignment = center_align
            ws_cover.merge_cells('A6:E6')
            
            ws_cover['A8'] = self.settings.project_name
            ws_cover['A8'].font = Font(bold=True, size=14)
            ws_cover['A8'].alignment = center_align
            ws_cover.merge_cells('A8:E8')
            
            # Proje bilgileri tablosu
            row = 11
            project_info = [
                ("Proje No:", self.settings.project_number or "-"),
                ("Müşteri:", self.settings.client_name or "-"),
                ("Mühendis:", self.settings.engineer_name or "-"),
                ("Standart:", self.settings.standard),
                ("Tarih:", self.settings.date),
            ]
            
            for label, value in project_info:
                ws_cover[f'B{row}'] = label
                ws_cover[f'B{row}'].font = Font(bold=True)
                ws_cover[f'C{row}'] = value
                for col in ['B', 'C']:
                    ws_cover[f'{col}{row}'].border = border
                row += 1
            
            # Sütun genişlikleri
            ws_cover.column_dimensions['A'].width = 5
            ws_cover.column_dimensions['B'].width = 20
            ws_cover.column_dimensions['C'].width = 30
            ws_cover.column_dimensions['D'].width = 15
            ws_cover.column_dimensions['E'].width = 5
            
            # ========== ÖZET SAYFASI ==========
            ws_summary = wb.create_sheet("Sistem Özeti")
            
            # Başlık
            ws_summary['A1'] = "SİSTEM ÖZETİ VE TASARIM PARAMETRELERİ"
            ws_summary['A1'].font = Font(bold=True, size=14, color="003366")
            ws_summary.merge_cells('A1:D1')
            
            # Hesaplama sonuçları tablosu
            row = 3
            ws_summary[f'A{row}'] = "Parametre"
            ws_summary[f'B{row}'] = "Değer"
            ws_summary[f'C{row}'] = "Birim"
            ws_summary[f'D{row}'] = "Durum"
            
            for col in ['A', 'B', 'C', 'D']:
                cell = ws_summary[f'{col}{row}']
                cell.font = header_font
                cell.fill = header_fill
                cell.border = border
                cell.alignment = center_align
            
            row += 1
            results = [
                ("Toplam Sistem Debisi", self.result.total_flow, "L/dk", "✓"),
                ("Toplam Sistem Basıncı", self.result.total_pressure, "Bar", "✓"),
                ("Sprinkler Sayısı", self.result.sprinkler_count, "adet", "✓"),
                ("Tasarım Yoğunluğu", self.result.density_mmpm, "mm/dk", "✓"),
                ("Tasarım Alanı", self.result.operating_area_m2, "m²", "✓"),
                ("Maksimum Hız", self.result.max_velocity, "m/s", 
                 "✓" if self.result.max_velocity <= 6.0 else "⚠ Yüksek"),
            ]
            
            for param, value, unit, status in results:
                ws_summary[f'A{row}'] = param
                ws_summary[f'B{row}'] = f"{value:.2f}" if isinstance(value, float) else value
                ws_summary[f'C{row}'] = unit
                ws_summary[f'D{row}'] = status
                
                for col in ['A', 'B', 'C', 'D']:
                    ws_summary[f'{col}{row}'].border = border
                
                # Durum sütunu renklendirme
                if "⚠" in status:
                    ws_summary[f'D{row}'].fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
                else:
                    ws_summary[f'D{row}'].fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
                
                row += 1
            
            # Uyarılar
            if self.result.warnings and self.settings.include_warnings:
                row += 2
                ws_summary[f'A{row}'] = "UYARILAR"
                ws_summary[f'A{row}'].font = Font(bold=True, size=12, color="FF0000")
                row += 1
                
                for warning in self.result.warnings:
                    ws_summary[f'A{row}'] = f"⚠ {warning}"
                    ws_summary[f'A{row}'].font = Font(color="FF0000")
                    ws_summary.merge_cells(f'A{row}:D{row}')
                    row += 1
            
            # Sütun genişlikleri
            ws_summary.column_dimensions['A'].width = 30
            ws_summary.column_dimensions['B'].width = 15
            ws_summary.column_dimensions['C'].width = 12
            ws_summary.column_dimensions['D'].width = 15
            
            # ========== DÜĞÜM SAYFASI ==========
            ws_nodes = wb.create_sheet("Düğümler")
            
            ws_nodes['A1'] = "DÜĞÜM TABLOSU"
            ws_nodes['A1'].font = Font(bold=True, size=14, color="003366")
            ws_nodes.merge_cells('A1:H1')
            
            node_headers = ["No", "Tip", "X (mm)", "Y (mm)", "Kot (m)", "K-Faktör", "Basınç (bar)", "Debi (L/dk)"]
            for col, header in enumerate(node_headers, 1):
                cell = ws_nodes.cell(row=3, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = border
                cell.alignment = center_align
            
            row = 4
            for node in self.network.nodes.values():
                ws_nodes.cell(row=row, column=1, value=node.id).border = border
                ws_nodes.cell(row=row, column=2, value=node.node_type.value).border = border
                ws_nodes.cell(row=row, column=3, value=node.coordinates.x).border = border
                ws_nodes.cell(row=row, column=4, value=node.coordinates.y).border = border
                
                elevation_cell = ws_nodes.cell(row=row, column=5, value=node.get_elevation())
                elevation_cell.border = border
                elevation_cell.number_format = '0.00'
                
                k_cell = ws_nodes.cell(row=row, column=6, value=node.k_factor if node.is_sprinkler() else "")
                k_cell.border = border
                k_cell.number_format = '0'
                
                pressure_cell = ws_nodes.cell(row=row, column=7, value=node.pressure if node.pressure else "")
                pressure_cell.border = border
                pressure_cell.number_format = '0.000'
                
                # Basınç renklendirme
                if node.pressure:
                    if node.pressure < 0.5:
                        pressure_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                    elif node.pressure > 12:
                        pressure_cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                
                flow_cell = ws_nodes.cell(row=row, column=8, value=node.total_flow if node.total_flow else "")
                flow_cell.border = border
                flow_cell.number_format = '0.0'
                
                row += 1
            
            # Sütun genişlikleri
            for col in range(1, 9):
                ws_nodes.column_dimensions[get_column_letter(col)].width = 15
            
            # ========== BORU SAYFASI ==========
            ws_pipes = wb.create_sheet("Borular")
            
            ws_pipes['A1'] = "BORU TABLOSU"
            ws_pipes['A1'].font = Font(bold=True, size=14, color="003366")
            ws_pipes.merge_cells('A1:J1')
            
            pipe_headers = ["No", "Başlangıç", "Bitiş", "Çap (mm)", "Uzunluk (m)", "Eq.L (m)", 
                          "C Faktörü", "Debi (L/dk)", "Hız (m/s)", "ΔP (bar)"]
            for col, header in enumerate(pipe_headers, 1):
                cell = ws_pipes.cell(row=3, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = border
                cell.alignment = center_align
            
            row = 4
            for pipe in self.network.pipes.values():
                ws_pipes.cell(row=row, column=1, value=pipe.id).border = border
                ws_pipes.cell(row=row, column=2, value=pipe.start_node_id).border = border
                ws_pipes.cell(row=row, column=3, value=pipe.end_node_id).border = border
                
                diam_cell = ws_pipes.cell(row=row, column=4, value=pipe.internal_diameter)
                diam_cell.border = border
                diam_cell.number_format = '0.0'
                
                length_cell = ws_pipes.cell(row=row, column=5, value=pipe.length)
                length_cell.border = border
                length_cell.number_format = '0.00'
                
                eq_cell = ws_pipes.cell(row=row, column=6, value=pipe.get_total_equivalent_length())
                eq_cell.border = border
                eq_cell.number_format = '0.00'
                
                ws_pipes.cell(row=row, column=7, value=pipe.c_factor).border = border
                
                flow_cell = ws_pipes.cell(row=row, column=8, value=pipe.flow if pipe.flow else "")
                flow_cell.border = border
                flow_cell.number_format = '0.0'
                
                velocity_cell = ws_pipes.cell(row=row, column=9, value=pipe.velocity if pipe.velocity else "")
                velocity_cell.border = border
                velocity_cell.number_format = '0.00'
                
                # Hız renklendirme
                if pipe.velocity:
                    if pipe.velocity > 10:
                        velocity_cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                        velocity_cell.font = Font(color="FFFFFF", bold=True)
                    elif pipe.velocity > 6:
                        velocity_cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                
                friction_cell = ws_pipes.cell(row=row, column=10, value=pipe.friction_loss if pipe.friction_loss else "")
                friction_cell.border = border
                friction_cell.number_format = '0.0000'
                
                row += 1
            
            # Sütun genişlikleri
            for col in range(1, 11):
                ws_pipes.column_dimensions[get_column_letter(col)].width = 12
            
            # ========== HESAPLAMA ADIMLARI ==========
            if self.result.calculation_steps and self.settings.include_calculation_steps:
                ws_steps = wb.create_sheet("Hesaplama Adımları")
                
                ws_steps['A1'] = "HESAPLAMA ADIMLARI (NFPA 13 Metodu)"
                ws_steps['A1'].font = Font(bold=True, size=14, color="003366")
                ws_steps.merge_cells('A1:I1')
                
                step_headers = ["#", "Düğüm", "Tip", "P_in (bar)", "P_out (bar)", 
                              "ΔP_friction (bar)", "ΔP_elevation (bar)", "Debi (L/dk)", "Notlar"]
                for col, header in enumerate(step_headers, 1):
                    cell = ws_steps.cell(row=3, column=col, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.border = border
                    cell.alignment = center_align
                
                row = 4
                for step in self.result.calculation_steps:
                    ws_steps.cell(row=row, column=1, value=step.step_number).border = border
                    ws_steps.cell(row=row, column=2, value=step.node_id).border = border
                    ws_steps.cell(row=row, column=3, value=step.node_type).border = border
                    
                    for col_idx, val in enumerate([step.pressure_in, step.pressure_out, 
                                                   step.friction_loss, step.elevation_loss], 4):
                        cell = ws_steps.cell(row=row, column=col_idx, value=val)
                        cell.border = border
                        cell.number_format = '0.000'
                    
                    flow_cell = ws_steps.cell(row=row, column=8, value=step.flow)
                    flow_cell.border = border
                    flow_cell.number_format = '0.0'
                    
                    ws_steps.cell(row=row, column=9, value=step.notes).border = border
                    row += 1
                
                for col in range(1, 10):
                    ws_steps.column_dimensions[get_column_letter(col)].width = 15
            
            # ========== GRAFİKLER (Opsiyonel) ==========
            if self.settings.include_charts:
                ws_charts = wb.create_sheet("Grafikler")
                
                # Basınç-Düğüm grafiği
                if len(self.network.nodes) > 1:
                    chart = LineChart()
                    chart.title = "Düğüm Basınçları"
                    chart.y_axis.title = 'Basınç (bar)'
                    chart.x_axis.title = 'Düğüm No'
                    
                    # Veri hazırlama
                    row = 2
                    ws_charts.cell(row=row, column=1, value="Düğüm")
                    ws_charts.cell(row=row, column=2, value="Basınç (bar)")
                    
                    row = 3
                    for node in self.network.nodes.values():
                        if node.pressure:
                            ws_charts.cell(row=row, column=1, value=node.id)
                            ws_charts.cell(row=row, column=2, value=node.pressure)
                            row += 1
                    
                    if row > 3:
                        data = Reference(ws_charts, min_col=2, min_row=2, max_row=row-1)
                        cats = Reference(ws_charts, min_col=1, min_row=3, max_row=row-1)
                        chart.add_data(data, titles_from_data=True)
                        chart.set_categories(cats)
                        ws_charts.add_chart(chart, "D2")
            
            # Kaydet
            wb.save(filepath)
            
            return True
            
        except Exception as e:
            print(f"Excel oluşturma hatası: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate_text_report(self) -> str:
        """Metin formatında rapor oluştur"""
        lines = []
        
        lines.append("=" * 70)
        lines.append("YANGIN SÖNDÜRME SİSTEMİ - HİDROLİK HESAP RAPORU")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Proje: {self.settings.project_name}")
        lines.append(f"Tarih: {self.settings.date}")
        lines.append(f"Standart: {self.settings.standard}")
        lines.append("")
        
        lines.append("-" * 70)
        lines.append("SİSTEM SONUÇLARI")
        lines.append("-" * 70)
        lines.append(f"  Toplam Sistem Debisi: {self.result.total_flow:.1f} L/dk")
        lines.append(f"  Toplam Sistem Basıncı: {self.result.total_pressure:.2f} Bar")
        lines.append(f"  Sprinkler Sayısı: {self.result.sprinkler_count} adet")
        lines.append(f"  Tasarım Yoğunluğu: {self.result.density_mmpm:.2f} mm/dk")
        lines.append(f"  Tasarım Alanı: {self.result.operating_area_m2:.1f} m²")
        lines.append(f"  Maksimum Hız: {self.result.max_velocity:.2f} m/s")
        lines.append("")
        
        lines.append("-" * 70)
        lines.append("DÜĞÜM TABLOSU")
        lines.append("-" * 70)
        lines.append(f"{'No':<12} {'Tip':<12} {'Kot(m)':<8} {'K':<6} {'P(bar)':<10} {'Q(L/dk)':<10}")
        lines.append("-" * 70)
        
        for node in self.network.nodes.values():
            k = f"{node.k_factor:.0f}" if node.is_sprinkler() else "-"
            p = f"{node.pressure:.3f}" if node.pressure else "-"
            q = f"{node.total_flow:.1f}" if node.total_flow else "-"
            
            lines.append(f"{node.id:<12} {node.node_type.value:<12} {node.get_elevation():<8.2f} {k:<6} {p:<10} {q:<10}")
        
        lines.append("")
        lines.append("-" * 70)
        lines.append("BORU TABLOSU")
        lines.append("-" * 70)
        lines.append(f"{'No':<10} {'Çap(mm)':<10} {'Uzunluk':<10} {'Eq.L':<8} {'ΔP(bar)':<10} {'Hız(m/s)':<10}")
        lines.append("-" * 70)
        
        for pipe in self.network.pipes.values():
            dp = f"{pipe.friction_loss:.4f}" if pipe.friction_loss else "-"
            v = f"{pipe.velocity:.2f}" if pipe.velocity else "-"
            
            lines.append(f"{pipe.id:<10} {pipe.internal_diameter:<10.1f} {pipe.length:<10.2f} {pipe.get_total_equivalent_length():<8.2f} {dp:<10} {v:<10}")
        
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"Rapor FireHydra v1.0 tarafından oluşturuldu.")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# ==================== Test ====================
if __name__ == "__main__":
    from .models import Node, Pipe, NodeType, Coordinates
    
    print("FireHydra Raporlama Testi")
    print("=" * 50)
    
    # Test ağı
    network = PipeNetwork("Test Projesi")
    
    source = Node(id="SOURCE", node_type=NodeType.SOURCE, coordinates=Coordinates(0, 0, 0))
    network.add_node(source)
    
    spr1 = Node(id="SPR1", node_type=NodeType.SPRINKLER, coordinates=Coordinates(5000, 0, 3))
    spr1.pressure = 0.5
    spr1.total_flow = 56.5
    spr1.is_calculated = True
    network.add_node(spr1)
    
    pipe = Pipe(id="P1", start_node_id="SOURCE", end_node_id="SPR1", length=5.0)
    pipe.flow = 56.5
    pipe.velocity = 0.8
    pipe.friction_loss = 0.05
    network.add_pipe(pipe)
    
    # Sonuç
    from .solver import SolverResult, CalculationStep
    
    result = SolverResult(
        success=True,
        total_flow=56.5,
        total_pressure=0.6,
        sprinkler_count=1,
        density_mmpm=5.0,
        operating_area_m2=150,
        max_velocity=0.8
    )
    
    # Rapor ayarları
    settings = ReportSettings(
        project_name="Test Projesi",
        project_number="PRJ-001",
        client_name="Test Müşteri",
        engineer_name="Test Mühendis"
    )
    
    # Rapor oluştur
    generator = ReportGenerator(network, result, settings)
    
    # Metin raporu
    text_report = generator.generate_text_report()
    print(text_report)
    
    print("\nTest tamamlandı!")
