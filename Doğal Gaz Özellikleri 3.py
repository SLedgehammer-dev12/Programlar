import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import threading
from datetime import datetime
import os
import re

# --- Loglama Kurulumu (UTF-8-SIG ile Windows uyumlu) ---
log_file = 'thermo_gas_calculator.log'
logging.basicConfig(
    filename=log_file,
    filemode='a',
    level=logging.INFO,
    encoding='utf-8-sig',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- CoolProp İçe Aktarma (Opsiyonel) ---
CP = None
COOLPROP_AVAILABLE = False
try:
    import CoolProp.CoolProp as CP
    COOLPROP_AVAILABLE = True
except ImportError as e:
    logging.error(f"CoolProp içe aktarılamadı: {e}")
    CP = None


class ThermoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Termodinamik Gaz Karışımı Hesaplayıcı")
        self.geometry("1000x850")
        self.load_full_gas_list()
        style = ttk.Style(self)
        style.theme_use('clam')
        input_frame = ttk.Frame(self, padding="10")
        input_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        output_frame = ttk.Frame(self, padding="10")
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.create_menu()
        self.create_input_widgets(input_frame)
        self.create_output_widgets(output_frame)
        self.create_status_bar()
        self.after(100, self.show_new_features_info)

    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Dosya", menu=file_menu)
        file_menu.add_command(label="Rapor Kaydet", command=self.generate_report)
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.quit)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Yardım", menu=help_menu)
        help_menu.add_command(label="Kullanım Kılavuzu", command=self.show_user_guide)
        help_menu.add_command(label="Hakkında", command=self.show_about)

    def show_new_features_info(self):
        info = (
            "✨ GÜNCEL SÜRÜM (4.6):\n"
            "• **HEOS Optimizasyon:** Geliştirilmiş karışım uyumluluk kontrolü\n"
            "• **Otomatik Backend Geçişi:** HEOS başarısız olursa SRK/PR'a otomatik geçiş\n"
            "• **Kararlılık:** Tüm gaz karışımları için güvenilir hesaplama\n"
            "• **Geliştirilmiş:** Aşamalı ısıl değer hesaplama sistemi\n"
            "• **Yeni:** HEOS uyumluluk analizi ve öneriler\n"
        )
        messagebox.showinfo("Güncel Bilgiler", info)

    def load_full_gas_list(self):
        self.gas_list = []
        if COOLPROP_AVAILABLE:
            try:
                fluids = CP.get_global_param_string("FluidsList")
                if fluids:
                    self.gas_list = sorted([f.strip() for f in fluids.split(',') if f.strip()])
                    logging.info(f"CoolProp'tan {len(self.gas_list)} akışkan yüklendi.")
                else:
                    raise Exception("CoolProp listesi boş döndü.")
            except Exception as e:
                logging.error(f"CoolProp akışkan listesi yüklenemedi: {e}")
        if not self.gas_list:
            self.gas_list = [
                "Methane", "Ethane", "Propane", "n-Butane", "Isobutane",
                "n-Pentane", "Isopentane", "n-Hexane", "n-Heptane", "n-Octane",
                "Nitrogen", "CarbonDioxide", "CarbonMonoxide", "HydrogenSulfide",
                "Hydrogen", "Oxygen", "Argon", "Helium", "Water", "Air",
                "Ethylene", "Propylene", "Acetylene", "Benzene", "Toluene",
                "Cyclohexane", "Neohexane", "Isooctane", "Methanol", "Ethanol",
                "Ammonia", "SulfurDioxide", "NitrousOxide", "R134a", "R22", "R410A"
            ]
            messagebox.showwarning(
                "CoolProp Uyarısı",
                "CoolProp akışkan listesi yüklenemedi.\n"
                "Genişletilmiş yedek akışkan listesi kullanılıyor."
            )

    def get_heos_supported_gases(self):
        heos_supported = [
            "Methane", "Ethane", "Propane", "n-Butane", "Isobutane",
            "Nitrogen", "CarbonDioxide", "CarbonMonoxide", "Hydrogen",
            "Oxygen", "Argon", "Water", "Helium", "Air"
        ]
        return heos_supported

    def validate_mixture_for_heos(self, components):
        heos_compatible = [g.lower() for g in self.get_heos_supported_gases()]
        incompatible = [g for g in components if g.lower() not in heos_compatible]
        return incompatible

    def create_heos_compatible_mixture(self):
        heos_compatible = [g.lower() for g in self.get_heos_supported_gases()]
        compatible_components = []
        compatible_fractions = []
        total_fraction = 0.0
        for i, gas in enumerate(self.components):
            if gas.lower() in heos_compatible:
                formatted = self.format_gas_name_for_coolprop(gas)
                compatible_components.append(formatted)
                compatible_fractions.append(self.fractions[i])
                total_fraction += self.fractions[i]
        if total_fraction > 0 and compatible_components:
            normalized = [f / total_fraction for f in compatible_fractions]
            mixture_string = '&'.join(compatible_components)
            logging.info(f"HEOS uyumlu karışım oluşturuldu: {mixture_string}")
            return mixture_string, normalized
        else:
            logging.warning("HEOS uyumlu karışım oluşturulamadı")
            return None, None

    def show_heos_compatibility_info(self, incompatible_gases, original_method):
        heos_supported = self.get_heos_supported_gases()
        info_msg = (
            "HEOS Backend Uyumluluk Bilgisi:\n"
            "HEOS backend'i aşağıdaki gazlar için tam karışım desteğine sahip değil:\n"
            f"{', '.join(incompatible_gases)}\n\n"
            "HEOS ile güvenilir çalışan gazlar:\n"
            f"{', '.join(heos_supported)}\n\n"
            "Öneriler:\n"
            "• SRK veya PR yöntemlerini kullanın (önerilir)\n"
            "• Uyumsuz gazları karışımdan çıkarın\n"
            "• Sadece HEOS destekli gazlarla çalışın\n\n"
            "SRK/PR yöntemleri daha geniş gaz yelpazesini destekler."
        )
        result = messagebox.askyesno(
            "HEOS Uyumluluk Uyarısı",
            info_msg + "\nSRK yöntemine otomatik geçiş yapılsın mı?",
            icon='warning'
        )
        if result:
            self.method.set("SRK")
            messagebox.showinfo("Backend Değişikliği",
                                f"Hesaplama {original_method} yerine SRK yöntemi ile devam edecek.")
            return "SRK"
        else:
            return "HEOS"

    def format_gas_name_for_coolprop(self, gas_name):
        # Önce boşlukları kaldır, küçük harfe çevir
        clean_name = re.sub(r'\s+', '', gas_name.strip()).lower()
        name_mapping = {
            'methane': 'Methane',
            'ethane': 'Ethane',
            'propane': 'Propane',
            'n-butane': 'n-Butane',
            'isobutane': 'Isobutane',
            'n-pentane': 'n-Pentane',
            'isopentane': 'Isopentane',
            'n-hexane': 'n-Hexane',
            'n-heptane': 'n-Heptane',
            'n-octane': 'n-Octane',
            'nitrogen': 'Nitrogen',
            'carbondioxide': 'CarbonDioxide',
            'carbonmonoxide': 'CarbonMonoxide',
            'hydrogensulfide': 'HydrogenSulfide',
            'hydrogen': 'Hydrogen',
            'oxygen': 'Oxygen',
            'argon': 'Argon',
            'helium': 'Helium',
            'water': 'Water',
            'air': 'Air',
            'ethylene': 'Ethylene',
            'propylene': 'Propylene',
            'acetylene': 'Acetylene',
            'benzene': 'Benzene',
            'toluene': 'Toluene',
            'cyclohexane': 'Cyclohexane',
            'neohexane': 'Neohexane',
            'isooctane': 'Isooctane',
            'methanol': 'Methanol',
            'ethanol': 'Ethanol',
            'ammonia': 'Ammonia',
            'sulfurdioxide': 'SulfurDioxide',
            'nitrousoxide': 'NitrousOxide'
        }
        return name_mapping.get(clean_name, gas_name)

    def create_mixture_string(self):
        formatted = [self.format_gas_name_for_coolprop(g) for g in self.components]
        return '&'.join(formatted)

    def get_heating_values_manual(self, gas_name):
        heating_values = {
            'methane': {'hhv': 55.5, 'lhv': 50.0},
            'ethane': {'hhv': 51.9, 'lhv': 47.8},
            'propane': {'hhv': 50.35, 'lhv': 46.35},
            'n-butane': {'hhv': 49.5, 'lhv': 45.75},
            'isobutane': {'hhv': 49.4, 'lhv': 45.65},
            'n-pentane': {'hhv': 49.0, 'lhv': 45.35},
            'isopentane': {'hhv': 48.8, 'lhv': 45.15},
            'n-hexane': {'hhv': 48.7, 'lhv': 45.1},
            'n-heptane': {'hhv': 48.4, 'lhv': 44.9},
            'n-octane': {'hhv': 48.2, 'lhv': 44.7},
            'hydrogen': {'hhv': 141.8, 'lhv': 119.9},
            'carbonmonoxide': {'hhv': 10.1, 'lhv': 10.1},
            'ethylene': {'hhv': 50.3, 'lhv': 47.2},
            'propylene': {'hhv': 48.9, 'lhv': 45.8},
            'acetylene': {'hhv': 49.9, 'lhv': 48.2},
            'benzene': {'hhv': 41.8, 'lhv': 40.1},
            'toluene': {'hhv': 42.5, 'lhv': 40.8},
            'methanol': {'hhv': 22.7, 'lhv': 19.9},
            'ethanol': {'hhv': 29.7, 'lhv': 26.8},
            'ammonia': {'hhv': 22.5, 'lhv': 18.6},
            'hydrogensulfide': {'hhv': 16.5, 'lhv': 15.2}
        }
        key = re.sub(r'\s+', '', gas_name.strip()).lower()
        return heating_values.get(key, {'hhv': 0, 'lhv': 0})

    def calculate_heating_values_manual_mixture(self):
        total_hhv, total_lhv = 0.0, 0.0
        valid = 0
        for i, gas in enumerate(self.components):
            vals = self.get_heating_values_manual(gas)
            if vals['hhv'] > 0:
                total_hhv += self.fractions[i] * vals['hhv']
                total_lhv += self.fractions[i] * vals['lhv']
                valid += 1
        if valid > 0:
            logging.info(f"Manuel hesaplama: {valid} bileşen, HHV: {total_hhv:.2f}, LHV: {total_lhv:.2f}")
            return total_hhv, total_lhv
        return 0, 0

    def calculate_heating_values_component_based(self, backend):
        if not COOLPROP_AVAILABLE:
            return 0, 0
        T_std, P_std = 288.15, 101325.0
        hhv_list, lhv_list = [], []
        for gas, frac in zip(self.components, self.fractions):
            try:
                gas_cp = self.format_gas_name_for_coolprop(gas)
                state = CP.AbstractState(backend, gas_cp)
                state.update(CP.PT_INPUTS, P_std, T_std)
                hhv = state.HHVmass() / 1e6 if hasattr(state, 'HHVmass') else 0
                lhv = state.LHVmass() / 1e6 if hasattr(state, 'LHVmass') else 0
                if hhv > 0 and lhv > 0:
                    hhv_list.append(frac * hhv)
                    lhv_list.append(frac * lhv)
                else:
                    logging.warning(f"{gas}: HHV/LHV CoolProp tarafından desteklenmiyor.")
            except Exception as e:
                logging.warning(f"{gas} bileşeni için ısıl değer hatası: {e}")
                continue
        if hhv_list and lhv_list:
            return sum(hhv_list), sum(lhv_list)
        return 0, 0

    def calculate_heating_values_staged(self, state_std, mixture_string, backend):
        hhv, lhv = 0, 0
        method_used = "Hesaplanamadı"

        # Aşama 1: Manuel tablo (öncelikli)
        hhv, lhv = self.calculate_heating_values_manual_mixture()
        if hhv > 0 and lhv > 0:
            method_used = "Manuel tablo"
            return hhv, lhv, method_used

        # Aşama 2: Bileşen bazlı (CoolProp varsa)
        if COOLPROP_AVAILABLE:
            hhv, lhv = self.calculate_heating_values_component_based(backend)
            if hhv > 0 and lhv > 0:
                method_used = "Bileşen bazlı"
                return hhv, lhv, method_used

        # Aşama 3: Yerleşik (HEOS için)
        if COOLPROP_AVAILABLE and backend == "HEOS":
            try:
                hhv = state_std.HHVmass() / 1e6
                lhv = state_std.LHVmass() / 1e6
                if hhv > 0 and lhv > 0:
                    method_used = "CoolProp yerleşik"
                    return hhv, lhv, method_used
            except Exception as e:
                logging.warning(f"Yerleşik HHV/LHV hatası: {e}")

        return hhv, lhv, method_used

    # --- UI ve Hesaplama Fonksiyonları (validate_inputs, create_input_widgets, vs.) ---
    # (Aşağıdaki fonksiyonlar orijinaldeki gibi, sadece CoolProp kontrolü eklendi)

    def create_input_widgets(self, parent):
        comp_frame = ttk.LabelFrame(parent, text="Gaz Kompozisyonu", padding="10")
        comp_frame.pack(fill=tk.X, pady=5)
        ttk.Label(comp_frame, text="Gaz Ara:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.gas_search = ttk.Entry(comp_frame, width=22)
        self.gas_search.grid(row=0, column=1, padx=5, pady=5)
        self.gas_search.bind('<KeyRelease>', self.filter_gas_list)
        ttk.Label(comp_frame, text="Gaz Seçin:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.gas_selector = ttk.Combobox(comp_frame, values=self.gas_list, state="normal", width=22)
        self.gas_selector.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(comp_frame, text="Yüzde [%]:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.fraction_entry = ttk.Entry(comp_frame, width=10)
        self.fraction_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.fraction_type = tk.StringVar(value="molar")
        ttk.Radiobutton(comp_frame, text="Molar", variable=self.fraction_type, value="molar").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(comp_frame, text="Kütlesel", variable=self.fraction_type, value="mass").grid(row=3, column=1, padx=5, pady=2, sticky="w")
        add_button = ttk.Button(comp_frame, text="Ekle", command=self.add_gas)
        add_button.grid(row=4, column=0, padx=5, pady=10)
        remove_button = ttk.Button(comp_frame, text="Seçileni Sil", command=self.remove_gas)
        remove_button.grid(row=4, column=1, padx=5, pady=10)
        cols = ("Gaz", "Yüzde [%]")
        self.composition_tree = ttk.Treeview(comp_frame, columns=cols, show="headings", height=8)
        for col in cols:
            self.composition_tree.heading(col, text=col)
            self.composition_tree.column(col, width=130)
        self.composition_tree.grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.composition_tree.bind("<Double-1>", self.on_double_click_composition)

        conditions_frame = ttk.LabelFrame(parent, text="Durum Koşulları", padding="10")
        conditions_frame.pack(fill=tk.X, pady=10)
        ttk.Label(conditions_frame, text="Sıcaklık:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.temp_entry = ttk.Entry(conditions_frame, width=12)
        self.temp_entry.grid(row=0, column=1, padx=5, pady=5)
        self.temp_unit = tk.StringVar(value="K")
        temp_units = ["K", "°C", "°F"]
        self.temp_unit_combo = ttk.Combobox(conditions_frame, textvariable=self.temp_unit, values=temp_units, state="readonly", width=6)
        self.temp_unit_combo.grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(conditions_frame, text="Basınç:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.press_entry = ttk.Entry(conditions_frame, width=12)
        self.press_entry.grid(row=1, column=1, padx=5, pady=5)
        self.press_unit = tk.StringVar(value="kPa")
        press_units = ["kPa", "bar(a)", "bar(g)", "psi(a)", "psi(g)", "MPa", "atm"]
        self.press_unit_combo = ttk.Combobox(conditions_frame, textvariable=self.press_unit, values=press_units, state="readonly", width=8)
        self.press_unit_combo.grid(row=1, column=2, padx=5, pady=5)

        volume_frame = ttk.LabelFrame(parent, text="Hacim Bilgisi (Opsiyonel: ACM → SCM @ 15°C, 101.325 kPa)", padding="10")
        volume_frame.pack(fill=tk.X, pady=10)
        ttk.Label(volume_frame, text="Hacim (ACM):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.volume_entry = ttk.Entry(volume_frame, width=12)
        self.volume_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(volume_frame, text="m³").grid(row=0, column=2, padx=5, pady=5, sticky="w")

        method_frame = ttk.LabelFrame(parent, text="Hesaplama Yöntemi", padding="10")
        method_frame.pack(fill=tk.X, pady=10)
        ttk.Label(method_frame, text="Yöntem:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.method = tk.StringVar(value="HEOS")
        methods = ["HEOS", "SRK", "PR"]
        self.method_combo = ttk.Combobox(method_frame, textvariable=self.method, values=methods, state="readonly", width=15)
        self.method_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        button_style = ttk.Style()
        button_style.configure("Accent.TButton", foreground="white", background="blue")
        self.calc_button = ttk.Button(parent, text="Hesapla", command=self.start_calculation, style="Accent.TButton")
        self.calc_button.pack(pady=20, fill=tk.X, ipady=5)

    def filter_gas_list(self, event=None):
        search_term = self.gas_search.get().lower()
        if search_term:
            filtered = [gas for gas in self.gas_list if search_term in gas.lower()]
            self.gas_selector['values'] = filtered
            if filtered:
                self.gas_selector.set(filtered[0])
        else:
            self.gas_selector['values'] = self.gas_list

    def on_double_click_composition(self, event):
        region = self.composition_tree.identify("region", event.x, event.y)
        if region != "cell": return
        column = self.composition_tree.identify_column(event.x)
        if column != "#2": return
        item = self.composition_tree.identify_row(event.y)
        if not item: return
        current_value = self.composition_tree.item(item, "values")[1]
        column_box = self.composition_tree.bbox(item, column)
        edit_entry = ttk.Entry(self.composition_tree)
        edit_entry.place(x=column_box[0], y=column_box[1], width=column_box[2], height=column_box[3])
        edit_entry.insert(0, current_value)
        edit_entry.select_range(0, tk.END)
        edit_entry.focus()
        def save_edit(event=None):
            new_val = edit_entry.get().strip().replace(',', '.')
            try:
                frac = float(new_val)
                if frac <= 0 or frac > 100:
                    raise ValueError("Yüzde 0-100 arasında olmalıdır.")
                values = list(self.composition_tree.item(item, "values"))
                values[1] = f"{frac:.4f}"
                self.composition_tree.item(item, values=values)
            except ValueError as e:
                messagebox.showwarning("Geçersiz Değer", str(e))
            finally:
                edit_entry.destroy()
        edit_entry.bind("<Return>", save_edit)
        edit_entry.bind("<FocusOut>", save_edit)

    def create_output_widgets(self, parent):
        results_frame = ttk.LabelFrame(parent, text="Hesaplama Sonuçları", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("Özellik", "Değer", "Birim")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show="headings", height=25)
        self.results_tree.heading("Özellik", text="Özellik")
        self.results_tree.heading("Değer", text="Değer")
        self.results_tree.heading("Birim", text="Birim")
        self.results_tree.column("Özellik", width=230)
        self.results_tree.column("Değer", width=160)
        self.results_tree.column("Birim", width=100)
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        report_button = ttk.Button(parent, text="Sonuçları Raporla (.txt)", command=self.generate_report)
        report_button.pack(pady=10, fill=tk.X, ipady=5)

    def create_status_bar(self):
        self.status_var = tk.StringVar(value="Hazır.")
        status_frame = ttk.Frame(self)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=2)
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate', length=100)

    def add_gas(self):
        gas = self.gas_selector.get().strip()
        if not gas:
            messagebox.showwarning("Giriş Hatası", "Lütfen bir gaz seçin.")
            return
        fraction_str = self.fraction_entry.get().replace(',', '.')
        if not fraction_str:
            messagebox.showwarning("Giriş Hatası", "Lütfen yüzde değeri girin.")
            return
        try:
            fraction = float(fraction_str)
            if fraction <= 0 or fraction > 100:
                raise ValueError("Yüzde 0 ile 100 arasında olmalıdır.")
        except ValueError as e:
            messagebox.showwarning("Giriş Hatası", f"Geçersiz yüzde değeri: {e}")
            return
        for item in self.composition_tree.get_children():
            existing_gas = self.composition_tree.item(item)['values'][0].strip()
            if existing_gas.lower() == gas.lower():
                messagebox.showwarning("Uyarı", f"{gas} zaten listede. Değiştirmek için önce silin.")
                return
        self.composition_tree.insert("", tk.END, values=(gas, f"{fraction:.4f}"))
        self.fraction_entry.delete(0, tk.END)
        self.gas_search.delete(0, tk.END)
        self.filter_gas_list()

    def remove_gas(self):
        selected_items = self.composition_tree.selection()
        if not selected_items:
            messagebox.showwarning("Seçim Hatası", "Lütfen silmek için tablodan bir gaz seçin.")
            return
        for item in selected_items:
            self.composition_tree.delete(item)

    def convert_temperature_to_K(self, value, unit):
        if unit == "K":
            return value
        elif unit == "°C":
            return value + 273.15
        elif unit == "°F":
            return (value - 32) * 5/9 + 273.15
        else:
            raise ValueError("Geçersiz sıcaklık birimi")

    def convert_pressure_to_Pa(self, value, unit):
        P_ATM_BAR = 1.01325
        P_ATM_PSI = 14.6959
        if unit == "kPa":
            return value * 1000
        elif unit == "bar(a)":
            return value * 1e5
        elif unit == "bar(g)":
            return (value + P_ATM_BAR) * 1e5
        elif unit == "psi(a)":
            return value * 6894.76
        elif unit == "psi(g)":
            return (value + P_ATM_PSI) * 6894.76
        elif unit == "MPa":
            return value * 1e6
        elif unit == "atm":
            return value * 101325.0
        else:
            raise ValueError("Geçersiz basınç birimi")

    def validate_numeric_input(self, value_str, field_name, min_val=None, max_val=None, allow_zero=False):
        if not value_str.strip():
            raise ValueError(f"{field_name} boş olamaz.")
        try:
            value = float(value_str.replace(',', '.'))
        except ValueError:
            raise ValueError(f"{field_name} geçerli bir sayı olmalıdır.")
        if min_val is not None and value < min_val:
            raise ValueError(f"{field_name} {min_val}'den küçük olamaz.")
        if max_val is not None and value > max_val:
            raise ValueError(f"{field_name} {max_val}'den büyük olamaz.")
        if not allow_zero and value == 0:
            raise ValueError(f"{field_name} sıfır olamaz.")
        return value

    def validate_inputs(self):
        self.components = []
        self.fractions = []
        total_fraction = 0.0
        items = self.composition_tree.get_children()
        if not items:
            raise ValueError("Gaz kompozisyonu boş olamaz. En az bir gaz ekleyin.")
        if len(items) > 20:
            raise ValueError("Maksimum 20 gaz eklenebilir.")
        gas_names = []
        for item in items:
            values = self.composition_tree.item(item)['values']
            gas_name = values[0].strip()
            if not gas_name:
                raise ValueError("Gaz ismi boş olamaz.")
            if gas_name.lower() in [g.lower() for g in gas_names]:
                raise ValueError(f"{gas_name} gazı birden fazla eklenemez.")
            gas_names.append(gas_name)
            self.components.append(gas_name)
            fraction = self.validate_numeric_input(values[1], "Gaz yüzdesi", 0.0001, 100)
            self.fractions.append(fraction)
            total_fraction += fraction
        if abs(total_fraction - 100.0) > 1e-4:
            raise ValueError(f"Gaz yüzdelerinin toplamı 100 olmalıdır. Mevcut toplam: {total_fraction:.4f}")
        self.fractions = [f / 100.0 for f in self.fractions]

        temp_str = self.temp_entry.get().strip()
        if not temp_str:
            raise ValueError("Sıcaklık değeri boş olamaz.")
        temp_val = self.validate_numeric_input(temp_str, "Sıcaklık", -273.15, 5000)
        self.temp_k = self.convert_temperature_to_K(temp_val, self.temp_unit.get())
        if self.temp_k <= 0.1:
            raise ValueError("Sıcaklık mutlak sıfıra çok yakın (≤ 0.1K).")
        if self.temp_k > 5000:
            raise ValueError("Sıcaklık çok yüksek (> 5000K).")

        press_str = self.press_entry.get().strip()
        if not press_str:
            raise ValueError("Basınç değeri boş olamaz.")
        press_val = self.validate_numeric_input(press_str, "Basınç", 1e-10, 1e9)
        self.press_pa = self.convert_pressure_to_Pa(press_val, self.press_unit.get())
        if self.press_pa <= 0:
            raise ValueError("Basınç pozitif olmalıdır.")
        if self.press_pa > 1e9:
            raise ValueError("Basınç çok yüksek (> 10000 bar).")

        self.volume_actual = None
        vol_str = self.volume_entry.get().strip()
        if vol_str:
            self.volume_actual = self.validate_numeric_input(vol_str, "Hacim", 1e-10, 1e9)

        if self.method.get() not in ["HEOS", "SRK", "PR"]:
            raise ValueError("Geçersiz hesaplama yöntemi.")
        return True

    def start_calculation(self):
        try:
            self.validate_inputs()
        except ValueError as e:
            messagebox.showerror("Giriş Hatası", str(e))
            return

        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.calc_button.config(state="disabled")

        original_method = self.method.get()
        if original_method == "HEOS":
            incompatible = self.validate_mixture_for_heos(self.components)
            if incompatible:
                selected = self.show_heos_compatibility_info(incompatible, original_method)
                if selected != "HEOS":
                    self.method.set(selected)

        self.status_var.set("Hesaplanıyor... Lütfen bekleyin.")
        self.progress_bar.pack(side=tk.RIGHT, padx=5)
        self.progress_bar.start()

        calc_thread = threading.Thread(target=self.run_calculation_with_fallback)
        calc_thread.daemon = True
        calc_thread.start()

    def run_calculation_with_fallback(self):
        if not COOLPROP_AVAILABLE:
            self.after(100, self.show_coolprop_missing_error)
            return

        backends = [self.method.get(), "SRK", "PR"]
        final_results, used_backend = None, None
        for backend in backends:
            try:
                self.status_var.set(f"{backend} ile hesaplanıyor...")
                logging.info(f"{backend} deneniyor...")
                results = self.run_calculation_with_backend(backend)
                if results:
                    final_results, used_backend = results, backend
                    break
            except Exception as e:
                logging.warning(f"{backend} başarısız: {e}")
                if backend == self.method.get():
                    self.after(100, lambda msg=str(e), b=backend: self.show_backend_fallback_info(msg, b))
                continue

        if final_results:
            self.after(100, lambda res=final_results, ub=used_backend: self.update_ui_with_results(res, ub))
        else:
            self.after(100, lambda: self.show_calculation_error("Tüm yöntemler başarısız oldu."))

    def show_coolprop_missing_error(self):
        self.calc_button.config(state="normal")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.status_var.set("CoolProp eksik!")
        messagebox.showerror("Bağımlılık Hatası", "CoolProp kurulu değil. Lütfen 'pip install CoolProp' komutuyla yükleyin.")

    def run_calculation_with_backend(self, backend):
        if backend == "HEOS":
            mixture, fractions = self.create_heos_compatible_mixture()
            if not mixture:
                raise ValueError("HEOS ile uyumlu karışım yok.")
        else:
            mixture = self.create_mixture_string()
            fractions = self.fractions

        # Karışım testi
        test_state = CP.AbstractState(backend, mixture)
        logging.info(f"Karışım geçerli ({backend}): {mixture}")

        # Gerçek koşullar
        state = CP.AbstractState(backend, mixture)
        if self.fraction_type.get() == 'molar':
            state.set_mole_fractions(fractions)
        else:
            state.set_mass_fractions(fractions)
        state.update(CP.PT_INPUTS, self.press_pa, self.temp_k)

        results = []
        density_actual = state.rhomass()
        results.append(("- GERÇEK KOŞULLAR SONUÇLARI -", "", ""))
        results.append(("Hesaplama Yöntemi", backend, ""))
        results.append(("Yoğunluk (Gerçek)", f"{density_actual:.4f}", "kg/m³"))
        results.append(("Mol Kütlesi (Karışım)", f"{state.molar_mass():.4f}", "kg/mol"))
        results.append(("Sıkıştırılabilirlik Faktörü (Z)", f"{state.compressibility_factor():.5f}", "-"))
        results.append(("İç Enerji", f"{state.umass() / 1000:.4f}", "kJ/kg"))
        results.append(("Entalpi", f"{state.hmass() / 1000:.4f}", "kJ/kg"))
        results.append(("Entropi", f"{state.smass() / 1000:.4f}", "kJ/(kg·K)"))
        results.append(("Cp", f"{state.cpmass() / 1000:.4f}", "kJ/(kg·K)"))
        results.append(("Cv", f"{state.cvmass() / 1000:.4f}", "kJ/(kg·K)"))
        try:
            k_val = state.cpmass() / state.cvmass()
            results.append(("İzotropik Üs (k)", f"{k_val:.4f}", "-"))
        except:
            results.append(("İzotropik Üs (k)", "Hesaplanamadı", "-"))

        # Standart koşullar (15°C, 101.325 kPa)
        T_std, P_std = 288.15, 101325.0
        state_std = CP.AbstractState(backend, mixture)
        if self.fraction_type.get() == 'molar':
            state_std.set_mole_fractions(fractions)
        else:
            state_std.set_mass_fractions(fractions)
        state_std.update(CP.PT_INPUTS, P_std, T_std)
        rho_std = state_std.rhomass()
        rho_air = CP.PropsSI('D', 'T', T_std, 'P', P_std, 'air')
        sg = rho_std / rho_air

        results.append(("- STANDART ÇEVRİM BİLGİLERİ (SCM @ 15°C, 101.325 kPa) -", "", ""))
        results.append(("Standart Koşullar", f"{T_std} K, {P_std/1000} kPa", "-"))
        results.append(("Yoğunluk (SCM)", f"{rho_std:.4f}", "kg/Sm³"))
        results.append(("Bağıl Yoğunluk (Hava=1)", f"{sg:.4f}", "-"))

        # Isıl değerler
        hhv, lhv, calc_method = self.calculate_heating_values_staged(state_std, mixture, backend)
        results.append(("- ISIL DEĞERLER (SCM) -", "", ""))
        results.append(("Hesaplama Yöntemi", calc_method, ""))
        if hhv > 0:
            results.append(("Üst Isıl Değer (HHV)", f"{hhv:.4f}", "MJ/kg (SCM)"))
            results.append(("Alt Isıl Değer (LHV)", f"{lhv:.4f}", "MJ/kg (SCM)"))
            hhv_vol = hhv * rho_std
            wobbe = hhv_vol / (sg ** 0.5)
            results.append(("Wobbe İndeksi", f"{wobbe:.2f}", "MJ/Sm³"))
        else:
            results.append(("Üst Isıl Değer (HHV)", "Hesaplanamadı", "-"))
            results.append(("Alt Isıl Değer (LHV)", "Hesaplanamadı", "-"))
            results.append(("Wobbe İndeksi", "Hesaplanamadı (HHV yok)", "-"))

        # Hacim dönüşümü
        if self.volume_actual is not None:
            mass = density_actual * self.volume_actual
            vol_std = mass / rho_std
            results.append(("- HACİM DÖNÜŞÜMÜ -", "", ""))
            results.append(("Girilen Hacim (ACM)", f"{self.volume_actual:.4f}", "m³"))
            results.append(("Standart Hacim (SCM)", f"{vol_std:.4f}", "Sm³"))

        return results

    def show_backend_fallback_info(self, error_message, failed_backend):
        info_msg = f"{failed_backend} backend'i başarısız oldu:\n{error_message}\nProgram otomatik olarak alternatif bir yöntem deneyecek."
        messagebox.showwarning("Backend Değişikliği", info_msg)

    def update_ui_with_results(self, results, used_backend):
        self.calc_button.config(state="normal")
        for res in results:
            self.results_tree.insert("", tk.END, values=res)
        if used_backend != self.method.get():
            self.status_var.set(f"Hesaplama tamamlandı. ({self.method.get()} yerine {used_backend} kullanıldı)")
            messagebox.showinfo("Backend Değişikliği", f"Hesaplama {used_backend} yöntemi ile tamamlandı.\n({self.method.get()} uyumlu değildi)")
        else:
            self.status_var.set("Hesaplama tamamlandı.")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

    def show_calculation_error(self, error):
        self.calc_button.config(state="normal")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.status_var.set("Hesaplama hatası oluştu. Log sonuçlara eklendi.")
        error_results = [
            ("--- HESAPLAMA HATASI ---", "", ""),
            ("Hata Mesajı", str(error), ""),
        ]
        log_lines = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
                    log_lines = lines[-10:]
            except Exception as e_log:
                log_lines = [f"Log okunamadı: {e_log}"]
        if log_lines:
            error_results.append(("- SON HATA LOGU -", "", ""))
            for line in log_lines:
                error_results.append((line.strip(), "", ""))
        for res in error_results:
            self.results_tree.insert("", tk.END, values=res)
        messagebox.showerror("Hesaplama Hatası", f"Hesaplama sırasında kritik bir hata oluştu:\n{error}\nDetaylar için Sonuçlar Tablosunu kontrol edin.")

    def generate_report(self):
        if not self.results_tree.get_children():
            messagebox.showwarning("Rapor Hatası", "Önce bir hesaplama yapmalısınız.")
            return
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Metin Dosyaları", "*.txt")],
                title="Raporu Kaydet"
            )
            if not file_path:
                return
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write("="*60 + "\n")
                f.write(" TERMODİNAMİK GAZ KARIŞIMI HESAPLAMA RAPORU (Kompresör Pompa)\n")
                f.write(f" Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*60 + "\n")
                f.write("--- GİRİLEN PARAMETRELER ---\n")
                f.write(f"Sıcaklık: {self.temp_entry.get()} {self.temp_unit.get()}\n")
                f.write(f"Basınç: {self.press_entry.get()} {self.press_unit.get()}\n")
                f.write(f"Hesaplama Yöntemi: {self.method.get()}\n")
                vol = self.volume_entry.get().strip()
                if vol:
                    f.write(f"Hacim (ACM): {vol} m³\n")
                f.write(f"Kompozisyon Tipi: {self.fraction_type.get().capitalize()}\n")
                f.write("Gaz Kompozisyonu:\n")
                for item in self.composition_tree.get_children():
                    values = self.composition_tree.item(item)['values']
                    f.write(f"  - {values[0]}: {values[1]} %\n")
                f.write("\n")
                f.write("--- HESAPLAMA SONUÇLARI ---\n")
                f.write(f"{'Özellik':<35} | {'Değer':<20} | {'Birim'}\n")
                f.write("-"*70 + "\n")
                for item in self.results_tree.get_children():
                    values = self.composition_tree.item(item)['values']
                    f.write(f"{values[0]:<35} | {values[1]:<20} | {values[2]}\n")
            messagebox.showinfo("Başarılı", f"Rapor başarıyla kaydedildi:\n{file_path}")
            self.status_var.set(f"Rapor kaydedildi: {file_path}")
        except Exception as e:
            logging.error(f"Rapor oluşturma hatası: {e}")
            messagebox.showerror("Rapor Hatası", f"Rapor kaydedilirken bir hata oluştu:\n{e}")

    def show_about(self):
        about_text = """
Termodinamik Gaz Karışımı Hesaplayıcı - Sürüm 4.6 (Kompresör Pompa)
Bu program, CoolProp kütüphanesini kullanarak gaz karışımlarının
termodinamik özelliklerini hesaplar. Amacı, doğal gaz/petrol sektöründe 
sıkça kullanılan, kompresör ve pompa tasarımları için kritik olan 
özellikleri sağlamaktır.
--- GELİŞTİRİLMİŞ HEOS DESTEĞİ ---
• **HEOS Uyumluluk Kontrolü:** Karışım HEOS ile uyumlu değilse otomatik tespit
• **Otomatik Backend Geçişi:** HEOS başarısız olursa SRK/PR'a otomatik geçiş
• **Akıllı Karışım Optimizasyonu:** HEOS için uyumlu alt karışım oluşturma
• **Kapsamlı Hata Yönetimi:** Tüm backend'ler için geliştirilmiş hata işleme
--- HESAPLAMA YÖNTEMLERİ ---
• **HEOS (Helmholtz Eşitliği):** En doğru yöntem, sınırlı gaz desteği
• **SRK (Soave-Redlich-Kwong):** Geniş gaz yelpazesi, yüksek güvenilirlik  
• **PR (Peng-Robinson):** SRK benzeri, alternatif kübik denklem
HEOS ile güvenilir çalışan gazlar: Metan, Etan, Propan, Bütan, Azot, CO2, Hidrojen
"""
        messagebox.showinfo("Hakkında", about_text)

    def show_user_guide(self):
        guide_text = """
KULLANIM KILAVUZU - GELİŞTİRİLMİŞ HEOS DESTEĞİ
1. HEOS Backend Seçimi:
   - HEOS'u seçtiğinizde program otomatik uyumluluk kontrolü yapar
   - Uyumsuz gazlar varsa SRK'ya geçiş önerilir
   - HEOS sadece temel doğal gaz bileşenleriyle güvenilir çalışır
2. Otomatik Backend Geçişi:
   - HEOS başarısız olursa program otomatik SRK/PR'a geçer
   - Kullanılan yöntem sonuçlarda belirtilir
   - Hiçbir yöntem çalışmazsa detaylı hata raporu sunulur
3. Önerilen Gaz Kombinasyonları:
   - HEOS için: Metan, Etan, Propan, Bütan, Azot, CO2 kombinasyonları
   - SRK/PR için: Tüm gazlar desteklenir
   - Karışımlarda maksimum 8-10 gaz kullanılması önerilir
4. Performans ve Doğruluk:
   - HEOS: En doğru, sınırlı gaz desteği
   - SRK: Yüksek doğruluk, geniş gaz desteği  
   - PR: SRK'ya alternatif, benzer performans
"""
        messagebox.showinfo("Kullanım Kılavuzu", guide_text)


if __name__ == "__main__":
    app = ThermoApp()
    app.mainloop()