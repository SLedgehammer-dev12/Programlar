"""
Input panel component.

Handles user inputs for gas composition, thermodynamic conditions, and calculation settings.
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import List, Tuple, Optional
import logging
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from natural_gas_g5.models.gas_data import GasComponent, GasMixture
from natural_gas_g5.core.exceptions import ValidationError
from natural_gas_g5.core import validators
from natural_gas_g5.core import converters
from natural_gas_g5.core.converters import VolumeUnit, convert_volume_to_m3
from natural_gas_g5.config.settings import config


class InputPanel(ctk.CTkFrame):
    """
    Input panel for gas composition and calculation parameters.
    
    Provides widgets for:
    - Gas component selection and composition
    - Temperature and pressure inputs with unit selection
    - Volume input (optional)
    - Backend method selection
    """
    
    def __init__(self, parent, gas_list: List[str], *args, **kwargs):
        """
        Initialize input panel.
        
        Args:
            parent: Parent widget
            gas_list: List of available gas names
        """
        super().__init__(parent, *args, **kwargs)
        
        self.gas_list = gas_list
        self.logger = logging.getLogger(__name__)
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create and layout all input widgets."""
        self._create_composition_section()
        self._create_standard_section()
        self._create_conditions_section()
        self._create_volume_method_section()
    
    def _create_composition_section(self):
        """Create gas composition input widgets."""
        comp_frame = ctk.CTkFrame(self)
        comp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Title
        ctk.CTkLabel(comp_frame, text="1. Gaz Kompozisyonu", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5, 0))
        
        # Layout: Left (Gas List), Right (Composition)
        paned = tk.PanedWindow(comp_frame, orient=tk.HORIZONTAL, bg="gray20", sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left Panel: Gas Selection
        left_frame = ctk.CTkFrame(paned, fg_color="transparent")
        paned.add(left_frame, minsize=200)
        
        # Search box
        ctk.CTkLabel(left_frame, text="Gaz Ara:").pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_gas_search)
        search_entry = ctk.CTkEntry(left_frame, textvariable=self.search_var)
        search_entry.pack(fill=tk.X, pady=(0, 5))
        
        # Filter toggle
        self.filter_var = ctk.BooleanVar(value=True) # True = Common, False = All
        self.filter_switch = ctk.CTkSwitch(
            left_frame, 
            text="Sadece Yaygın Gazlar", 
            variable=self.filter_var,
            font=ctk.CTkFont(size=11),
            command=self._on_gas_search
        )
        self.filter_switch.pack(anchor="w", pady=(0, 5))
        
        # Gas Listbox (fallback to standard tk.Listbox for now, CTk doesn't have a native one)
        list_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.gas_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.SINGLE,
            bg="#2b2b2b",
            fg="white",
            selectbackground="#1f538d",
            relief="flat",
            height=6
        )
        self.gas_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.gas_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.gas_listbox.configure(yscrollcommand=scrollbar.set)
        
        # Initial population
        self._update_gas_list()
        
        # Add Button
        ctk.CTkButton(
            left_frame,
            text="Ekle >>",
            command=self._on_add_gas
        ).pack(fill=tk.X, pady=5)
        
        # Right Panel: Selected Composition (Inline Editing)
        right_frame = ctk.CTkFrame(paned, fg_color="transparent")
        paned.add(right_frame, minsize=250)
        
        # Headers
        header_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=5, pady=(0, 2))
        ctk.CTkLabel(header_frame, text="Bileşen", width=120, anchor="w").pack(side=tk.LEFT)
        ctk.CTkLabel(header_frame, text="Oran (%)", width=80, anchor="w").pack(side=tk.LEFT)
        
        # Scrollable Frame for rows
        self.comp_scroll_frame = ctk.CTkScrollableFrame(right_frame, height=150)
        self.comp_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        # Dictionary to store row widgets: gas_name -> {'frame': frame, 'entry': entry, 'var': var}
        self.comp_rows = {}
        
        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=5)
        
        # Presets
        ctk.CTkLabel(btn_frame, text="Şablon:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.preset_var = tk.StringVar(value="Seçiniz...")
        preset_combo = ctk.CTkComboBox(
            btn_frame, 
            variable=self.preset_var,
            values=["Seçiniz...", "Tipik Doğal Gaz", "BOTAŞ Standardı", "Zengin Gaz (LNG)"],
            state="readonly",
            command=self._on_preset_selected,
            width=135
        )
        preset_combo.pack(side=tk.LEFT)
        
        ctk.CTkButton(
            btn_frame,
            text="Temizle",
            command=self._on_clear_all,
            fg_color="#F44336",
            hover_color="#D32F2F",
            width=60
        ).pack(side=tk.RIGHT)
        
        # Total label
        self.total_label = ctk.CTkLabel(
            comp_frame,
            text="Toplam: 0.00%",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.total_label.pack(anchor="e", padx=10, pady=(0, 5))
        
        # Fraction type selector
        type_frame = ctk.CTkFrame(comp_frame, fg_color="transparent")
        type_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ctk.CTkLabel(type_frame, text="Oran Tipi:").pack(side=tk.LEFT)
        
        self.fraction_type_var = tk.StringVar(value="molar")
        ctk.CTkRadioButton(
            type_frame,
            text="Molar %",
            variable=self.fraction_type_var,
            value="molar"
        ).pack(side=tk.LEFT, padx=10)
        
        ctk.CTkRadioButton(
            type_frame,
            text="Kütlesel %",
            variable=self.fraction_type_var,
            value="mass"
        ).pack(side=tk.LEFT)
        
        # Third Panel: Pie Chart
        pie_frame = ctk.CTkFrame(paned, fg_color="transparent")
        paned.add(pie_frame, minsize=200)
        
        self.pie_fig = Figure(figsize=(3, 3), dpi=80)
        self.pie_ax = self.pie_fig.add_subplot(111)
        
        bg_col = '#2b2b2b' if ctk.get_appearance_mode() == "Dark" else '#f0f0f0'
        self.pie_fig.patch.set_facecolor(bg_col)
        self.pie_ax.set_facecolor(bg_col)
        
        self.pie_canvas = FigureCanvasTkAgg(self.pie_fig, master=pie_frame)
        self.pie_canvas.draw()
        self.pie_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial draw
        self._update_pie_chart()

    def _create_standard_section(self):
        """Create standard condition selection widgets."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(frame, text="2. Referans Standart Koşullar", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 5))
        
        # Standard Selection
        ctk.CTkLabel(frame, text="Standart Seçimi:").grid(row=1, column=0, sticky="w", padx=10, pady=(0, 5))
        
        self.standard_var = ctk.StringVar()
        standards = list(config.STANDARD_CONDITIONS.keys()) + ["Özel..."]
        
        self.standard_combo = ctk.CTkComboBox(
            frame,
            variable=self.standard_var,
            values=standards,
            state="readonly",
            width=250,
            command=self._on_standard_change
        )
        self.standard_combo.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 5))
        self.standard_combo.set(standards[0])  # Select first (ISO)
        
        # Info label
        self.std_info_label = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.std_info_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 5))
        
        # Trigger initial update
        self._on_standard_change()

    def _create_conditions_section(self):
        """Create thermodynamic conditions input widgets."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(frame, text="3. İşletme Koşulları", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5, 5))
        
        inputs_frame = ctk.CTkFrame(frame, fg_color="transparent")
        inputs_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Temperature
        ctk.CTkLabel(inputs_frame, text="Sıcaklık:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.temp_var = tk.DoubleVar(value=15.0)
        ctk.CTkEntry(inputs_frame, textvariable=self.temp_var, width=80).grid(row=0, column=1, padx=(0, 5))
        
        self.temp_unit_var = ctk.StringVar(value="°C")
        temp_units = ["°C", "°F", "K"]
        ctk.CTkComboBox(
            inputs_frame,
            variable=self.temp_unit_var,
            values=temp_units,
            state="readonly",
            width=70
        ).grid(row=0, column=2, padx=(0, 15))
        
        # Pressure
        ctk.CTkLabel(inputs_frame, text="Basınç:").grid(row=0, column=3, sticky="w", padx=(0, 5))
        
        self.press_var = tk.DoubleVar(value=1.01325)
        ctk.CTkEntry(inputs_frame, textvariable=self.press_var, width=80).grid(row=0, column=4, padx=(0, 5))
        
        self.press_unit_var = ctk.StringVar(value="bar(a)")
        press_units = ["bar(a)", "bar(g)", "kPa", "MPa", "psi(a)", "psi(g)", "atm"]
        ctk.CTkComboBox(
            inputs_frame,
            variable=self.press_unit_var,
            values=press_units,
            state="readonly",
            width=90
        ).grid(row=0, column=5)
    
    def _create_volume_method_section(self):
        """Create volume and method selection widgets."""
        volume_frame = ctk.CTkFrame(self)
        volume_frame.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(volume_frame, text="4. Hacim ve Metot", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=(5, 5), sticky="w")
        
        # Volume (optional)
        ctk.CTkLabel(volume_frame, text="Hacim (ACM - Gerçek m³):").grid(
            row=1, column=0, padx=10, pady=(0, 5), sticky="w"
        )
        
        self.volume_entry = ctk.CTkEntry(volume_frame, width=100)
        self.volume_entry.grid(row=1, column=1, padx=(0, 5), pady=(0, 5), sticky="w")
        
        self.vol_unit_var = ctk.StringVar(value="m³")
        vol_units = [u.value for u in VolumeUnit]
        ctk.CTkComboBox(
            volume_frame,
            variable=self.vol_unit_var,
            values=vol_units,
            state="readonly",
            width=70
        ).grid(row=1, column=2, padx=(0, 10), pady=(0, 5), sticky="w")
        
        # Backend method
        ctk.CTkLabel(volume_frame, text="Yöntem:").grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")
        
        self.method = ctk.StringVar(value=config.DEFAULT_BACKEND)
        methods = config.AVAILABLE_BACKENDS
        self.method_combo = ctk.CTkComboBox(
            volume_frame,
            variable=self.method,
            values=methods,
            state="readonly",
            width=175
        )
        self.method_combo.grid(row=2, column=1, columnspan=2, padx=(0, 10), pady=(0, 10), sticky="w")

    def _get_filtered_gas_list(self):
        """Return the gas list based on the filter switch."""
        common = {
            "Methane", "Ethane", "Propane", "n-Butane", "Isobutane",
            "n-Pentane", "Isopentane", "n-Hexane", "n-Heptane", "n-Octane", "n-Nonane", "n-Decane",
            "CarbonDioxide", "Nitrogen", "HydrogenSulfide",
            "Water", "Helium", "Hydrogen", "Oxygen", "Argon", "CarbonMonoxide"
        }
        if self.filter_var.get():
            return [g for g in self.gas_list if g in common]
        return self.gas_list

    def _update_gas_list(self):
        """Update gas listbox with available gases."""
        self.gas_listbox.delete(0, tk.END)
        for gas in self._get_filtered_gas_list():
            self.gas_listbox.insert(tk.END, gas)
    
    # Event handlers
    
    def _on_gas_search(self, *args):
        """Handle gas search box key release and switch toggle."""
        search_term = self.search_var.get().lower()
        
        self.gas_listbox.delete(0, tk.END)
        base_list = self._get_filtered_gas_list()
        
        if search_term:
            filtered = [gas for gas in base_list if search_term in gas.lower()]
            for gas in filtered:
                self.gas_listbox.insert(tk.END, gas)
        else:
            for gas in base_list:
                self.gas_listbox.insert(tk.END, gas)
    
    def _on_add_gas(self):
        """Handle add gas button click."""
        selection = self.gas_listbox.curselection()
        if not selection:
            from natural_gas_g5.ui.dialogs import show_warning
            show_warning("Giriş Hatası", "Lütfen bir gaz seçin.")
            return

        gas_name = self.gas_listbox.get(selection[0])
        
        # Check for duplicates
        if gas_name in self.comp_rows:
            from natural_gas_g5.ui.dialogs import show_warning
            show_warning("Giriş Hatası", f"{gas_name} zaten ekli.")
            return

        # Calculate remaining percentage for default value
        current_total = sum(float(row['var'].get()) for row in self.comp_rows.values() if row['var'].get())
        remaining = max(0.0, 100.0 - current_total)
        default_val = f"{remaining:.4f}" if remaining > 0 else "0.0000"
        
        self._add_gas_row(gas_name, default_val)
        self._update_total_label()

    def _add_gas_row(self, gas_name: str, fraction_value: str):
        """Add a row to the composition scrollable frame."""
        row_frame = ctk.CTkFrame(self.comp_scroll_frame, fg_color="transparent")
        row_frame.pack(fill=tk.X, pady=2)
        
        # Name Label
        ctk.CTkLabel(row_frame, text=gas_name, width=120, anchor="w").pack(side=tk.LEFT)
        
        # Fraction Entry
        var = ctk.StringVar(value=fraction_value)
        var.trace_add("write", lambda *args: self._update_total_label())
        
        entry = ctk.CTkEntry(row_frame, textvariable=var, width=80)
        entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # Remove button
        def remove_row():
            self._on_remove_gas(gas_name)
            
        rm_btn = ctk.CTkButton(row_frame, text="X", width=30, fg_color="transparent", text_color="#F44336", hover_color="#303030", command=remove_row)
        rm_btn.pack(side=tk.LEFT)
        
        self.comp_rows[gas_name] = {
            'frame': row_frame,
            'entry': entry,
            'var': var
        }

    def _on_remove_gas(self, gas_name: str):
        """Handle remove gas button click."""
        if gas_name in self.comp_rows:
            self.comp_rows[gas_name]['frame'].destroy()
            del self.comp_rows[gas_name]
            self._update_total_label()

    def _on_clear_all(self):
        """Clear all gases from composition."""
        for row in list(self.comp_rows.values()):
            row['frame'].destroy()
        self.comp_rows.clear()
        self._update_total_label()
        
    def _on_preset_selected(self, choice):
        """Auto-fill gas composition based on selected preset."""
        if choice == "Seçiniz...":
            return
            
        presets = {
            "Tipik Doğal Gaz": {"Methane": 94.0, "Ethane": 4.0, "Propane": 1.0, "Nitrogen": 0.5, "CarbonDioxide": 0.5},
            "Zengin Gaz (LNG)": {"Methane": 88.0, "Ethane": 8.0, "Propane": 3.0, "n-Butane": 1.0},
            "BOTAŞ Standardı": {"Methane": 92.5, "Ethane": 5.0, "Propane": 1.5, "n-Butane": 0.5, "Nitrogen": 0.5}
        }
        
        if choice in presets:
            self._on_clear_all()
            for gas, val in presets[choice].items():
                # Ensure the gas is added even if not in the visible listbox
                self._add_gas_row(gas, str(val))
            self._update_total_label()
            
        self.preset_var.set("Seçiniz...")
        
    def _update_total_label(self):
        """Update total composition label."""
        total = 0.0
        for gas_name, row in self.comp_rows.items():
            try:
                val = float(row['var'].get() or 0)
                total += val
            except ValueError:
                pass
            
        self.total_label.configure(text=f"Toplam: {total:.4f}%")
        if abs(total - 100.0) > 0.0001:
            self.total_label.configure(text_color="#F44336") # Red
        else:
            self.total_label.configure(text_color="#4CAF50") # Green
            
        self._update_pie_chart()
            
    def _update_pie_chart(self):
        """Update pie chart representation of gas mixture."""
        self.pie_ax.clear()
        labels = []
        sizes = []
        for gas_name, row in self.comp_rows.items():
            try:
                val = float(row['var'].get().replace(',', '.') or 0)
                if val > 0.01:
                    labels.append(gas_name.split(' ')[0])
                    sizes.append(val)
            except ValueError:
                pass
        
        is_dark = ctk.get_appearance_mode() == "Dark"
        text_color = 'white' if is_dark else 'black'
        bg_col = '#2b2b2b' if is_dark else '#f0f0f0'
        
        if sum(sizes) > 0:
            wedges, texts, autotexts = self.pie_ax.pie(
                sizes, labels=labels, autopct='%1.1f%%', 
                startangle=90, textprops={'fontsize': 8}
            )
            for text in texts: text.set_color(text_color)
            for autotext in autotexts: autotext.set_color("black")
        else:
            # Empty state
            wedges, texts = self.pie_ax.pie([1], labels=["Bileşen Yok"], colors=[bg_col])
            for text in texts: text.set_color(text_color)
            
        self.pie_fig.tight_layout()
        self.pie_canvas.draw()
    
    # Public methods for getting inputs
    
    def _on_standard_change(self, event=None):
        """Handle standard selection change."""
        selected = self.standard_var.get()
        
        if selected in config.STANDARD_CONDITIONS:
            # Update info label
            params = config.STANDARD_CONDITIONS[selected]
            t_val = params["T"]
            p_val = params["P"]
            
            # Helper to format meaningful text
            t_c = t_val - 273.15
            p_kpa = p_val / 1000.0
            p_psi = p_val / 6894.76
            
            info_text = f"Referans: {t_c:.2f}°C, {p_kpa:.3f} kPa ({p_psi:.3f} psi)"
            self.std_info_label.configure(text=info_text)
            
            # Auto-update conditions if user hasn't manually modified them yet 
            # (Optional: for now we just show info, maybe we can add a checkbox "Sync conditions")
            # Or better: We set these as the "Standard" parameters that passed to calculator
        else:
            self.std_info_label.configure(text="Özel tanımlı standart koşullar")

    def get_mixture(self) -> GasMixture:
        """
        Get gas mixture from composition inputs.
        
        Returns:
            GasMixture object
            
        Raises:
            ValidationError: If composition is invalid
        """
        # Collect components
        components = []
        for gas_name, row in self.comp_rows.items():
            try:
                fraction_str = row['var'].get().replace(',', '.')
                fraction = float(fraction_str)
                components.append(GasComponent(name=gas_name, fraction=fraction))
            except ValueError:
                raise ValidationError("Gaz Kompozisyonu", f"{gas_name} için geçersiz sayısal değer.")
        
        if not components:
            raise ValidationError("Gaz Kompozisyonu", "En az bir gaz bileşeni eklemelisiniz.")
        
        # Create mixture
        mixture = GasMixture(
            components=components,
            fraction_type=self.fraction_type_var.get()
        )
        
        # Validate total
        mixture.validate_total()
        
        return mixture
    
    def get_standard_conditions(self) -> Tuple[float, float, str]:
        """
        Get selected standard conditions.
        
        Returns:
            Tuple of (Temperature K, Pressure Pa, Standard Name)
        """
        selected = self.standard_var.get()
        
        if selected in config.STANDARD_CONDITIONS:
            params = config.STANDARD_CONDITIONS[selected]
            return params["T"], params["P"], selected
        else:
            # Custom or fallback
            return config.T_STANDARD, config.P_STANDARD, "Özel"

    def get_temperature_k(self) -> float:
        """
        Get temperature in Kelvin.
        
        Returns:
            Temperature in Kelvin
            
        Raises:
            ValidationError: If temperature is invalid
        """
        try:
            val = self.temp_var.get()
            unit = self.temp_unit_var.get()
            temperature_k = converters.convert_temperature_to_K(val, unit)
            validators.validate_temperature(temperature_k)
            return temperature_k
        except Exception as e:
            if isinstance(e, ValidationError): raise
            raise ValidationError("Sıcaklık", "Geçersiz değer")
    
    def get_pressure_pa(self) -> float:
        """
        Get pressure in Pascals.
        
        Returns:
            Pressure in Pascals
            
        Raises:
            ValidationError: If pressure is invalid
        """
        try:
            val = self.press_var.get()
            unit = self.press_unit_var.get()
            pressure_pa = converters.convert_pressure_to_Pa(val, unit)
            validators.validate_pressure(pressure_pa)
            return pressure_pa
        except Exception as e:
            if isinstance(e, ValidationError): raise
            raise ValidationError("Basınç", "Geçersiz değer")
    
    def get_volume_m3(self) -> Optional[float]:
        """
        Get volume in cubic meters (optional).
        
        Returns:
            Volume in m³ or None if not provided
            
        Raises:
            ValidationError: If volume is invalid
        """
        # Assuming self.volume_entry is still the entry widget for volume
        vol_str = self.volume_entry.get().strip()
        
        if not vol_str:
            return None
            
        try:
            val = float(vol_str.replace(',', '.'))
            unit = self.vol_unit_var.get()
            
            # Convert to m3
            val_m3 = convert_volume_to_m3(val, unit)
            validators.validate_volume(val_m3)
            return val_m3
        except ValueError:
            raise ValidationError("Hacim", "Geçersiz sayısal değer")
    
    def get_backend(self) -> str:
        """
        Get selected backend.
        
        Returns:
            Backend name
            
        Raises:
            ValidationError: If backend is invalid
        """
        backend = self.method.get() # Assuming self.method is still the correct variable
        validators.validate_backend(backend)
        return backend
    
    def set_backend(self, backend: str) -> None:
        """
        Set backend selection.
        
        Args:
            backend: Backend name to set
        """
        self.method.set(backend)
    
    def get_all_inputs(self) -> dict:
        """
        Get all inputs as dictionary.
        
        Returns:
            Dictionary with all input values
        """
        standard_T, standard_P, standard_name = self.get_standard_conditions()
        volume_raw = self.volume_entry.get().strip()

        return {
            'mixture': self.get_mixture(),
            'temp_k': self.get_temperature_k(),
            'press_pa': self.get_pressure_pa(),
            'vol_m3': self.get_volume_m3(),
            'backend': self.get_backend(),
            'standard_T': standard_T,
            'standard_P': standard_P,
            'standard_name': standard_name,
            'temperature_display': f"{self.temp_var.get()} {self.temp_unit_var.get()}",
            'pressure_display': f"{self.press_var.get()} {self.press_unit_var.get()}",
            'volume_display': f"{volume_raw} {self.vol_unit_var.get()}" if volume_raw else None,
        }
    
    def get_save_data(self) -> dict:
        """
        Get all inputs in a format suitable for saving to file.
        
        Returns:
            Dictionary with serializable input values
        """
        # Collect composition
        composition = []
        for gas_name, row in self.comp_rows.items():
            try:
                fraction = float(row['var'].get().replace(',','.'))
            except: fraction = 0.0
            composition.append({
                "name": gas_name,
                "fraction": fraction
            })
        
        # Collect other settings
        data = {
            "composition": composition,
            "fraction_type": self.fraction_type_var.get(),
            "standard": self.standard_var.get(),
            "temperature": {
                "value": self.temp_var.get(),
                "unit": self.temp_unit_var.get()
            },
            "pressure": {
                "value": self.press_var.get(),
                "unit": self.press_unit_var.get()
            },
            "volume": {
                "value": self.volume_entry.get().strip(),
                "unit": self.vol_unit_var.get()
            },
            "backend": self.method.get()
        }
        
        return data
    
    def set_load_data(self, data: dict) -> None:
        """
        Load inputs from a dictionary (typically from a saved file).
        
        Args:
            data: Dictionary with saved input values
        """
        # Clear existing composition
        self._on_clear_all()
        
        # Load composition
        composition = data.get("composition", [])
        for comp in composition:
            name = comp.get("name", "")
            fraction = comp.get("fraction", 0.0)
            self._add_gas_row(name, f"{fraction:.4f}")
        
        self._update_total_label()
        
        # Load fraction type
        if "fraction_type" in data:
            self.fraction_type_var.set(data["fraction_type"])
        
        # Load standard
        if "standard" in data:
            self.standard_var.set(data["standard"])
            self._on_standard_change()
        
        # Load temperature
        if "temperature" in data:
            temp_data = data["temperature"]
            if "value" in temp_data:
                self.temp_var.set(temp_data["value"])
            if "unit" in temp_data:
                self.temp_unit_var.set(temp_data["unit"])
        
        # Load pressure
        if "pressure" in data:
            press_data = data["pressure"]
            if "value" in press_data:
                self.press_var.set(press_data["value"])
            if "unit" in press_data:
                self.press_unit_var.set(press_data["unit"])
        
        # Load volume
        if "volume" in data:
            vol_data = data["volume"]
            # Handle backward compatibility (if volume was just a string/float)
            if isinstance(vol_data, dict):
                 if "value" in vol_data and vol_data["value"]:
                     self.volume_entry.delete(0, "end")
                     self.volume_entry.insert(0, str(vol_data["value"]))
                 if "unit" in vol_data:
                     self.vol_unit_var.set(vol_data["unit"])
            elif vol_data: # Old format
                 self.volume_entry.delete(0, "end")
                 self.volume_entry.insert(0, str(vol_data))
        
        # Load backend
        if "backend" in data:
            self.method.set(data["backend"])

