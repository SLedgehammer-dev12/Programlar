"""
Dialog windows and user prompts.

Provides reusable dialog functions for user interaction.
"""

from tkinter import messagebox
from typing import List, Optional
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from natural_gas_g5.config import preferences


def show_heos_compatibility_warning(
    incompatible_gases: List[str],
    heos_supported_gases: List[str]
) -> bool:
    """
    Show HEOS compatibility warning and ask user if they want to switch to SRK.
    
    Args:
        incompatible_gases: List of incompatible gas names
        heos_supported_gases: List of HEOS-compatible gases
        
    Returns:
        True if user wants to switch to SRK, False otherwise
    """
    gases_str = ", ".join(incompatible_gases)
    
    message = (
        f"HEOS Backend Uyumluluk Uyarısı\n\n"
        f"Seçilen karışım HEOS backend'i için tam karışım desteğine sahip değil.\n"
        f"Uyumsuz gazlar: {gases_str}\n\n"
        f"KRİTİK UYARI: HEOS ile devam etmek hatalı sonuçlara yol açabilir.\n\n"
        f"Doğruluk için SRK yöntemine otomatik geçiş yapılsın mı?\n"
        f"(ÖNERİLİR)"
    )
    
    result = messagebox.askyesno(
        "HEOS Uyumluluk Uyarısı",
        message,
        icon='warning'
    )
    
    if result:
        messagebox.showinfo(
            "Backend Değişikliği",
            "Hesaplama HEOS yerine SRK yöntemi ile devam edecek."
        )
    else:
        messagebox.showwarning(
            "Risk Kabul Edildi",
            "HEOS ile devam etme riskini kabul ettiniz. "
            "Hesaplama başarısız olabilir."
        )
    
    return result


def show_heating_value_method_warning(method: str) -> None:
    """
    Show warning when heating values are calculated using component-based method.
    
    Args:
        method: Calculation method used
    """
    if method.startswith("Bileşen bazlı"):
        messagebox.showwarning(
            "Isıl Değer Hesaplama Uyarısı ⚠️",
            "CoolProp yerleşik modeli ısıl değerleri doğrudan hesaplayamadığı için,\n"
            "daha sağlam 'Bileşen Bazlı Toplama' yöntemi kullanılmıştır.\n\n"
            "Bu yöntem karışım etkileşimlerini ihmal eder ve CoolProp yerleşik\n"
            "hesabına göre daha düşük doğrulukta olabilir.\n\n"
            "**Sonuçları mühendislik onayı ile kullanınız.**"
        )


def show_backend_fallback_info(error_message: str, failed_backend: str) -> None:
    """
    Show information when backend fallback occurs.
    
    Args:
        error_message: Error message from failed backend
        failed_backend: Name of the backend that failed
    """
    messagebox.showwarning(
        "Backend Değişikliği",
        f"{failed_backend} backend'i başarısız oldu:\n\n"
        f"CoolProp Hatası: {error_message}\n\n"
        f"Program otomatik olarak alternatif bir yöntem deneyecek."
    )


def show_backend_used_info(requested_backend: str, used_backend: str) -> None:
    """
    Show info when different backend was used than requested.
    
    Args:
        requested_backend: Backend user requested
        used_backend: Backend actually used
    """
    if requested_backend != used_backend:
        messagebox.showinfo(
            "Backend Değişikliği",
            f"Hesaplama {used_backend} yöntemi ile tamamlandı.\n"
            f"(İstenilen: {requested_backend})"
        )


def show_about_dialog() -> None:
    """Show application about information."""
    about_text = (
        "Termodinamik Gaz Karışımı Hesaplayıcı\n"
        "Sürüm 5.3.1 - Profesyonel Sürüm\n\n"
        "Bu program, CoolProp kütüphanesini kullanarak gaz karışımlarının\n"
        "termodinamik özelliklerini hesaplar.\n\n"
        "G5.3 sürümü ile görselleştirme ve raporlama özellikleri eklenmiştir.\n\n"
        "© 2026 Kompresör Pompa"
    )
    messagebox.showinfo("Hakkında", about_text)


def show_user_guide_dialog() -> None:
    """Show user guide information."""
    from natural_gas_g5.config.settings import config
    
    guide_text = (
        "KULLANIM KILAVUZU - Doğal Gaz Özellikleri G5\n\n"
        "1. GAZ KOMPOZİSYONU:\n"
        "   • Yüzde toplamı tam 100% olmalıdır\n"
        "   • Maksimum 20 gaz bileşeni eklenebilir\n"
        "   • Arama kutusu ile gaz seçimi hızlandırılabilir\n\n"
        "2. BASINÇ GİRİŞİ:\n"
        f"   • Gauge (g) basınçları için atmosferik basınç ({config.P_ATM_BAR} bar) referans alınır\n"
        "   • Absolute (a) basınçlar doğrudan kullanılır\n\n"
        "3. HESAPLAMA YÖNTEMİ:\n"
        "   • HEOS: En doğru, ancak sınırlı gaz desteği\n"
        "   • SRK/PR: Daha geniş kapsam, cubic equations of state\n"
        "   • Uyumsuzluk durumunda otomatik geçiş yapılabilir\n\n"
        "4. ISIL DEĞER GÜVENİLİRLİĞİ (KRİTİK):\n"
        "   • 'CoolProp yerleşik': En doğru yöntem\n"
        "   • 'Bileşen bazlı': Yedekleme yöntemi, daha düşük doğruluk\n"
        "   • Uyarı mesajları dikkate alınmalıdır\n\n"
        "5. SONUÇLAR:\n"
        "   • Gerçek koşullar (girilen T ve P'de)\n"
        "   • Standart koşullar (seçilen referans standarda göre)\n"
        "   • Isıl değerler (HHV, LHV, Wobbe)\n"
        "   • Hacim dönüşümü (isteğe bağlı)"
    )
    messagebox.showinfo("Kullanım Kılavuzu", guide_text)


def show_new_features_info() -> None:
    """Show new features information for G5.3 with do not show again option."""
    # Create custom window
    dialog = ctk.CTkToplevel()
    dialog.title("Yenilikler - Sürüm 5.3.1")
    dialog.geometry("620x600")
    dialog.resizable(False, False)
    
    # Make modal (optional, but good for focus)
    dialog.transient()
    dialog.grab_set()
    
    # Content Frame
    frame = ctk.CTkFrame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Title
    ctk.CTkLabel(
        frame, 
        text="🚀 DOĞAL GAZ ÖZELLİKLERİ G5.3 - YENİ SÜRÜM", 
        font=ctk.CTkFont(size=14, weight="bold")
    ).pack(pady=(0, 20))
    
    # Info Text
    info_text = (
        "🌟 YENİ ÖZELLİKLER (v5.3):\n"
        "• 📈 Faz Diyagramı: Karışımlarınız için çiğlenme/kaynama noktası eğrilerini görün.\n"
        "• 📄 Profesyonel PDF Raporu: Hesaplamalarınızı grafikler içeren şık PDF'lere dönüştürün.\n"
        "• 🥧 Bileşen Pasta Grafiği: Gaz kompozisyonunu görsel olarak anlık takip edin.\n"
        "• 🎨 Çoklu Tema Desteği: Mavi, Yeşil ve Koyu-Mavi tema seçenekleri eklendi.\n"
        "• ⚡ Akıllı Filtreleme: 100+ gaz arasından sadece yaygın doğal gazları görün.\n"
        "• 📋 Hazır Şablonlar: Botaş, LNG gibi sık kullanılan gaz karışımlarını tek tıkla yükleyin.\n\n"
        "🎉 ÖNCEKİ ÖZELLİKLER (v5.2):\n"
        "• Modüler Mimari ve Modern CustomTkinter Arayüzü.\n"
        "• KPI Panosu ile en kritik değerlere hızlı bakış.\n"
        "• Thread-Safe güvenli hesaplama yapısı."
    )
    
    text_area = ctk.CTkTextbox(frame, wrap=tk.WORD, height=250, width=540, font=ctk.CTkFont(size=12))
    text_area.insert("1.0", info_text)
    text_area.configure(state="disabled")
    text_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    # Checkbox
    dont_show_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(
        frame, 
        text="Bu pencereyi bir daha gösterme", 
        variable=dont_show_var
    ).pack(anchor="w", pady=(0, 15))
    
    # Close Logic
    def on_close():
        if dont_show_var.get():
            preferences.set_preference("show_welcome_v5_3", False)
        dialog.destroy()
    
    # Button
    ctk.CTkButton(
        frame, 
        text="Tamam, Başlayalım!", 
        command=on_close,
        width=200
    ).pack(anchor="center")
    
    # Handle window close button (X)
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    
    # Center on screen
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'{width}x{height}+{x}+{y}')


def confirm_calculation_start() -> bool:
    """
    Ask user confirmation before starting heavy calculation (if needed).
    
    Returns:
        True if user confirms, False otherwise
    """
    # For now, always return True (no confirmation needed)
    # Can be extended for very large calculations
    return True


def show_error(title: str, message: str) -> None:
    """
    Show error message dialog.
    
    Args:
        title: Dialog title
        message: Error message
    """
    messagebox.showerror(title, message)


def show_warning(title: str, message: str) -> None:
    """
    Show warning message dialog.
    
    Args:
        title: Dialog title
        message: Warning message
    """
    messagebox.showwarning(title, message)


def show_info(title: str, message: str) -> None:
    """
    Show information message dialog.
    
    Args:
        title: Dialog title
        message: Information message
    """
    messagebox.showinfo(title, message)
