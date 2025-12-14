"""
FireHydra package initializer.

Allows running with `python -m Yangin_Sondurme_Hesaplama.main_app`.
"""
# FireHydra - Yangın Hidrolik Hesaplama ve Tasarım Yazılımı
# Version: 1.0
# Standartlar: NFPA 13, NFPA 20, TS EN 12845, BYKHY
"""
FireHydra - Fire Hydraulic Calculation and Design Software
===========================================================

Bu yazılım, yangın söndürme sistemlerinin hidrolik hesaplamalarını
yapan, 2D çizim tabanlı bir mühendislik uygulamasıdır.

Modüller:
- database: Veritabanı ve referans tablolar
- models: Node, Pipe ve Graph veri yapıları
- engine: Hidrolik hesaplama çekirdeği
- solver: Recursive back-calculation algoritması
- pump_tank: Pompa ve tank seçim modülü (NFPA 20)
- gui_canvas: 2D Canvas çizim arayüzü
- report: PDF/Excel raporlama
- main_app: Ana uygulama penceresi
"""

__version__ = "1.0.0"
__author__ = "FireHydra Team"
__license__ = "MIT"

from .models import Node, Pipe, PipeNetwork, NodeType, FittingCategory, Fitting, Coordinates
from .database import DatabaseManager, PipeType, FittingType, HazardClass
from .engine import HydraulicEngine
from .solver import HydraulicSolver, SolverResult, CalculationStep
from .pump_tank import FirePump, PumpAndTankModule, PumpType
from .report import ReportGenerator, ReportSettings
from .main_app import FireHydraApp, main
