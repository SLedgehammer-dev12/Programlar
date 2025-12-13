# translations.py - Multi-language support for Gas Flow Calculator V5

# Current language setting
_current_lang = "tr"

# Translation dictionaries
TRANSLATIONS = {
    "tr": {
        # App Title
        "app_title": "Doğal Gaz Hesaplayıcı V5 (Modüler & Ergonomik)",
        
        # Menu - File
        "menu_file": "Dosya",
        "menu_save_project": "Projeyi Kaydet (JSON)",
        "menu_load_project": "Proje Aç (JSON)",
        "menu_exit": "Çıkış",
        
        # Menu - Update
        "menu_update": "Güncelleme",
        "menu_check_updates": "Güncellemeleri Kontrol Et",
        "menu_download_latest": "Son Sürümü İndir",
        "menu_apply_update": "Zip'ten Güncellemeyi Uygula...",
        "menu_update_config": "Güncelleme Yapılandırması...",
        
        # Menu - Language
        "menu_language": "Dil",
        "lang_turkish": "Türkçe",
        "lang_english": "English",
        
        # Tabs
        "tab_calculation": "Hesaplama",
        "tab_logs": "İşlem Günlüğü",
        
        # Sections
        "section_gas_mixture": "1. Gaz Karışımı",
        "section_process_conditions": "2. Proses Koşulları",
        "section_pipe_properties": "3. Boru ve Hat Özellikleri",
        "section_design_criteria": "Tasarım Kriterleri (Min. Çap Hesabı)",
        "section_fittings": "Boru Elemanları (Adet)",
        
        # Gas Section
        "gas_search": "Gaz Ara:",
        "btn_add_gas": "Ekle",
        "gas_total": "Toplam:",
        "composition_type": "Bileşim Türü:",
        "mol_percent": "Mol %",
        "mass_percent": "Kütle %",
        
        # Process Section
        "inlet_pressure": "Giriş Basıncı:",
        "temperature": "Sıcaklık:",
        "flow_rate": "Akış Miktarı:",
        "calc_target": "Hesaplama Hedefi:",
        "thermo_model": "Model:",
        "flow_type": "Akış Tipi:",
        
        # Calculation Targets
        "target_pressure_drop": "Çıkış Basıncı",
        "target_max_length": "Maksimum Uzunluk",
        "target_min_diameter": "Minimum Çap",
        
        # Flow Types
        "flow_incompressible": "Sıkıştırılamaz",
        "flow_compressible": "Sıkıştırılabilir",
        
        # Pipe Section
        "material": "Malzeme:",
        "length": "Uzunluk (m):",
        "outer_diameter": "Dış Çap (mm):",
        "wall_thickness": "Et Kalınlığı (mm):",
        "target_outlet_pressure": "Hedef Çıkış Basıncı:",
        "max_velocity": "Maks. Hız (m/s):",
        "design_pressure": "Tasarım Basıncı:",
        "factor_f": "Faktör F:",
        "factor_e": "Faktör E:",
        "factor_t": "Faktör T:",
        
        # Results Section
        "results_summary": "Özet Tablo",
        "results_schematic": "Sistem Şeması",
        "results_report": "Detaylı Rapor",
        
        # Buttons
        "btn_calculate": "HESAPLA",
        "btn_show_graphs": "Grafikler",
        "btn_save_report": "Raporu Kaydet",
        
        # Schematic Labels
        "schematic_inlet": "GİRİŞ",
        "schematic_outlet": "ÇIKIŞ",
        "schematic_pending": "Hesaplama Bekleniyor",
        "schematic_calculating": "Hesaplanıyor...",
        "schematic_completed": "Hesaplama Tamamlandı",
        "schematic_error": "Hesaplama Hatası",
        "schematic_results": "SON HESAPLAMA SONUÇLARI",
        "schematic_details": "HESAPLAMA DETAYLARI",
        "schematic_selection_details": "SEÇİM DETAYLARI",
        
        # Schematic Targets
        "schematic_target_pressure": "Çıkış Basıncı Hesaplama",
        "schematic_target_length": "Maksimum Hat Uzunluğu",
        "schematic_target_diameter": "Minimum Boru Çapı",
        
        # Schematic Values
        "schematic_p_inlet": "P_giriş",
        "schematic_p_outlet": "P_çıkış",
        "schematic_p_target": "P_hedef",
        "schematic_temp": "Sıcaklık",
        "schematic_flow": "Debi",
        "schematic_length": "Uzunluk",
        "schematic_diameter": "Çap",
        "schematic_velocity": "Hız",
        "schematic_fittings": "Fitting",
        "schematic_unknown": "???",
        
        # Detail Labels
        "detail_reynolds": "Re",
        "detail_friction": "f",
        "detail_laminar": "Laminer",
        "detail_transition": "Geçiş",
        "detail_turbulent": "Türbülanslı",
        "detail_pipe_loss": "Boru",
        "detail_fitting_loss": "Fitting",
        "detail_density": "ρ",
        "detail_min_theoretical": "Min. Teorik Çap",
        "detail_wall_thickness": "Et Kalınlığı",
        "detail_velocity_usage": "Hız Kullanımı",
        "detail_alternatives": "alternatif boru mevcut",
        
        # Log Section
        "log_filter": "Filtre:",
        "log_all": "Tümü",
        "log_info": "INFO",
        "log_warning": "WARNING",
        "log_error": "ERROR",
        "btn_clear_logs": "Temizle",
        
        # Messages
        "msg_program_started": "PROGRAM BAŞLATILDI",
        "msg_version": "Uygulama sürümü",
        "msg_calculation_started": "Hesaplama başlatıldı...",
        "msg_calculation_completed": "Hesaplama başarıyla tamamlandı.",
        "msg_calculation_error": "Hesaplama hatası",
        "msg_starting": "Başlatılıyor...",
        "msg_calculating": "Hesaplanıyor...",
        "msg_completed": "Tamamlandı",
        
        # Validation
        "validation_positive_pressure": "Giriş basıncı pozitif olmalıdır.",
        "validation_positive_temp": "Sıcaklık mutlak sıfırın üzerinde olmalıdır.",
        "validation_positive_flow": "Akış miktarı pozitif olmalıdır.",
        "validation_add_gas": "En az bir gaz bileşeni eklemelisiniz.",
        "validation_positive_length": "Uzunluk pozitif olmalıdır.",
        "validation_positive_diameter": "Çap pozitif olmalıdır.",
        
        # Gas Composition
        "gas_composition_warning": "Gaz bileşimi toplamı",
        "gas_composition_normalize": "normalize edilsin mi?",
        "gas_composition_normalized": "Gaz bileşimi normalize edildi",
        
        # Updates
        "update_checking": "Güncellemeler kontrol ediliyor...",
        "update_config_error": "Güncelleme yapılandırması eksik veya bağlantı hatası.",
        "update_new_version": "Yeni sürüm bulundu",
        "update_changes": "Değişiklikler",
        "update_download_ask": "İndirmek ister misiniz?",
        "update_available": "Güncelleme Mevcut",
        "update_up_to_date": "Uygulamanız güncel.",
        "update_downloading": "Son sürüm indiriliyor...",
        "update_downloaded": "Dosya indirildi",
        "update_apply_ask": "Şimdi güncellemeyi uygulamak ister misiniz?",
        "update_later": "Daha sonra 'Zip'ten Güncellemeyi Uygula...' menüsünden uygulayabilirsiniz.",
        "update_no_asset": "İndirilebilir bir varlık bulunamadı.",
        "update_applied": "Güncelleme başarıyla uygulandı. Uygulamayı yeniden başlatmanız önerilir.",
        
        # Dialogs
        "dialog_update": "Güncelleme",
        "dialog_info": "Bilgi",
        "dialog_error": "Hata",
        "dialog_warning": "Uyarı",
        "dialog_confirm": "Onay",
        
        # Tooltips
        "tooltip_factor_f": "Dizayn Faktörü (F)\nASME B31.8'e göre:\n0.72 (Class 1)\n0.60 (Class 2)\n0.50 (Class 3)\n0.40 (Class 4)",
        "tooltip_factor_e": "Boyuna Ek Yeri Faktörü (E)\n1.00 (Dikişsiz/ERW)\n0.80 (Spiral Kaynaklı bazı tipler)",
        "tooltip_factor_t": "Sıcaklık Derating Faktörü (T)\n1.00 (<= 121°C)\n0.967 (135°C)\n0.933 (149°C)",
        
        # Language Change
        "lang_change_title": "Dil Değişikliği",
        "lang_change_message": "Dil değişikliği için uygulamayı yeniden başlatmanız gerekiyor.",
        "lang_restart_now": "Şimdi yeniden başlatılsın mı?",
        
        # Log Headers
        "log_time": "Zaman",
        "log_level": "Seviye",
        "log_message": "Mesaj",
        
        # Report
        "report_saved": "Rapor kaydedildi.",
        "dialog_success": "Başarılı",
        
        # Gas selection
        "select_gas": "Gaz Seçin",
        "delete": "Sil",
        
        # Results table
        "result_parameter": "Parametre",
        "result_value": "Değer",
        "result_unit": "Birim",
        
        # Project
        "project_saved": "Proje kaydedildi.",
        "project_loaded": "Proje yüklendi.",
        "save_error": "Kaydetme hatası",
        "load_error": "Yükleme hatası",
        
        # Results panel
        "calculation_results": "Hesaplama Sonuçları",
        "calculating_progress": "Hesaplanıyor... %",
        "show_graphs": "Grafikleri Göster",
        "save_report": "Raporu Kaydet",
    },
    
    "en": {
        # App Title
        "app_title": "Natural Gas Calculator V5 (Modular & Ergonomic)",
        
        # Menu - File
        "menu_file": "File",
        "menu_save_project": "Save Project (JSON)",
        "menu_load_project": "Open Project (JSON)",
        "menu_exit": "Exit",
        
        # Menu - Update
        "menu_update": "Update",
        "menu_check_updates": "Check for Updates",
        "menu_download_latest": "Download Latest Version",
        "menu_apply_update": "Apply Update from Zip...",
        "menu_update_config": "Update Configuration...",
        
        # Menu - Language
        "menu_language": "Language",
        "lang_turkish": "Türkçe",
        "lang_english": "English",
        
        # Tabs
        "tab_calculation": "Calculation",
        "tab_logs": "Activity Log",
        
        # Sections
        "section_gas_mixture": "1. Gas Mixture",
        "section_process_conditions": "2. Process Conditions",
        "section_pipe_properties": "3. Pipe and Line Properties",
        "section_design_criteria": "Design Criteria (Min. Diameter Calc.)",
        "section_fittings": "Pipe Fittings (Count)",
        
        # Gas Section
        "gas_search": "Search Gas:",
        "btn_add_gas": "Add",
        "gas_total": "Total:",
        "composition_type": "Composition Type:",
        "mol_percent": "Mol %",
        "mass_percent": "Mass %",
        
        # Process Section
        "inlet_pressure": "Inlet Pressure:",
        "temperature": "Temperature:",
        "flow_rate": "Flow Rate:",
        "calc_target": "Calculation Target:",
        "thermo_model": "Model:",
        "flow_type": "Flow Type:",
        
        # Calculation Targets
        "target_pressure_drop": "Outlet Pressure",
        "target_max_length": "Maximum Length",
        "target_min_diameter": "Minimum Diameter",
        
        # Flow Types
        "flow_incompressible": "Incompressible",
        "flow_compressible": "Compressible",
        
        # Pipe Section
        "material": "Material:",
        "length": "Length (m):",
        "outer_diameter": "Outer Diameter (mm):",
        "wall_thickness": "Wall Thickness (mm):",
        "target_outlet_pressure": "Target Outlet Pressure:",
        "max_velocity": "Max. Velocity (m/s):",
        "design_pressure": "Design Pressure:",
        "factor_f": "Factor F:",
        "factor_e": "Factor E:",
        "factor_t": "Factor T:",
        
        # Results Section
        "results_summary": "Summary Table",
        "results_schematic": "System Schematic",
        "results_report": "Detailed Report",
        
        # Buttons
        "btn_calculate": "CALCULATE",
        "btn_show_graphs": "Graphs",
        "btn_save_report": "Save Report",
        
        # Schematic Labels
        "schematic_inlet": "INLET",
        "schematic_outlet": "OUTLET",
        "schematic_pending": "Calculation Pending",
        "schematic_calculating": "Calculating...",
        "schematic_completed": "Calculation Completed",
        "schematic_error": "Calculation Error",
        "schematic_results": "LAST CALCULATION RESULTS",
        "schematic_details": "CALCULATION DETAILS",
        "schematic_selection_details": "SELECTION DETAILS",
        
        # Schematic Targets
        "schematic_target_pressure": "Outlet Pressure Calculation",
        "schematic_target_length": "Maximum Line Length",
        "schematic_target_diameter": "Minimum Pipe Diameter",
        
        # Schematic Values
        "schematic_p_inlet": "P_inlet",
        "schematic_p_outlet": "P_outlet",
        "schematic_p_target": "P_target",
        "schematic_temp": "Temperature",
        "schematic_flow": "Flow Rate",
        "schematic_length": "Length",
        "schematic_diameter": "Diameter",
        "schematic_velocity": "Velocity",
        "schematic_fittings": "Fittings",
        "schematic_unknown": "???",
        
        # Detail Labels
        "detail_reynolds": "Re",
        "detail_friction": "f",
        "detail_laminar": "Laminar",
        "detail_transition": "Transition",
        "detail_turbulent": "Turbulent",
        "detail_pipe_loss": "Pipe",
        "detail_fitting_loss": "Fittings",
        "detail_density": "ρ",
        "detail_min_theoretical": "Min. Theoretical Diameter",
        "detail_wall_thickness": "Wall Thickness",
        "detail_velocity_usage": "Velocity Usage",
        "detail_alternatives": "alternative pipes available",
        
        # Log Section
        "log_filter": "Filter:",
        "log_all": "All",
        "log_info": "INFO",
        "log_warning": "WARNING",
        "log_error": "ERROR",
        "btn_clear_logs": "Clear",
        
        # Messages
        "msg_program_started": "PROGRAM STARTED",
        "msg_version": "Application version",
        "msg_calculation_started": "Calculation started...",
        "msg_calculation_completed": "Calculation completed successfully.",
        "msg_calculation_error": "Calculation error",
        "msg_starting": "Starting...",
        "msg_calculating": "Calculating...",
        "msg_completed": "Completed",
        
        # Validation
        "validation_positive_pressure": "Inlet pressure must be positive.",
        "validation_positive_temp": "Temperature must be above absolute zero.",
        "validation_positive_flow": "Flow rate must be positive.",
        "validation_add_gas": "You must add at least one gas component.",
        "validation_positive_length": "Length must be positive.",
        "validation_positive_diameter": "Diameter must be positive.",
        
        # Gas Composition
        "gas_composition_warning": "Gas composition total is",
        "gas_composition_normalize": "Normalize to 100%?",
        "gas_composition_normalized": "Gas composition normalized",
        
        # Updates
        "update_checking": "Checking for updates...",
        "update_config_error": "Update configuration missing or connection error.",
        "update_new_version": "New version found",
        "update_changes": "Changes",
        "update_download_ask": "Do you want to download?",
        "update_available": "Update Available",
        "update_up_to_date": "Your application is up to date.",
        "update_downloading": "Downloading latest version...",
        "update_downloaded": "File downloaded",
        "update_apply_ask": "Do you want to apply the update now?",
        "update_later": "You can apply it later from 'Apply Update from Zip...' menu.",
        "update_no_asset": "No downloadable asset found.",
        "update_applied": "Update applied successfully. Please restart the application.",
        
        # Dialogs
        "dialog_update": "Update",
        "dialog_info": "Info",
        "dialog_error": "Error",
        "dialog_warning": "Warning",
        "dialog_confirm": "Confirm",
        
        # Tooltips
        "tooltip_factor_f": "Design Factor (F)\nPer ASME B31.8:\n0.72 (Class 1)\n0.60 (Class 2)\n0.50 (Class 3)\n0.40 (Class 4)",
        "tooltip_factor_e": "Longitudinal Joint Factor (E)\n1.00 (Seamless/ERW)\n0.80 (Some spiral welded types)",
        "tooltip_factor_t": "Temperature Derating Factor (T)\n1.00 (<= 250°F)\n0.967 (275°F)\n0.933 (300°F)",
        
        # Language Change
        "lang_change_title": "Language Change",
        "lang_change_message": "The application needs to restart to change the language.",
        "lang_restart_now": "Restart now?",
        
        # Log Headers
        "log_time": "Time",
        "log_level": "Level",
        "log_message": "Message",
        
        # Report
        "report_saved": "Report saved.",
        "dialog_success": "Success",
        
        # Gas selection
        "select_gas": "Select Gas",
        "delete": "Delete",
        
        # Results table
        "result_parameter": "Parameter",
        "result_value": "Value",
        "result_unit": "Unit",
        
        # Project
        "project_saved": "Project saved.",
        "project_loaded": "Project loaded.",
        "save_error": "Save error",
        "load_error": "Load error",
        
        # Results panel
        "calculation_results": "Calculation Results",
        "calculating_progress": "Calculating... %",
        "show_graphs": "Show Graphs",
        "save_report": "Save Report",
    }
}

# Fitting names translations
FITTING_TRANSLATIONS = {
    "tr": {
        "90° Dirsek": "90° Dirsek",
        "45° Dirsek": "45° Dirsek",
        "30° Dirsek": "30° Dirsek",
        "60° Dirsek": "60° Dirsek",
        "180° Dirsek": "180° Dirsek",
        "Tee (Doğrudan)": "Tee (Doğrudan)",
        "Tee (Yan Dal)": "Tee (Yan Dal)",
        "Küresel Vana (Tam Açık)": "Küresel Vana (Tam Açık)",
        "Globe Vana (Tam Açık)": "Globe Vana (Tam Açık)",
        "Gate Vana (Tam Açık)": "Gate Vana (Tam Açık)",
        "Check Valve": "Check Valve",
    },
    "en": {
        "90° Dirsek": "90° Elbow",
        "45° Dirsek": "45° Elbow",
        "30° Dirsek": "30° Elbow",
        "60° Dirsek": "60° Elbow",
        "180° Dirsek": "180° U-Bend",
        "Tee (Doğrudan)": "Tee (Run)",
        "Tee (Yan Dal)": "Tee (Branch)",
        "Küresel Vana (Tam Açık)": "Ball Valve (Fully Open)",
        "Globe Vana (Tam Açık)": "Globe Valve (Fully Open)",
        "Gate Vana (Tam Açık)": "Gate Valve (Fully Open)",
        "Check Valve": "Check Valve",
    }
}


def set_language(lang: str):
    """Set the current language."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_language() -> str:
    """Get the current language code."""
    return _current_lang


def t(key: str, default: str = None) -> str:
    """Get translation for a key."""
    translations = TRANSLATIONS.get(_current_lang, TRANSLATIONS["tr"])
    return translations.get(key, default or key)


def t_fitting(fitting_name: str) -> str:
    """Get translated fitting name."""
    translations = FITTING_TRANSLATIONS.get(_current_lang, FITTING_TRANSLATIONS["tr"])
    return translations.get(fitting_name, fitting_name)


def get_fitting_name_tr(fitting_name_translated: str) -> str:
    """Get Turkish fitting name from translated name (for K factor lookup)."""
    if _current_lang == "tr":
        return fitting_name_translated
    # Reverse lookup
    en_to_tr = {v: k for k, v in FITTING_TRANSLATIONS["en"].items()}
    return en_to_tr.get(fitting_name_translated, fitting_name_translated)
