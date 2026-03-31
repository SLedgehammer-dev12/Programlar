"""
Output panel component.

Displays calculation results in a TreeView widget with selectable unit systems.
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import List, Tuple, Optional
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

from natural_gas_g5.models.calculation_result import CalculationResult, PhaseEnvelopeData


class OutputPanel(ctk.CTkFrame):
    """
    Output panel for displaying calculation results.
    
    Shows results in a TreeView with columns: Property, Value, Unit
    """
    
    def __init__(self, parent, *args, **kwargs):
        """
        Initialize output panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent, *args, **kwargs)
        
        # Store current result for re-displaying with different units
        self.current_result: Optional[CalculationResult] = None
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create and layout widgets."""
        # Main label frame
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(main_frame, text="4. Hesaplama Sonuçları", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5, 5))
        
        # Notebook for tabs
        self.notebook = ctk.CTkTabview(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # ============== TAB 1: Results ==============
        self.notebook.add("Sonuçlar")
        results_tab = self.notebook.tab("Sonuçlar")
        
        # --- KPI DASHBOARD ---
        self.kpi_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        self.kpi_frame.pack(fill=tk.X, pady=(0, 10))
        
        # KPI variables
        self.kpis = {
            "Z-Faktörü": {"var": ctk.StringVar(value="-"), "unit_var": ctk.StringVar(value="")},
            "Yoğunluk": {"var": ctk.StringVar(value="-"), "unit_var": ctk.StringVar(value="kg/m³")},
            "Mol Kütlesi": {"var": ctk.StringVar(value="-"), "unit_var": ctk.StringVar(value="kg/mol")},
            "HHV": {"var": ctk.StringVar(value="-"), "unit_var": ctk.StringVar(value="MJ/Sm³")}
        }
        
        cols = len(self.kpis)
        for i, (title, data) in enumerate(self.kpis.items()):
            card = ctk.CTkFrame(self.kpi_frame, corner_radius=10, fg_color=("gray85", "gray25"))
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12)).pack(pady=(5, 0))
            ctk.CTkLabel(
                card, 
                textvariable=data["var"], 
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="#4CAF50"
            ).pack()
            ctk.CTkLabel(
                card,
                textvariable=data["unit_var"],
                font=ctk.CTkFont(size=10)
            ).pack(pady=(0, 5))
        
        # --- UNIT SELECTOR & TREEVIEW ---
        unit_select_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        unit_select_frame.pack(fill=tk.X, pady=(0, 5))
        
        ctk.CTkLabel(unit_select_frame, text="Birim Sistemi:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.unit_system_var = ctk.StringVar(value="SI")
        unit_combo = ctk.CTkComboBox(
            unit_select_frame,
            variable=self.unit_system_var,
            values=["SI", "Imperial", "Mixed"],
            state="readonly",
            width=150,
            command=self._on_unit_change
        )
        unit_combo.pack(side=tk.LEFT)
        
        # Apply dark theme styling to Treeview (since it's still a ttk widget)
        style = ttk.Style()
        bg_color = "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#f0f0f0"
        fg_color = "white" if ctk.get_appearance_mode() == "Dark" else "black"
        sel_bg = "#1f538d"
        
        style.theme_use("default")
        style.configure("Treeview",
                        background=bg_color,
                        foreground=fg_color,
                        rowheight=25,
                        fieldbackground=bg_color)
        style.map('Treeview', background=[('selected', sel_bg)])
        style.configure("Treeview.Heading",
                        background="#3c3c3c" if bg_color == "#2b2b2b" else "#d9d9d9",
                        foreground=fg_color,
                        relief="flat")
        style.map("Treeview.Heading",
                  background=[('active', "#4c4c4c" if bg_color == "#2b2b2b" else "#e0e0e0")])

        # TreeView with columns
        cols = ("Özellik", "Değer", "Birim")
        self.results_tree = ttk.Treeview(
            results_tab,
            columns=cols,
            show="headings",
            height=15
        )
        
        # Configure columns
        self.results_tree.heading("Özellik", text="Özellik")
        self.results_tree.heading("Değer", text="Değer")
        self.results_tree.heading("Birim", text="Birim")
        
        self.results_tree.column("Özellik", width=250)
        self.results_tree.column("Değer", width=170)
        self.results_tree.column("Birim", width=120)
        
        # Scrollbar for results
        scrollbar = ttk.Scrollbar(
            results_tab,
            orient=tk.VERTICAL,
            command=self.results_tree.yview
        )
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure tag styles
        self.results_tree.tag_configure(
            'header',
            background='#3c3c3c' if ctk.get_appearance_mode() == "Dark" else '#E0E0E0',
            font=('TkDefaultFont', 9, 'bold')
        )
        self.results_tree.tag_configure(
            'error_header',
            background='#5c2b2b' if ctk.get_appearance_mode() == "Dark" else '#FFCCCC',
            foreground='white' if ctk.get_appearance_mode() == "Dark" else 'black',
            font=('TkDefaultFont', 9, 'bold')
        )
        
        # ============== TAB 2: Faz Diyagramı ==============
        self.notebook.add("Faz Diyagramı")
        phase_tab = self.notebook.tab("Faz Diyagramı")
        
        self.phase_fig = Figure(figsize=(5, 4), dpi=100)
        self.phase_ax = self.phase_fig.add_subplot(111)
        
        # Theme configuration for plot
        bg_col = '#2b2b2b' if ctk.get_appearance_mode() == "Dark" else '#f0f0f0'
        fg_col = 'white' if ctk.get_appearance_mode() == "Dark" else 'black'
        
        self.phase_fig.patch.set_facecolor(bg_col)
        self.phase_ax.set_facecolor(bg_col)
        self.phase_ax.tick_params(colors=fg_col)
        for spine in self.phase_ax.spines.values():
            spine.set_edgecolor(fg_col)
        self.phase_ax.xaxis.label.set_color(fg_col)
        self.phase_ax.yaxis.label.set_color(fg_col)
        
        # Add canvas
        self.phase_canvas = FigureCanvasTkAgg(self.phase_fig, master=phase_tab)
        self.phase_canvas.draw()
        
        # Add toolbar
        toolbar_frame = ctk.CTkFrame(phase_tab)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.phase_toolbar = NavigationToolbar2Tk(self.phase_canvas, toolbar_frame)
        self.phase_toolbar.update()
        
        self.phase_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ============== TAB 3: Loglar ==============
        self.notebook.add("Loglar")
        logs_tab = self.notebook.tab("Loglar")
        
        # Log level filter
        filter_frame = ctk.CTkFrame(logs_tab, fg_color="transparent")
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        
        ctk.CTkLabel(filter_frame, text="Seviye:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.log_level_var = ctk.StringVar(value="Hepsi")
        level_combo = ctk.CTkComboBox(
            filter_frame,
            variable=self.log_level_var,
            values=["Hepsi", "DEBUG", "INFO", "WARNING", "ERROR"],
            state="readonly",
            width=100,
            command=self._on_log_level_change
        )
        level_combo.pack(side=tk.LEFT)
        
        # Clear button
        ctk.CTkButton(
            filter_frame,
            text="Temizle",
            command=self._clear_logs,
            width=80
        ).pack(side=tk.RIGHT, padx=5)
        
        # Auto-scroll checkbox
        self.auto_scroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            filter_frame,
            text="Otomatik Kaydır",
            variable=self.auto_scroll_var
        ).pack(side=tk.RIGHT, padx=10)
        
        # Log text widget
        log_frame = ctk.CTkFrame(logs_tab)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(
            log_frame,
            wrap=tk.WORD,
            height=20,
            font=('Consolas', 9),
            state=tk.DISABLED,
            bg="#1e1e1e" if ctk.get_appearance_mode() == "Dark" else "white",
            fg="#d4d4d4" if ctk.get_appearance_mode() == "Dark" else "black",
            relief="flat",
            padx=5, pady=5
        )
        
        log_scrollbar = ctk.CTkScrollbar(log_frame, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure log text tags for colors
        self.log_text.tag_configure("DEBUG", foreground="#888888")
        self.log_text.tag_configure(
            "INFO",
            foreground="#d4d4d4" if ctk.get_appearance_mode() == "Dark" else "#000000"
        )
        self.log_text.tag_configure("WARNING", foreground="#CC8800")
        self.log_text.tag_configure("ERROR", foreground="#CC0000")
        self.log_text.tag_configure("CRITICAL", foreground="#FF0000", background="#FFEEEE")
        
        # Setup logging handler
        self._setup_log_handler()
    
    def _setup_log_handler(self):
        """Setup custom logging handler to capture logs to Text widget."""
        import logging
        
        # Store all log records for filtering
        self.log_records = []
        
        # Level name to numeric mapping
        self.level_map = {
            "Hepsi": 0,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }
        
        panel = self  # Reference for inner class
        
        class TextHandler(logging.Handler):
            def __init__(self, text_widget, auto_scroll_var):
                super().__init__()
                self.text_widget = text_widget
                self.auto_scroll_var = auto_scroll_var
            
            def emit(self, record):
                msg = self.format(record)
                level = record.levelname
                
                # Store record for filtering
                panel.log_records.append((msg, level, record.levelno))
                
                # Check if should display based on current filter
                selected_level = panel.log_level_var.get()
                min_level = panel.level_map.get(selected_level, 0)
                
                if record.levelno >= min_level:
                    def append():
                        self.text_widget.configure(state=tk.NORMAL)
                        self.text_widget.insert(tk.END, msg + '\n', level)
                        if self.auto_scroll_var.get():
                            self.text_widget.see(tk.END)
                        self.text_widget.configure(state=tk.DISABLED)
                    
                    # Schedule on main thread
                    self.text_widget.after(0, append)
        
        # Create and add handler
        self.text_handler = TextHandler(self.log_text, self.auto_scroll_var)
        self.text_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')
        )
        
        # Remove existing TextHandlers to prevent memory leaks and duplicates
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if handler.__class__.__name__ == 'TextHandler':
                root_logger.removeHandler(handler)
                
        # Add to root logger
        root_logger.addHandler(self.text_handler)
    
    def _on_log_level_change(self, event=None):
        """Handle log level filter change - refresh display."""
        selected_level = self.log_level_var.get()
        min_level = self.level_map.get(selected_level, 0)
        
        # Clear and re-display filtered logs
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        
        for msg, level, levelno in self.log_records:
            if levelno >= min_level:
                self.log_text.insert(tk.END, msg + '\n', level)
        
        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)
        
        self.log_text.configure(state=tk.DISABLED)
    
    def _clear_logs(self):
        """Clear log text widget."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)
    
    def display_results(self, result: CalculationResult) -> None:
        """
        Display calculation results in tree view.
        
        Args:
            result: Calculation result object
        """
        # Clear existing results
        self.clear_results()
        
        # Store result for unit switching
        self.current_result = result
        
        # Get current unit system
        unit_system = self.unit_system_var.get()
        
        # Display Standard Info header
        std_info = "Standart: "
        if result.standard.standard_name:
            std_info += f"{result.standard.standard_name} "
        
        # Format T and P for display info
        t_c = result.standard.reference_temperature - 273.15
        p_kpa = result.standard.reference_pressure / 1000.0
        
        std_info += f"({t_c:.2f}°C, {p_kpa:.3f} kPa)"
        
        self.results_tree.insert(
            "",
            tk.END,
            values=(f"--- {std_info} ---", "", ""),
            tags=('header',)
        )
        
        # Get formatted results with selected unit system
        results_list = result.to_display_list(unit_system=unit_system)
        
        # Update KPIs
        # Reset KPIs
        for kpi in self.kpis.values():
            kpi["var"].set("-")
        
        # Find required values in display list
        for prop, val, unit in results_list:
            if "Sıkıştırılabilirlik" in prop:
                self.kpis["Z-Faktörü"]["var"].set(val)
            elif "Gerçek - ρ" in prop:
                self.kpis["Yoğunluk"]["var"].set(val)
                self.kpis["Yoğunluk"]["unit_var"].set(unit)
            elif "Mol Kütlesi" in prop:
                self.kpis["Mol Kütlesi"]["var"].set(val)
            elif "(Hacimsel)" in prop and "HHV" in prop:
                self.kpis["HHV"]["var"].set(val)
                self.kpis["HHV"]["unit_var"].set(unit)
        
        # Insert into tree
        for prop_name, value, unit in results_list:
            if prop_name.startswith('-'):
                # Header row
                self.results_tree.insert("", tk.END, values=(prop_name, value, unit), tags=('header',))
            else:
                # Normal row
                self.results_tree.insert("", tk.END, values=(prop_name, value, unit))
                
        # Update Phase Envelope
        if result.phase_envelope:
            self._plot_phase_envelope(
                result.phase_envelope, 
                result.actual.temperature, 
                result.actual.pressure
            )
        else:
            self.phase_ax.clear()
            msg = "Faz diyagramı oluşturulamadı.\n1. Karışım HEOS için uygun olmayabilir.\n2. SRK/PR algoritmaları grafiği oluşturamamış olabilir."
            self.phase_ax.text(0.5, 0.5, msg, ha='center', va='center', color='red', transform=self.phase_ax.transAxes)
            self.phase_canvas.draw()
    
    def _on_unit_change(self, event=None) -> None:
        """
        Handle unit system change event.
        
        Re-displays current results with new unit system.
        """
        if self.current_result is not None:
            # Re-display with new unit system
            self.display_results(self.current_result)
    
    def display_error(self, error_message: str, log_lines: List[str] = None) -> None:
        """
        Display error message and optional log lines.
        
        Args:
            error_message: Main error message
            log_lines: Optional list of log lines to display
        """
        self.clear_results()
        
        # Error header
        self.results_tree.insert(
            "",
            tk.END,
            values=("--- KRİTİK HESAPLAMA HATASI ---", "", ""),
            tags=('error_header',)
        )
        
        # Error message
        self.results_tree.insert(
            "",
            tk.END,
            values=("Hata Mesajı", str(error_message), "")
        )
        
        # Log lines if provided
        if log_lines:
            self.results_tree.insert(
                "",
                tk.END,
                values=("- SON HATA LOGU (İPUCU) -", "", ""),
                tags=('error_header',)
            )
            
            for line in log_lines:
                self.results_tree.insert(
                    "",
                    tk.END,
                    values=(line.strip(), "", "")
                )
    
    def clear_results(self) -> None:
        """Clear all results from tree view."""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
    
    def get_results_as_list(self) -> List[Tuple[str, str, str]]:
        """
        Get current results as list of tuples.
        
        Returns:
            List of (property, value, unit) tuples
        """
        results = []
        for item in self.results_tree.get_children():
            values = self.results_tree.item(item)['values']
            results.append(tuple(values))
        return results

    def _plot_phase_envelope(self, phase_env_data: PhaseEnvelopeData, current_t: float, current_p: float):
        """Plot phase envelope data."""
        self.phase_ax.clear()
        
        # Determine colors based on theme
        is_dark = ctk.get_appearance_mode() == "Dark"
        text_color = 'white' if is_dark else 'black'
        grid_color = '#444444' if is_dark else '#dddddd'
        
        # Convert K to C, Pa to bar for plotting
        T = np.array(phase_env_data.temperature_k) - 273.15
        p = np.array(phase_env_data.pressure_pa) / 100000.0
        
        # Operating point
        op_t = current_t - 273.15
        op_p = current_p / 100000.0
        
        # Plot full curve
        self.phase_ax.plot(T, p, 'b-', linewidth=2, label='Faz Sınırı (Çiğlenme/Kaynama)')
        
        # Plot critical point if exists
        if phase_env_data.critical_t and phase_env_data.critical_p:
            crit_t = phase_env_data.critical_t - 273.15
            crit_p = phase_env_data.critical_p / 100000.0
            self.phase_ax.plot(crit_t, crit_p, 'rD', markersize=8, label='Kritik Nokta')
            
        # Plot operating point
        self.phase_ax.plot(op_t, op_p, 'g*', markersize=12, label='İşletme Noktası')
        
        # Setup graph details
        self.phase_ax.set_title("Faz Diyagramı (Phase Envelope)", color=text_color, fontweight='bold')
        self.phase_ax.set_xlabel("Sıcaklık (°C)", color=text_color)
        self.phase_ax.set_ylabel("Basınç (bar)", color=text_color)
        self.phase_ax.grid(True, linestyle='--', color=grid_color)
        
        self.phase_ax.set_yscale("log")
        from matplotlib.ticker import ScalarFormatter
        formatter = ScalarFormatter()
        formatter.set_scientific(False)
        self.phase_ax.yaxis.set_major_formatter(formatter)
        
        legend = self.phase_ax.legend(loc='best')
        if is_dark:
            for text in legend.get_texts():
                text.set_color("black")
                
        self.phase_fig.tight_layout()
        self.phase_canvas.draw()
        
    def save_phase_envelope_plot(self, file_path: str) -> bool:
        """Save current phase envelope plot to image file."""
        try:
            # Ensure we're in a clean state for saving
            is_dark = ctk.get_appearance_mode() == "Dark"
            if is_dark:
                # Temporarily change text color to white for visibility on white PDF background
                # or just use a white background for the export
                self.phase_fig.patch.set_facecolor('white')
                self.phase_ax.set_facecolor('white')
                self.phase_ax.tick_params(colors='black')
                for spine in self.phase_ax.spines.values():
                    spine.set_edgecolor('black')
                self.phase_ax.xaxis.label.set_color('black')
                self.phase_ax.yaxis.label.set_color('black')
                self.phase_ax.title.set_color('black')
                
            self.phase_fig.savefig(file_path, dpi=150, bbox_inches='tight')
            
            # Restore theme
            if is_dark:
                bg_col = '#2b2b2b'
                fg_col = 'white'
                self.phase_fig.patch.set_facecolor(bg_col)
                self.phase_ax.set_facecolor(bg_col)
                self.phase_ax.tick_params(colors=fg_col)
                for spine in self.phase_ax.spines.values():
                    spine.set_edgecolor(fg_col)
                self.phase_ax.xaxis.label.set_color(fg_col)
                self.phase_ax.yaxis.label.set_color(fg_col)
                self.phase_ax.title.set_color(fg_col)
                self.phase_canvas.draw()
            return True
        except Exception as e:
            print(f"Error saving plot: {e}")
            return False
