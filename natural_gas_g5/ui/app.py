"""
Main application window.

Coordinates between input panel, output panel, calculator, and user interactions.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import threading
import queue
import logging
import os
from pathlib import Path

from natural_gas_g5.config.settings import config
from natural_gas_g5.config import preferences
from natural_gas_g5.models.calculator import ThermoCalculator, COOLPROP_AVAILABLE
from natural_gas_g5.core.exceptions import (
    ValidationError,
    BackendNotAvailableError,
    ThermoCalculationError
)
from natural_gas_g5.ui.input_panel import InputPanel
from natural_gas_g5.ui.output_panel import OutputPanel
from natural_gas_g5.ui import dialogs
from natural_gas_g5.utils.report_generator import ReportGenerator
from natural_gas_g5.utils.data_serializer import (
    save_inputs_to_file,
    load_inputs_from_file,
    validate_loaded_data,
    DataSerializationError,
    FILE_EXTENSION,
    FILE_TYPE_NAME
)
from natural_gas_g5.utils.updater import UpdateChecker


class ThermoApp(ctk.CTk):
    """
    Main application window using CustomTkinter.
    
    Manages the GUI, user interactions, and calculation workflow.
    """
    
    def __init__(self):
        """Initialize main application window."""
        super().__init__()
        
        # Configure CustomTkinter appearance from preferences
        saved_mode = preferences.get_preference("ctk_appearance_mode", config.CTK_THEME)
        saved_theme = preferences.get_preference("ctk_color_theme", config.CTK_COLOR_THEME)
        
        ctk.set_appearance_mode(saved_mode)
        ctk.set_default_color_theme(saved_theme)
        
        self.title(config.WINDOW_TITLE)
        self.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing ThermoApp")
        
        # Load gas list
        self.gas_list = self._load_gas_list()
        
        # Apply theme (Remove old ttk style)
        # style = ttk.Style(self)
        # style.theme_use(config.UI_THEME)
        
        # Initialize calculator
        self.calculator = ThermoCalculator()
        
        # Setup thread-safe queue for calculation results
        self.result_queue = queue.Queue()
        self._check_queue()

        
        # Create UI
        self._create_menu()
        self._create_main_layout()
        self._create_status_bar()
        
        # Show welcome message
        self.after(100, self._show_welcome)
    
    def _load_gas_list(self) -> list:
        """
        Load gas list from CoolProp or use fallback.
        
        Returns:
            List of gas names
        """
        if COOLPROP_AVAILABLE:
            try:
                import CoolProp.CoolProp as CP
                fluids = CP.get_global_param_string("FluidsList")
                if fluids:
                    all_gases = [f.strip() for f in fluids.split(',') if f.strip()]
                    # Filter for natural gas focused components
                    natural_gases = [g.lower() for g in config.NATURAL_GAS_FOCUS_LIST]
                    gas_list = sorted([
                        f for f in all_gases 
                        if f.lower() in natural_gases
                    ])
                    
                    if not gas_list: # Fallback if filter is too strict
                        gas_list = sorted(all_gases)
                        
                    self.logger.info(f"Loaded {len(gas_list)} focused gases from CoolProp")
                    return gas_list
            except Exception as e:
                self.logger.error(f"Failed to load CoolProp gas list: {e}")
        
        # Fallback list
        self.logger.warning("Using fallback gas list")
        messagebox.showwarning(
            "CoolProp Uyarısı",
            "CoolProp akışkan listesi yüklenemedi.\n"
            "Kısıtlı yedek akışkan listesi kullanılıyor."
        )
        return config.FALLBACK_GAS_LIST
    
    def _create_menu(self):
        """Create menu bar."""
        menubar = tk.Menu(self)
        self.configure(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Dosya", menu=file_menu)
        file_menu.add_command(label="Aç...", command=self._on_load_data, accelerator="Ctrl+O")
        file_menu.add_command(label="Kaydet...", command=self._on_save_data, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Rapor Kaydet", command=self._on_save_report)
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.quit)
        
        # Keyboard shortcuts
        self.bind_all("<Control-o>", lambda e: self._on_load_data())
        self.bind_all("<Control-s>", lambda e: self._on_save_data())
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Yardım", menu=help_menu)
        help_menu.add_command(label="Kullanım Kılavuzu", command=dialogs.show_user_guide_dialog)
        help_menu.add_separator()
        help_menu.add_command(label="Güncellemeleri Denetle", command=self._check_for_updates_manual)
        help_menu.add_separator()
        help_menu.add_command(label="Hakkında", command=self._show_about)
        
        # View menu (Appearance)
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Görünüm", menu=view_menu)
        
        # Appearance Mode
        mode_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Mod", menu=mode_menu)
        mode_menu.add_command(label="Sistem", command=lambda: self._change_appearance_mode("System"))
        mode_menu.add_command(label="Koyu", command=lambda: self._change_appearance_mode("Dark"))
        mode_menu.add_command(label="Açık", command=lambda: self._change_appearance_mode("Light"))
        
        # Color Theme
        theme_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Renk Teması", menu=theme_menu)
        theme_menu.add_command(label="Mavi (Standart)", command=lambda: self._change_color_theme("blue"))
        theme_menu.add_command(label="Yeşil", command=lambda: self._change_color_theme("green"))
        theme_menu.add_command(label="Koyu Mavi", command=lambda: self._change_color_theme("dark-blue"))
    
    def _create_main_layout(self):
        """Create main content layout with input and output panels."""
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Input panel (left side)
        input_frame = ctk.CTkFrame(main_content)
        input_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=(0, 10))
        
        self.input_panel = InputPanel(input_frame, self.gas_list)
        self.input_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Calculate button frame with progress
        calc_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        calc_frame.pack(pady=10, padx=10, fill=tk.X)
        
        self.calc_button = ctk.CTkButton(
            calc_frame,
            text="Hesapla",
            command=self._on_calculate,
            fg_color="#4CAF50",
            hover_color="#45a049",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=40,
            cursor="hand2"
        )
        self.calc_button.pack(fill=tk.X)
        
        # Progress bar inside button frame (starts hidden)
        self.calc_progress = ctk.CTkProgressBar(calc_frame, mode='indeterminate')
        
        # Output panel (right side)
        output_frame = ctk.CTkFrame(main_content)
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.output_panel = OutputPanel(output_frame)
        self.output_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Report button
        report_button = ctk.CTkButton(
            output_frame,
            text="Profesyonel PDF Raporu Oluştur",
            command=self._on_save_report,
            fg_color="#1f538d",
            hover_color="#14375e",
            text_color="white",
            font=ctk.CTkFont(weight="bold")
        )
        report_button.pack(pady=10, padx=10, fill=tk.X)
    
    def _create_status_bar(self):
        """Create status bar at bottom."""
        self.status_var = tk.StringVar(value="Hazır.")
        status_frame = ctk.CTkFrame(self, height=30, corner_radius=0)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        status_label = ctk.CTkLabel(
            status_frame,
            textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.progress_bar = ctk.CTkProgressBar(status_frame, mode='indeterminate', width=150)
    
    def _show_welcome(self):
        """Show welcome/new features message if not disabled."""
        should_show = preferences.get_preference("show_welcome_v5_3", default=True)
        if should_show:
            dialogs.show_new_features_info()

    def _show_about(self):
        """Show about dialog."""
        dialogs.show_about_dialog()
        
    def _change_appearance_mode(self, new_mode: str):
        """Change application appearance mode."""
        ctk.set_appearance_mode(new_mode)
        # Store preference
        preferences.set_preference("ctk_appearance_mode", new_mode)
        # Update plots and other theme-dependent elements
        if hasattr(self, 'output_panel'):
            self.output_panel._on_unit_change() # Triggers re-plotting with correct theme colors
            
    def _change_color_theme(self, new_theme: str):
        """Change application color theme (Requires restart for full effect usually, but let's try)."""
        # Note: ctk.set_default_color_theme usually needs to be called BEFORE mainloop
        # But we can inform the user.
        messagebox.showinfo("Tema Değişikliği", "Renk teması değişikliği uygulandı. Bazı pencereler için programın yeniden başlatılması gerekebilir.")
        ctk.set_default_color_theme(new_theme)
        # Persist preference
        preferences.set_preference("ctk_color_theme", new_theme)
    
    # Event handlers
    
    def _on_calculate(self):
        """Handle calculate button click."""
        # Validate inputs
        try:
            inputs = self.input_panel.get_all_inputs()
        except ValidationError as e:
            dialogs.show_error("Giriş Hatası", str(e))
            return
        except Exception as e:
            self.logger.error(f"Input validation error: {e}", exc_info=True)
            dialogs.show_error("Giriş Hatası", f"Beklenmeyen hata: {str(e)}")
            return
        
        # Check HEOS compatibility
        try:
            incompatible_gases = []
            if inputs["backend"] == "HEOS":
                incompatible_gases = inputs["mixture"].check_heos_compatibility()

            if incompatible_gases:
                switch_to_srk = dialogs.show_heos_compatibility_warning(
                    incompatible_gases,
                    config.HEOS_COMPATIBLE_GASES
                )
                if switch_to_srk:
                    inputs["backend"] = "SRK"
                    self.input_panel.set_backend("SRK")
                else:
                    inputs["force_requested_backend"] = True
            
            # Show progress
            self.status_var.set("Hesaplanıyor...")
            self.calc_button.configure(state="disabled", fg_color="#FFA500", text="Hesaplanıyor...")
            self.calc_progress.pack(fill=tk.X, pady=(5, 0))
            self.calc_progress.start()
            
            # Run in thread
            thread = threading.Thread(
                target=self._run_calculation,
                args=(inputs,),
                daemon=True
            )
            thread.start()
            
        except ThermoCalculationError as e:
            messagebox.showerror("Giriş Hatası", str(e))
        except Exception as e:
            messagebox.showerror("Hata", f"Beklenmeyen hata: {e}")
            logging.error(f"Input processing failed: {e}", exc_info=True)

    def _check_queue(self):
        """Check queue for calculation results."""
        try:
            while True:
                msg_type, data = self.result_queue.get_nowait()
                if msg_type == "success":
                    result, used_backend, inputs = data
                    self._on_calculation_success(result, used_backend, inputs)
                elif msg_type == "error":
                    self._on_calculation_error(data)
                self.result_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.after(100, self._check_queue)
            
    def _run_calculation(self, inputs: dict):
        """
        Run calculation in background thread.
        
        Args:
            inputs: Dictionary of validated inputs
        """
        try:
            calculation_kwargs = {
                "mixture": inputs["mixture"],
                "temperature_k": inputs["temp_k"],
                "pressure_pa": inputs["press_pa"],
                "volume_m3": inputs["vol_m3"],
                "standard_T": inputs.get("standard_T", config.T_STANDARD),
                "standard_P": inputs.get("standard_P", config.P_STANDARD),
                "standard_name": inputs.get("standard_name")
            }

            if inputs.get("force_requested_backend"):
                result = self.calculator.calculate_properties(
                    backend=inputs["backend"],
                    **calculation_kwargs
                )
                used_backend = inputs["backend"]
            else:
                result, used_backend = self.calculator.calculate_with_fallback(
                    preferred_backend=inputs["backend"],
                    **calculation_kwargs
                )
                if result is None or not used_backend:
                    raise ThermoCalculationError(
                        "Hesaplama mevcut backend'lerle tamamlanamadı."
                    )
            
            # Send success to queue
            self.result_queue.put(("success", (result, used_backend, inputs)))
            
        except Exception as e:
            # Send error to queue
            self.result_queue.put(("error", e))
    
    def _on_calculation_success(self, result, used_backend: str, inputs: dict):
        """
        Handle successful calculation.
        
        Args:
            result: Calculation result
            used_backend: Backend that was used
            inputs: Original inputs
        """
        # Stop progress
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        # Display results
        self.output_panel.display_results(result)
        
        # Store for report generation
        self.last_result = result
        self.last_inputs = inputs
        
        # Show warnings if applicable
        if result.heating:
            dialogs.show_heating_value_method_warning(result.heating.calculation_method)
        
        if used_backend != inputs['backend']:
            dialogs.show_backend_used_info(inputs['backend'], used_backend)
            self.status_var.set(
                f"Hesaplama tamamlandı. "
                f"({inputs['backend']} yerine {used_backend} kullanıldı)"
            )
        else:
            self.status_var.set("Hesaplama tamamlandı.")
        
        # Re-enable UI
        self.calc_progress.stop()
        self.calc_progress.pack_forget()
        self.calc_button.configure(state="normal", fg_color="#4CAF50", text="Hesapla")
        
        # Success notification
        messagebox.showinfo("Hesaplama Tamamlandı", "Sonuçlar başarıyla hesaplandı!")
    
    def _on_calculation_error(self, error: Exception):
        """
        Handle calculation error.
        
        Args:
            error: Exception that occurred
        """
        # Stop progress
        self.calc_progress.stop()
        self.calc_progress.pack_forget()
        
        # Re-enable UI
        self.calc_button.configure(state="normal", fg_color="#F44336", text="Hata! Tekrar Dene")
        
        # Get log lines
        log_lines = self._get_recent_log_lines(10)
        
        # Display error
        self.output_panel.display_error(str(error), log_lines)
        self.status_var.set("Hesaplama hatası oluştu.")
        
        # Show error dialog
        dialogs.show_error(
            "Hesaplama Hatası",
            f"Hesaplama sırasında bir hata oluştu:\n\n{str(error)}\n\n"
            "Detaylar için Sonuçlar Tablosunu kontrol edin."
        )
    
    def _get_recent_log_lines(self, count: int = 10) -> list:
        """
        Get recent lines from log file.
        
        Args:
            count: Number of lines to retrieve
            
        Returns:
            List of log lines
        """
        log_file = config.LOG_FILE
        
        if not os.path.exists(log_file):
            return []
        
        try:
            with open(log_file, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-count:]]
        except Exception as e:
            self.logger.error(f"Could not read log file: {e}")
            return [f"Log okunamadı: {e}"]
    
    def _on_save_report(self):
        """Handle save report button click."""
        if not hasattr(self, 'last_result') or self.last_result is None:
            dialogs.show_warning("Rapor Hatası", "Önce bir hesaplama yapmalısınız.")
            return
        
        try:
            # Ask for file path
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF Dosyaları", "*.pdf"), ("Metin Dosyaları", "*.txt")],
                title="Raporu Kaydet"
            )
            
            if not file_path:
                return
            
            # Prepare input parameters for report
            inputs = self.last_inputs
            input_params = {
                'temperature': inputs['temperature_display'],
                'pressure': inputs['pressure_display'],
                'backend': self.last_result.backend_used,
                'volume': inputs.get('volume_display'),
                'fraction_type': inputs['mixture'].fraction_type
            }
            
            # Get gas composition
            gas_composition = [
                (comp.name, comp.fraction)
                for comp in inputs['mixture'].components
            ]
            
            # Get results
            results = self.output_panel.get_results_as_list()
            
            if file_path.lower().endswith(".pdf"):
                # Save plot to temp file
                import tempfile
                import os
                
                plot_img = None
                if self.last_result.phase_envelope:
                    fd, temp_path = tempfile.mkstemp(suffix=".png")
                    os.close(fd)
                    if self.output_panel.save_phase_envelope_plot(temp_path):
                        plot_img = temp_path
                
                # Generate PDF
                ReportGenerator.generate_pdf_report(
                    input_params,
                    results,
                    gas_composition,
                    file_path,
                    plot_image_path=plot_img
                )
                
                # Cleanup temp file
                if plot_img and os.path.exists(plot_img):
                    try: os.remove(plot_img)
                    except: pass
            else:
                # Fallback to Text
                ReportGenerator.generate_and_save(
                    input_params,
                    results,
                    gas_composition,
                    file_path,
                    log_file=config.LOG_FILE
                )
            
            dialogs.show_info("Başarılı", f"Rapor başarıyla kaydedildi:\n{file_path}")
            self.status_var.set(f"Rapor kaydedildi: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}", exc_info=True)
            dialogs.show_error("Rapor Hatası", f"Rapor kaydedilirken bir hata oluştu:\n{e}")

    def _on_save_data(self):
        """Handle save data menu item."""
        try:
            # Get data from input panel
            data = self.input_panel.get_save_data()
            
            # Check if there's any data to save
            if not data.get("composition"):
                dialogs.show_warning("Kaydetme Hatası", "Kaydedilecek gaz bileşeni yok.")
                return
            
            # Ask for file path
            file_path = filedialog.asksaveasfilename(
                defaultextension=FILE_EXTENSION,
                filetypes=[(FILE_TYPE_NAME, f"*{FILE_EXTENSION}"), ("Tüm Dosyalar", "*.*")],
                title="Verileri Kaydet"
            )
            
            if not file_path:
                return
            
            # Save to file
            save_inputs_to_file(data, file_path)
            
            dialogs.show_info("Başarılı", f"Veriler başarıyla kaydedildi:\n{file_path}")
            self.status_var.set(f"Kaydedildi: {file_path}")
            
        except DataSerializationError as e:
            dialogs.show_error("Kaydetme Hatası", str(e))
        except Exception as e:
            self.logger.error(f"Save data failed: {e}", exc_info=True)
            dialogs.show_error("Kaydetme Hatası", f"Beklenmeyen hata: {e}")

    def _on_load_data(self):
        """Handle load data menu item."""
        try:
            # Ask for file path
            file_path = filedialog.askopenfilename(
                defaultextension=FILE_EXTENSION,
                filetypes=[(FILE_TYPE_NAME, f"*{FILE_EXTENSION}"), ("Tüm Dosyalar", "*.*")],
                title="Verileri Aç"
            )
            
            if not file_path:
                return
            
            # Load from file
            data = load_inputs_from_file(file_path)
            
            # Validate data
            if not validate_loaded_data(data):
                dialogs.show_warning("Yükleme Uyarısı", "Dosya formatı beklenen şekilde değil. Bazı veriler yüklenemeyebilir.")
            
            # Apply to input panel
            self.input_panel.set_load_data(data)
            
            dialogs.show_info("Başarılı", f"Veriler başarıyla yüklendi:\n{file_path}")
            self.status_var.set(f"Yüklendi: {file_path}")
            
        except DataSerializationError as e:
            dialogs.show_error("Yükleme Hatası", str(e))
        except Exception as e:
            dialogs.show_error("Yükleme Hatası", f"Beklenmeyen hata: {e}")
            
    def _check_for_updates_manual(self):
        """Check for updates manually triggered by user."""
        try:
            self.status_var.set("Güncellemeler kontrol ediliyor...")
            self.configure(cursor="watch")
            self.update();
            
            checker = UpdateChecker()
            has_update, update_info = checker.check_for_updates()
            
            self.configure(cursor="")
            
            if has_update:
                msg = (
                    f"✨ YENİ SÜRÜM MEVCUT!\n\n"
                    f"Versiyon: {update_info.get('version')}\n"
                    f"Tarih: {update_info.get('date')}\n\n"
                    f"Değişiklikler:\n{update_info.get('changelog', '-')}\n\n"
                    f"İndirme sayfasına gitmek ister misiniz?"
                )
                if messagebox.askyesno("Güncelleme Mevcut", msg):
                    checker.open_download_page(update_info.get('download_url'))
            else:
                messagebox.showinfo(
                    "Güncel",
                    f"Programınız güncel.\n"
                    f"Versiyon: {config.APP_VERSION}"
                )
                
            self.status_var.set("Hazır.")
            
        except Exception as e:
            self.configure(cursor="")
            self.logger.error(f"Manual update check failed: {e}")
            messagebox.showerror("Hata", f"Güncelleme kontrolü başarısız:\n{e}")
            self.status_var.set("Güncelleme kontrolü başarısız.")
