#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FireHydra Updater Module
========================

GitHub'dan güncelleme kontrolü ve uygulama modülü.
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple, Dict
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# GitHub repository bilgileri
GITHUB_OWNER = "SLedgehammer-dev12"
GITHUB_REPO = "Programlar"
GITHUB_BRANCH = "Fire-Hydra"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
GITHUB_DOWNLOAD_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

# Lokal versiyon dosyası
VERSION_FILE = "version.json"
CURRENT_VERSION = "1.0.0"


def get_local_version() -> Dict:
    """Lokal versiyon bilgisini al"""
    version_path = os.path.join(os.path.dirname(__file__), VERSION_FILE)
    
    if os.path.exists(version_path):
        try:
            with open(version_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    return {
        "version": CURRENT_VERSION,
        "commit_sha": None,
        "last_check": None
    }


def save_local_version(version_info: Dict):
    """Lokal versiyon bilgisini kaydet"""
    version_path = os.path.join(os.path.dirname(__file__), VERSION_FILE)
    
    try:
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(version_info, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Versiyon kaydetme hatası: {e}")


def check_for_updates() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    GitHub'dan güncellemeleri kontrol et.
    
    Returns:
        Tuple[bool, str, str]: (güncelleme_var_mı, yeni_commit_sha, hata_mesajı)
    """
    try:
        # GitHub API'den son commit'i al
        request = Request(GITHUB_API_URL)
        request.add_header('Accept', 'application/vnd.github.v3+json')
        request.add_header('User-Agent', 'FireHydra-Updater')
        
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        remote_sha = data.get('sha', '')[:7]  # İlk 7 karakter
        remote_message = data.get('commit', {}).get('message', 'Güncelleme mevcut')
        
        # Lokal versiyon ile karşılaştır
        local_version = get_local_version()
        local_sha = local_version.get('commit_sha', '')
        
        if not local_sha or local_sha != remote_sha:
            return True, remote_sha, remote_message
        
        return False, remote_sha, None
        
    except HTTPError as e:
        return False, None, f"HTTP Hatası: {e.code}"
    except URLError as e:
        return False, None, f"Bağlantı hatası: {e.reason}"
    except Exception as e:
        return False, None, f"Hata: {str(e)}"


def download_update(progress_callback=None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Güncellemeyi indir.
    
    Args:
        progress_callback: İlerleme callback fonksiyonu (yüzde, mesaj)
    
    Returns:
        Tuple[bool, str, str]: (başarılı_mı, zip_dosya_yolu, hata_mesajı)
    """
    try:
        if progress_callback:
            progress_callback(0, "İndirme başlatılıyor...")
        
        # Temp dosya oluştur
        temp_dir = tempfile.gettempdir()
        zip_path = os.path.join(temp_dir, f"firehydra_update_{GITHUB_BRANCH}.zip")
        
        # İndir
        request = Request(GITHUB_DOWNLOAD_URL)
        request.add_header('User-Agent', 'FireHydra-Updater')
        
        with urlopen(request, timeout=60) as response:
            total_size = response.headers.get('Content-Length')
            total_size = int(total_size) if total_size else 0
            
            downloaded = 0
            chunk_size = 8192
            
            with open(zip_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        progress_callback(percent, f"İndiriliyor... {downloaded // 1024} KB")
        
        if progress_callback:
            progress_callback(100, "İndirme tamamlandı!")
        
        return True, zip_path, None
        
    except Exception as e:
        return False, None, f"İndirme hatası: {str(e)}"


def apply_update(zip_path: str, progress_callback=None) -> Tuple[bool, Optional[str]]:
    """
    Güncellemeyi uygula.
    
    Args:
        zip_path: İndirilen zip dosyasının yolu
        progress_callback: İlerleme callback fonksiyonu
    
    Returns:
        Tuple[bool, str]: (başarılı_mı, hata_mesajı)
    """
    try:
        if progress_callback:
            progress_callback(0, "Güncelleme uygulanıyor...")
        
        # Hedef dizin
        target_dir = os.path.dirname(__file__)
        
        # Backup oluştur
        backup_dir = os.path.join(tempfile.gettempdir(), "firehydra_backup")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        
        # Mevcut .py dosyalarını yedekle
        py_files = [f for f in os.listdir(target_dir) if f.endswith('.py')]
        os.makedirs(backup_dir, exist_ok=True)
        
        for py_file in py_files:
            src = os.path.join(target_dir, py_file)
            dst = os.path.join(backup_dir, py_file)
            shutil.copy2(src, dst)
        
        if progress_callback:
            progress_callback(30, "Yedekleme tamamlandı...")
        
        # Zip'i aç
        temp_extract = os.path.join(tempfile.gettempdir(), "firehydra_extract")
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
        
        if progress_callback:
            progress_callback(50, "Dosyalar açıldı...")
        
        # İçerideki Fire Hydra klasörünü bul
        extracted_dirs = os.listdir(temp_extract)
        if not extracted_dirs:
            return False, "Arşiv boş!"
        
        # GitHub archive formatı: Programlar-Fire-Hydra/Fire Hydra/
        source_dir = os.path.join(temp_extract, extracted_dirs[0], "Fire Hydra")
        
        if not os.path.exists(source_dir):
            # Alternatif yol dene
            source_dir = os.path.join(temp_extract, extracted_dirs[0])
        
        if progress_callback:
            progress_callback(70, "Dosyalar kopyalanıyor...")
        
        # .py dosyalarını kopyala
        updated_files = 0
        for item in os.listdir(source_dir):
            if item.endswith('.py'):
                src = os.path.join(source_dir, item)
                dst = os.path.join(target_dir, item)
                shutil.copy2(src, dst)
                updated_files += 1
        
        if progress_callback:
            progress_callback(90, "Versiyon güncelleniyor...")
        
        # Yeni commit SHA'yı kaydet
        has_update, new_sha, _ = check_for_updates()
        if new_sha:
            version_info = get_local_version()
            version_info['commit_sha'] = new_sha
            version_info['version'] = CURRENT_VERSION
            save_local_version(version_info)
        
        # Temizlik
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
        if progress_callback:
            progress_callback(100, "Güncelleme tamamlandı!")
        
        return True, None
        
    except Exception as e:
        return False, f"Güncelleme hatası: {str(e)}"


class UpdateDialog(tk.Toplevel):
    """Güncelleme dialog penceresi"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Güncelleme Kontrolü")
        self.geometry("450x250")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Ortala
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 250) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_widgets()
        self._check_updates()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        ttk.Label(main_frame, text="🔄 FireHydra Güncelleme", 
                  font=("Arial", 14, "bold")).pack(pady=(0, 15))
        
        # Durum etiketi
        self.status_var = tk.StringVar(value="Güncellemeler kontrol ediliyor...")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var,
                                       wraplength=400)
        self.status_label.pack(pady=10)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=400)
        self.progress.pack(pady=10)
        self.progress.start(10)
        
        # Detay etiketi
        self.detail_var = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.detail_var, 
                  foreground="gray").pack(pady=5)
        
        # Butonlar
        self.btn_frame = ttk.Frame(main_frame)
        self.btn_frame.pack(pady=15)
        
        self.update_btn = ttk.Button(self.btn_frame, text="Güncelle", 
                                      command=self._do_update, state=tk.DISABLED)
        self.update_btn.pack(side=tk.LEFT, padx=5)
        
        self.close_btn = ttk.Button(self.btn_frame, text="Kapat", 
                                     command=self.destroy)
        self.close_btn.pack(side=tk.LEFT, padx=5)
    
    def _check_updates(self):
        """Arka planda güncelleme kontrolü"""
        def check_thread():
            has_update, sha, message = check_for_updates()
            self.after(0, lambda: self._on_check_complete(has_update, sha, message))
        
        thread = threading.Thread(target=check_thread, daemon=True)
        thread.start()
    
    def _on_check_complete(self, has_update: bool, sha: Optional[str], message: Optional[str]):
        """Kontrol tamamlandığında"""
        self.progress.stop()
        self.progress.config(mode='determinate', value=100)
        
        if message and not has_update and sha is None:
            # Hata durumu
            self.status_var.set(f"❌ Kontrol başarısız: {message}")
            self.detail_var.set("İnternet bağlantınızı kontrol edin.")
        elif has_update:
            self.status_var.set("✅ Yeni güncelleme mevcut!")
            self.detail_var.set(f"Commit: {sha}\n{message[:100] if message else ''}")
            self.update_btn.config(state=tk.NORMAL)
        else:
            self.status_var.set("✓ Program güncel!")
            self.detail_var.set(f"Mevcut sürüm: {sha or CURRENT_VERSION}")
    
    def _do_update(self):
        """Güncellemeyi başlat"""
        self.update_btn.config(state=tk.DISABLED)
        self.close_btn.config(state=tk.DISABLED)
        self.progress.config(mode='determinate', value=0)
        self.status_var.set("Güncelleme indiriliyor...")
        
        def update_thread():
            # İndir
            success, zip_path, error = download_update(
                lambda p, m: self.after(0, lambda: self._update_progress(p, m))
            )
            
            if not success:
                self.after(0, lambda: self._on_update_error(error))
                return
            
            # Uygula
            success, error = apply_update(
                zip_path,
                lambda p, m: self.after(0, lambda: self._update_progress(p, m))
            )
            
            if success:
                self.after(0, self._on_update_complete)
            else:
                self.after(0, lambda: self._on_update_error(error))
        
        thread = threading.Thread(target=update_thread, daemon=True)
        thread.start()
    
    def _update_progress(self, percent: int, message: str):
        """İlerlemeyi güncelle"""
        self.progress['value'] = percent
        self.detail_var.set(message)
    
    def _on_update_complete(self):
        """Güncelleme tamamlandı"""
        self.status_var.set("✅ Güncelleme tamamlandı!")
        self.detail_var.set("Değişikliklerin geçerli olması için programı yeniden başlatın.")
        self.progress['value'] = 100
        self.close_btn.config(state=tk.NORMAL)
        
        # Yeniden başlatma seçeneği
        if messagebox.askyesno("Güncelleme Tamamlandı", 
                               "Güncelleme başarıyla tamamlandı!\n\n"
                               "Değişikliklerin geçerli olması için programı yeniden başlatmanız gerekiyor.\n\n"
                               "Şimdi yeniden başlatılsın mı?"):
            self._restart_app()
    
    def _on_update_error(self, error: str):
        """Güncelleme hatası"""
        self.status_var.set(f"❌ Güncelleme hatası!")
        self.detail_var.set(error)
        self.close_btn.config(state=tk.NORMAL)
    
    def _restart_app(self):
        """Uygulamayı yeniden başlat"""
        python = sys.executable
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "run.py"))
        os.execl(python, python, script)


def show_update_dialog(parent):
    """Güncelleme dialogunu göster"""
    UpdateDialog(parent)
