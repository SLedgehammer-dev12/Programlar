#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FireHydra - Yangın Hidrolik Hesaplama Yazılımı
==============================================

Bu script, FireHydra uygulamasını başlatır.

Kullanım:
    python run.py

Gereksinimler:
    - Python 3.8+
    - tkinter (genellikle Python ile birlikte gelir)
    - reportlab (PDF raporlama için - opsiyonel)
    - openpyxl (Excel raporlama için - opsiyonel)

Standartlar:
    - NFPA 13: Sprinkler Sistemleri
    - NFPA 20: Yangın Pompaları
    - TS EN 12845: Otomatik Sprinkler Sistemleri
    - BYKHY: Binaların Yangından Korunması Hakkında Yönetmelik
"""

import sys
import os

# Modül yolunu ayarla
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def check_dependencies():
    """Bağımlılıkları kontrol et"""
    missing = []
    optional_missing = []
    
    # Zorunlu
    try:
        import tkinter
    except ImportError:
        missing.append("tkinter")
    
    # Opsiyonel
    try:
        import reportlab
    except ImportError:
        optional_missing.append("reportlab (PDF raporlama için)")
    
    try:
        import openpyxl
    except ImportError:
        optional_missing.append("openpyxl (Excel raporlama için)")
    
    try:
        import ezdxf
    except ImportError:
        optional_missing.append("ezdxf (DXF/DWG import için)")
    
    if missing:
        print("HATA: Aşağıdaki zorunlu paketler eksik:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nKurulum için: pip install <paket_adı>")
        return False
    
    if optional_missing:
        print("UYARI: Aşağıdaki opsiyonel paketler eksik:")
        for pkg in optional_missing:
            print(f"  - {pkg}")
        print("Devam ediliyor...\n")
    
    return True


def main():
    """Ana fonksiyon"""
    print("=" * 50)
    print("FireHydra - Yangın Hidrolik Hesaplama v1.0")
    print("=" * 50)
    print()
    
    if not check_dependencies():
        sys.exit(1)
    
    print("Uygulama başlatılıyor...")
    
    try:
        # Import and run
        import main_app
        main_app.main()
    except Exception as e:
        print(f"HATA: Uygulama başlatılamadı:\n{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
