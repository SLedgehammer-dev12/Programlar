import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math
import CoolProp.CoolProp as CP
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import numpy as np
import time 

# R: Evrensel Gaz Sabiti [J/(mol*K)]
R_J_mol_K = 8.314462618
MIN_PRESSURE_PA = 1000.0 # Mutlak minimum basınç (1000 Pa)

class GasFlowCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gaz Akış ve Boru Tasarım Hesaplayıcısı (Kompresör Pompa Uzmanlığı)")
        self.root.geometry("1450x950")
        self.root.minsize(1050, 750)

        self.gas_components = {}
        self.viscosity_fallback_warning = False
        self.log_queue = queue.Queue() 

        # 🟢 Düzeltme 1: Eksik öznitelikler tanımlandı (Önceki hatanın çözümü).
        self.fitting_counts = {} 
        self.ball_valve_kv = tk.DoubleVar(value=0.0)
        self.ball_valve_cv = tk.DoubleVar(value=0.0)

        # Style tanımla
        self.style = ttk.Style()
        self.style.configure("Bold.TLabelframe", font=("Arial", 11, "bold"))
        self.style.configure("Bold.TLabelframe.Label", font=("Arial", 11, "bold"))
        
        # Fontlar
        self.label_font_bold = ("Arial", 11, "bold")
        self.label_font_normal = ("Arial", 11)

        # --- Temel Veri ve Materyal Tanımları ---
        self.coolprop_gases = {
            "METHANE": "Methane (CH₄)", "ETHANE": "Ethane (C₂H₆)", "PROPANE": "Propane (C₃H₈)", 
            "ISOBUTANE": "Isobutane (i-C₄H₁₀)", "BUTANE": "n-Butane (n-C₄H₁₀)", "ISOPENTANE": "Isopentane (i-C₅H₁₂)", 
            "PENTANE": "n-Pentane (n-C₅H₁₂)", "HEXANE": "n-Hexane (C₆H₁₄)", "HEPTANE": "n-Heptane (C₇H₁₆)", 
            "OCTANE": "n-Octane (C₈H₁₈)", "NITROGEN": "Nitrogen (N₂)", "OXYGEN": "Oxygen (O₂)", 
            "CARBONDIOXIDE": "Carbon Dioxide (CO₂)", "WATER": "Water (H₂O)", "HYDROGENSULFIDE": "Hydrogen Sulfide (H₂S)", 
            "HELIUM": "Helium (He)", "AIR": "Air", "ARGON": "Argon (Ar)", "KRYPTON": "Krypton (Kr)", "XENON": "Xenon (Xe)"
        }
        self.pipe_materials = {
            "API 5L Grade B": 241, "API 5L X42": 290, "API 5L X52": 359, "API 5L X60": 414, 
            "API 5L X65": 448, "API 5L X70": 483, "ASTM A53 Grade B": 241, "ASTM A106 Grade B": 241,
            "ASTM A312 TP316L": 210, "ASTM A335 P11": 205
        }
        self.pipe_roughness = {
            "API 5L Grade B": 0.0457e-3, "API 5L X42": 0.0457e-3, "API 5L X52": 0.0457e-3, "API 5L X60": 0.0457e-3,
            "API 5L X65": 0.0457e-3, "API 5L X70": 0.0457e-3, "ASTM A53 Grade B": 0.0457e-3, "ASTM A106 Grade B": 0.0457e-3,
            "ASTM A312 TP316L": 0.0015e-3, "ASTM A335 P11": 0.0457e-3
        }
        self.fitting_k_factors = {
            "90° Dirsek": 0.3, "45° Dirsek": 0.2, "30° Dirsek": 0.15, "60° Dirsek": 0.25, "180° Dirsek": 0.5,
            "Tee (Doğrudan)": 0.4, "Tee (Yan Dal)": 1.5, "Küresel Vana (Tam Açık)": 0.05,
            "Globe Vana (Tam Açık)": 6.0, "Gate Vana (Tam Açık)": 0.15, "Check Valve": 2.0
        }

        self.asme_b36_10m = self.load_asme_b36_10m_data()

        # Validasyon
        self.validate_float_positive = self.root.register(self.validate_float_positive_func)
        self.validate_int_positive = self.root.register(self.validate_int_positive_func)

        # --- Ana Sekme Kontrolü ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Ana Giriş Sekmesi
        main_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.notebook.add(main_tab, text="Giriş / Hesaplama")
        main_tab.grid_columnconfigure(0, weight=3)
        main_tab.grid_columnconfigure(1, weight=1)
        main_tab.grid_rowconfigure(0, weight=1)

        # Log Sekmesi
        log_tab = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.notebook.add(log_tab, text="Program Logları")
        log_tab.grid_columnconfigure(0, weight=1)
        log_tab.grid_rowconfigure(0, weight=1)
        self.create_log_widgets(log_tab) 

        # Sol taraf: Girdiler
        input_controls_frame = ttk.Frame(main_tab)
        input_controls_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        self.create_input_widgets(input_controls_frame)

        # Sağ taraf: Rapor
        report_frame = ttk.Frame(main_tab)
        report_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=5)
        self.create_report_widgets(report_frame)
        
        # Alt Butonlar (Yardım ve Hakkında)
        self.create_info_buttons()
        
        self.log_message("PROGRAM BAŞLATILDI: Kompresör Pompa Hesaplayıcısı")
        # 🟢 Düzeltme 2: __version__ hatası CoolProp.get_global_param_string('version') ile giderildi.
        self.log_message(f"Termodinamik Kütüphanesi: CoolProp v{CP.get_global_param_string('version')}")
        self.log_message("Kullanılan ASME B36.10M verisi yüklendi.")
        
    def create_info_buttons(self):
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky="ew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        ttk.Button(button_frame, text="Yardım (Kullanım Kılavuzu)", command=self.show_help).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Button(button_frame, text="Hakkında (Formüller & Referans)", command=self.show_about).grid(row=0, column=1, padx=5, pady=5, sticky="w")


    def load_asme_b36_10m_data(self):
        # Kullanıcı tarafından sağlanan güncel ve eksiksiz ASME B36.10M verisi
        return {
            "1/8": {"OD_mm": 10.29, "schedules": {"10": 1.24, "30": 1.45, "STD": 1.73, "40": 1.73, "XS": 2.41, "80": 2.41, "160": 3.15, "XXS": 4.83}},
            "1/4": {"OD_mm": 13.72, "schedules": {"10": 1.65, "30": 1.85, "STD": 2.24, "40": 2.24, "XS": 3.02, "80": 3.02, "160": 3.68, "XXS": 6.05}},
            "3/8": {"OD_mm": 17.14, "schedules": {"10": 1.65, "30": 1.85, "STD": 2.31, "40": 2.31, "XS": 3.20, "80": 3.20, "160": 4.01, "XXS": 6.40}},
            "1/2": {"OD_mm": 21.34, "schedules": {"5": 1.65, "10": 2.11, "30": 2.41, "STD": 2.77, "40": 2.77, "XS": 3.73, "80": 3.73, "160": 4.78, "XXS": 7.47}},
            "3/4": {"OD_mm": 26.67, "schedules": {"5": 1.65, "10": 2.11, "30": 2.41, "STD": 2.87, "40": 2.87, "XS": 3.91, "80": 3.91, "160": 5.56, "XXS": 7.82}},
            "1": {"OD_mm": 33.40, "schedules": {"5": 1.65, "10": 2.77, "30": 2.90, "STD": 3.38, "40": 3.38, "XS": 4.55, "80": 4.55, "160": 6.35, "XXS": 9.09}},
            "1 1/4": {"OD_mm": 42.16, "schedules": {"5": 1.65, "10": 2.77, "30": 2.97, "STD": 3.56, "40": 3.56, "XS": 4.85, "80": 4.85, "160": 6.35, "XXS": 9.70}},
            "1 1/2": {"OD_mm": 48.26, "schedules": {"5": 1.65, "10": 2.77, "30": 3.18, "STD": 3.68, "40": 3.68, "XS": 5.08, "80": 5.08, "160": 7.14, "XXS": 10.16}},
            "2": {"OD_mm": 60.32, "schedules": {"5": 1.65, "10": 2.77, "30": 3.18, "STD": 3.91, "40": 3.91, "XS": 5.54, "80": 5.54, "160": 8.74, "XXS": 11.07, "2.11mm": 2.11, "3.58mm": 3.58, "4.37mm": 4.37, "4.78mm": 4.78, "6.35mm": 6.35, "7.14mm": 7.14}},
            "2 1/2": {"OD_mm": 73.02, "schedules": {"5": 2.11, "10": 2.77, "30": 4.78, "STD": 5.16, "40": 5.16, "XS": 7.01, "80": 7.01, "160": 9.52, "XXS": 14.02, "3.05mm": 3.05, "3.18mm": 3.18, "3.58mm": 3.58, "3.96mm": 3.96, "4.37mm": 4.37, "6.35mm": 6.35}},
            "3": {"OD_mm": 88.90, "schedules": {"5": 2.11, "10": 3.05, "30": 4.78, "STD": 5.49, "40": 5.49, "XS": 7.62, "80": 7.62, "160": 11.13, "XXS": 15.24, "2.77mm": 2.77, "3.18mm": 3.18, "3.58mm": 3.58, "3.96mm": 3.96, "4.37mm": 4.37, "6.35mm": 6.35, "7.14mm": 7.14}},
            "3 1/2": {"OD_mm": 101.60, "schedules": {"5": 2.11, "10": 3.05, "30": 4.78, "STD": 5.74, "40": 5.74, "XS": 8.08, "80": 8.08, "2.77mm": 2.77, "3.18mm": 3.18, "3.58mm": 3.58, "3.96mm": 3.96, "4.37mm": 4.37, "6.35mm": 6.35, "7.14mm": 7.14}},
            "4": {"OD_mm": 114.30, "schedules": {"5": 2.11, "10": 3.05, "30": 4.78, "STD": 6.02, "40": 6.02, "XS": 8.56, "80": 8.56, "120": 11.13, "160": 13.49, "XXS": 17.12, "2.77mm": 2.77, "3.18mm": 3.18, "3.58mm": 3.58, "3.96mm": 3.96, "4.37mm": 4.37, "5.16mm": 5.16, "5.56mm": 5.56, "6.35mm": 6.35, "7.14mm": 7.14, "7.92mm": 7.92}},
            "5": {"OD_mm": 141.30, "schedules": {"5": 2.77, "10": 3.40, "STD": 6.55, "40": 6.55, "XS": 9.52, "80": 9.52, "120": 12.70, "160": 15.88, "XXS": 19.05, "2.11mm": 2.11, "3.18mm": 3.18, "3.96mm": 3.96, "4.78mm": 4.78, "5.56mm": 5.56, "7.14mm": 7.14, "7.92mm": 7.92, "8.74mm": 8.74}},
            "6": {"OD_mm": 168.28, "schedules": {"5": 2.77, "10": 3.40, "STD": 7.11, "40": 7.11, "XS": 10.97, "80": 10.97, "120": 14.27, "160": 18.26, "XXS": 21.95, "2.11mm": 2.11, "3.18mm": 3.18, "3.58mm": 3.58, "3.96mm": 3.96, "4.37mm": 4.37, "4.78mm": 4.78, "5.16mm": 5.16, "5.56mm": 5.56, "6.35mm": 6.35, "7.92mm": 7.92, "8.74mm": 8.74, "12.70mm": 12.70, "15.88mm": 15.88, "19.05mm": 19.05, "22.22mm": 22.22}},
            "8": {"OD_mm": 219.08, "schedules": {"5": 2.77, "10": 3.76, "20": 6.35, "30": 7.04, "STD": 8.18, "40": 8.18, "60": 10.31, "XS": 12.70, "80": 12.70, "100": 15.09, "120": 18.26, "140": 20.62, "160": 23.01, "XXS": 22.22, "3.18mm": 3.18, "3.96mm": 3.96, "4.78mm": 4.78, "5.16mm": 5.16, "5.56mm": 5.56, "7.92mm": 7.92, "8.74mm": 8.74, "9.52mm": 9.52, "11.13mm": 11.13, "14.27mm": 14.27, "15.88mm": 15.88, "19.05mm": 19.05, "25.40mm": 25.40, "25.58mm": 25.58}},
            "10": {"OD_mm": 273.0, "schedules": {"5": 3.40, "10": 4.19, "20": 6.35, "30": 7.80, "STD": 9.27, "40": 9.27, "60": 12.70, "XS": 12.70, "80": 15.09, "100": 18.26, "120": 21.44, "140": 25.40, "160": 28.58, "XXS": 25.40, "3.96mm": 3.96, "4.78mm": 4.78, "5.16mm": 5.16, "5.56mm": 5.56, "7.09mm": 7.09, "8.74mm": 8.74, "11.13mm": 11.13, "14.27mm": 14.27, "15.88mm": 15.88, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "31.75mm": 31.75, "34.92mm": 34.92, "36.53mm": 36.53}},
            "12": {"OD_mm": 323.8, "schedules": {"5": 3.96, "10": 4.57, "20": 6.35, "30": 8.38, "STD": 9.52, "40": 10.31, "60": 14.27, "XS": 12.70, "80": 17.48, "100": 21.44, "120": 25.40, "140": 28.58, "160": 33.32, "XXS": 25.40, "4.37mm": 4.37, "4.78mm": 4.78, "5.16mm": 5.16, "5.56mm": 5.56, "7.14mm": 7.14, "7.92mm": 7.92, "8.74mm": 8.74, "11.13mm": 11.13, "15.88mm": 15.88, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "26.97mm": 26.97, "31.75mm": 31.75, "34.92mm": 34.92, "38.10mm": 38.10}},
            "14": {"OD_mm": 355.6, "schedules": {"5": 3.96, "10": 6.35, "20": 7.92, "30": 9.52, "STD": 9.52, "40": 11.13, "60": 15.09, "XS": 12.70, "80": 19.05, "100": 23.83, "120": 27.79, "140": 31.75, "160": 35.71, "4.78mm": 4.78, "5.16mm": 5.16, "5.33mm": 5.33, "5.56mm": 5.56, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "20.62mm": 20.62, "22.22mm": 22.22, "25.40mm": 25.40, "26.97mm": 26.97, "50.80mm": 50.80, "53.98mm": 53.98, "55.88mm": 55.88, "63.50mm": 63.50}},
            "16": {"OD_mm": 406.4, "schedules": {"5": 4.19, "10": 6.35, "20": 7.92, "30": 9.52, "STD": 9.52, "40": 12.70, "60": 16.66, "XS": 12.70, "80": 21.44, "100": 26.19, "120": 30.96, "140": 36.53, "160": 40.49, "4.78mm": 4.78, "5.16mm": 5.16, "5.56mm": 5.56, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75, "44.45mm": 44.45}},
            "18": {"OD_mm": 457.2, "schedules": {"10": 6.35, "20": 7.92, "30": 11.13, "STD": 9.52, "40": 14.27, "60": 19.05, "XS": 12.70, "80": 23.83, "100": 29.36, "120": 34.92, "140": 39.67, "160": 45.24, "4.19mm": 4.19, "4.78mm": 4.78, "5.56mm": 5.56, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.91mm": 11.91, "15.88mm": 15.88, "17.48mm": 17.48, "20.62mm": 20.62, "22.22mm": 22.22, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "20": {"OD_mm": 508.0, "schedules": {"10": 6.35, "20": 9.52, "30": 12.70, "STD": 9.52, "40": 15.09, "60": 20.62, "XS": 12.70, "80": 26.19, "100": 32.54, "120": 38.10, "140": 44.45, "160": 50.01, "4.78mm": 4.78, "5.56mm": 5.56, "7.14mm": 7.14, "7.92mm": 7.92, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75, "33.32mm": 33.32, "34.92mm": 34.92}},
            "22": {"OD_mm": 558.8, "schedules": {"10": 6.35, "20": 9.52, "30": 12.70, "STD": 9.52, "60": 22.22, "XS": 12.70, "80": 28.58, "100": 34.92, "120": 41.28, "140": 47.62, "160": 53.98, "4.78mm": 4.78, "5.56mm": 5.56, "7.14mm": 7.14, "7.92mm": 7.92, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "30.18mm": 30.18, "31.75mm": 31.75, "33.32mm": 33.32, "36.53mm": 36.53, "38.10mm": 38.10}},
            "24": {"OD_mm": 609.6, "schedules": {"10": 6.35, "20": 9.52, "30": 14.27, "STD": 9.52, "40": 17.48, "60": 24.61, "XS": 12.70, "80": 30.96, "100": 38.89, "120": 46.02, "140": 52.37, "160": 59.54, "5.54mm": 5.54, "7.14mm": 7.14, "7.92mm": 7.92, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "15.88mm": 15.88, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75, "33.32mm": 33.32, "34.92mm": 34.92, "36.53mm": 36.53, "38.10mm": 38.10}},
            "26": {"OD_mm": 660.4, "schedules": {"10": 7.92, "20": 12.70, "STD": 9.52, "XS": 12.70, "6.35mm": 6.35, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97}},
            "28": {"OD_mm": 711.2, "schedules": {"10": 7.92, "20": 12.70, "30": 15.88, "STD": 9.52, "XS": 12.70, "6.35mm": 6.35, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97}},
            "30": {"OD_mm": 762.0, "schedules": {"5": 6.35, "10": 7.92, "20": 12.70, "30": 15.88, "STD": 9.52, "XS": 12.70, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "32": {"OD_mm": 813.0, "schedules": {"10": 7.92, "20": 12.70, "30": 15.88, "40": 17.48, "STD": 9.52, "XS": 12.70, "6.35mm": 6.35, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "34": {"OD_mm": 864.0, "schedules": {"10": 7.92, "20": 12.70, "30": 15.88, "40": 17.48, "STD": 9.52, "XS": 12.70, "6.35mm": 6.35, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "36": {"OD_mm": 914.0, "schedules": {"10": 7.92, "20": 12.70, "30": 14.27, "40": 19.05, "STD": 9.52, "XS": 12.70, "6.35mm": 6.35, "7.14mm": 7.14, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "15.88mm": 15.88, "17.48mm": 17.48, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "38": {"OD_mm": 965.0, "schedules": {"STD": 9.52, "XS": 12.70, "7.92mm": 7.92, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "40": {"OD_mm": 1016.0, "schedules": {"STD": 9.52, "XS": 12.70, "7.92mm": 7.92, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "42": {"OD_mm": 1067.0, "schedules": {"STD": 9.52, "XS": 12.70, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "44": {"OD_mm": 1118.0, "schedules": {"STD": 9.52, "XS": 12.70, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "46": {"OD_mm": 1168.0, "schedules": {"STD": 9.52, "XS": 12.70, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "48": {"OD_mm": 1219.0, "schedules": {"STD": 9.52, "XS": 12.70, "8.74mm": 8.74, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "52": {"OD_mm": 1321.0, "schedules": {"9.52mm": 9.52, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "12.70mm": 12.70, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "56": {"OD_mm": 1422.0, "schedules": {"9.52mm": 9.52, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "12.70mm": 12.70, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "60": {"OD_mm": 1524.0, "schedules": {"9.52mm": 9.52, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "12.70mm": 12.70, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "64": {"OD_mm": 1626.0, "schedules": {"9.52mm": 9.52, "10.31mm": 10.31, "11.13mm": 11.13, "11.91mm": 11.91, "12.70mm": 12.70, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "68": {"OD_mm": 1727.0, "schedules": {"11.91mm": 11.91, "12.70mm": 12.70, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "72": {"OD_mm": 1829.0, "schedules": {"12.70mm": 12.70, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "76": {"OD_mm": 1930.0, "schedules": {"12.70mm": 12.70, "14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}},
            "80": {"OD_mm": 2032.0, "schedules": {"14.27mm": 14.27, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "20.62mm": 20.62, "22.22mm": 22.22, "23.83mm": 23.83, "25.40mm": 25.40, "26.97mm": 26.97, "28.58mm": 28.58, "30.18mm": 30.18, "31.75mm": 31.75}}
        }

    def create_log_widgets(self, parent):
        self.log_text = ScrolledText(parent, wrap=tk.WORD, state=tk.DISABLED, bg="#F0F0F0", font=("Courier", 10))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        ttk.Button(parent, text="Logları Temizle", command=lambda: self.log_text.config(state=tk.NORMAL) or self.log_text.delete(1.0, tk.END) or self.log_text.config(state=tk.DISABLED)).grid(row=1, column=0, pady=5, sticky="e")
        parent.grid_rowconfigure(0, weight=1)

    def log_message(self, message, level="INFO"):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        self.log_queue.put(log_entry)
        self.root.after(0, self.update_log_text)

    def update_log_text(self):
        self.log_text.config(state=tk.NORMAL)
        while not self.log_queue.empty():
            self.log_text.insert(tk.END, self.log_queue.get())
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def create_report_widgets(self, parent):
        self.report_label = ttk.Label(parent, text="Hesaplama Raporu:", font=self.label_font_bold)
        self.report_label.grid(row=0, column=0, sticky="w")
        self.report_text = ScrolledText(parent, height=30, width=40, wrap=tk.WORD)
        self.report_text.grid(row=1, column=0, pady=10, sticky="nsew")
        parent.grid_rowconfigure(1, weight=1)
        ttk.Button(parent, text="Raporu Yazdır", command=self.print_report).grid(row=2, column=0, pady=5)

    def create_input_widgets(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(10, weight=1)
        label_font_normal = self.label_font_normal
        label_font_bold = self.label_font_bold

        # === Gaz Karışımı (Row 0) ===
        self.gas_frame = ttk.LabelFrame(parent, text="Gaz Karışımı (%)", padding=10)
        self.gas_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.gas_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(self.gas_frame, text="Gaz Ara:", font=label_font_normal).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.gas_search_entry = ttk.Entry(self.gas_frame, width=25)
        self.gas_search_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky="ew")
        self.gas_search_entry.bind('<KeyRelease>', self.filter_gas_list)

        self.gas_dropdown = ttk.Combobox(self.gas_frame, values=list(self.coolprop_gases.values()), width=25)
        self.gas_dropdown.grid(row=1, column=0, padx=5, pady=2)
        self.gas_dropdown.set("Gaz Seçin")
        ttk.Button(self.gas_frame, text="Ekle", command=self.add_gas_row).grid(row=1, column=1, padx=5)

        # Ergonomi: Gaz Tablosu Yüksekliği %20 Artırıldı (150 -> 180)
        self.gas_canvas = tk.Canvas(self.gas_frame, height=180)
        self.gas_scrollbar = ttk.Scrollbar(self.gas_frame, orient="vertical", command=self.gas_canvas.yview)
        self.gas_list_frame = ttk.Frame(self.gas_canvas)
        self.gas_list_frame.bind("<Configure>", lambda e: self.gas_canvas.configure(scrollregion=self.gas_canvas.bbox("all")))
        self.gas_canvas.create_window((0,0), window=self.gas_list_frame, anchor="nw")
        self.gas_canvas.configure(yscrollcommand=self.gas_scrollbar.set)
        self.gas_canvas.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        self.gas_scrollbar.grid(row=2, column=2, sticky="ns")
        self.gas_frame.grid_rowconfigure(2, weight=1)

        ttk.Label(self.gas_frame, text="Bileşim Türü", font=label_font_normal).grid(row=3, column=0, sticky="w", pady=(10,0))
        self.composition_type = ttk.Combobox(self.gas_frame, values=["Mol %", "Kütle %"], width=10)
        self.composition_type.grid(row=3, column=1, pady=(10,0))
        self.composition_type.set("Mol %")

        # === Basınç ve Sıcaklık (Row 1) ===
        self.pressure_frame = ttk.LabelFrame(parent, text="Giriş Basıncı ve Sıcaklık", padding=10)
        self.pressure_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.pressure_frame, text="Basınç Değeri", font=label_font_normal).grid(row=0, column=0, sticky="w")
        self.pressure_value = tk.DoubleVar()
        self.pressure_value_entry = ttk.Entry(self.pressure_frame, textvariable=self.pressure_value, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.pressure_value_entry.grid(row=0, column=1)
        ttk.Label(self.pressure_frame, text="Basınç Birimi", font=label_font_normal).grid(row=0, column=2, padx=5)
        self.pressure_unit = ttk.Combobox(self.pressure_frame, values=["Barg", "Bara", "Psig", "Psia"], width=8)
        self.pressure_unit.grid(row=0, column=3)
        self.pressure_unit.set("Barg")
        ttk.Label(self.pressure_frame, text="Sıcaklık Değeri", font=label_font_normal).grid(row=1, column=0, sticky="w")
        self.temperature_value = tk.DoubleVar(value=298.15)
        self.temperature_value_entry = ttk.Entry(self.pressure_frame, textvariable=self.temperature_value, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.temperature_value_entry.grid(row=1, column=1)
        ttk.Label(self.pressure_frame, text="Sıcaklık Birimi", font=label_font_normal).grid(row=1, column=2, padx=5)
        self.temperature_unit = ttk.Combobox(self.pressure_frame, values=["K", "°C", "°F"], width=8)
        self.temperature_unit.grid(row=1, column=3)
        self.temperature_unit.set("K")

        # === Akış ve Tasarım Kriterleri (Row 2) ===
        self.flow_design_frame = ttk.LabelFrame(parent, text="Akış ve Tasarım Kriterleri", padding=10)
        self.flow_design_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        ttk.Label(self.flow_design_frame, text="Akış Değeri", font=label_font_normal).grid(row=0, column=0, sticky="w")
        self.flow_value = tk.DoubleVar()
        self.flow_value_entry = ttk.Entry(self.flow_design_frame, textvariable=self.flow_value, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.flow_value_entry.grid(row=0, column=1)
        ttk.Label(self.flow_design_frame, text="Akış Birimi", font=label_font_normal).grid(row=0, column=2, padx=5)
        self.flow_unit = ttk.Combobox(self.flow_design_frame, values=["Sm³/h", "kg/s"], width=8)
        self.flow_unit.grid(row=0, column=3)
        self.flow_unit.set("Sm³/h")
        
        ttk.Label(self.flow_design_frame, text="Maks. Hız (m/s)", font=label_font_normal).grid(row=1, column=0, sticky="w", pady=(5,0))
        self.max_velocity = tk.DoubleVar(value=20.0)
        self.max_velocity_entry = ttk.Entry(self.flow_design_frame, textvariable=self.max_velocity, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.max_velocity_entry.grid(row=1, column=1, pady=(5,0))

        ttk.Label(self.flow_design_frame, text="Tasarım Basıncı", font=label_font_normal).grid(row=2, column=0, sticky="w", pady=(10,0))
        self.design_pressure_value = tk.DoubleVar()
        self.design_pressure_value_entry = ttk.Entry(self.flow_design_frame, textvariable=self.design_pressure_value, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.design_pressure_value_entry.grid(row=2, column=1, pady=(10,0))
        ttk.Label(self.flow_design_frame, text="Birim", font=label_font_normal).grid(row=2, column=2, padx=5, pady=(10,0))
        self.design_pressure_unit = ttk.Combobox(self.flow_design_frame, values=["Barg", "Bara", "Psig", "Psia"], width=8)
        self.design_pressure_unit.grid(row=2, column=3, pady=(10,0))
        self.design_pressure_unit.set("Barg")
        
        ttk.Label(self.flow_design_frame, text="Malzeme", font=label_font_normal).grid(row=3, column=0, sticky="w", pady=(10,0))
        self.pipe_material = ttk.Combobox(self.flow_design_frame, values=list(self.pipe_materials.keys()), width=20)
        self.pipe_material.grid(row=3, column=1)
        self.pipe_material.set("API 5L Grade B")

        ttk.Label(self.flow_design_frame, text="Faktör F", font=label_font_normal).grid(row=4, column=0, sticky="w")
        self.factor_F = tk.DoubleVar(value=0.72)
        ttk.Entry(self.flow_design_frame, textvariable=self.factor_F, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P')).grid(row=4, column=1)

        ttk.Label(self.flow_design_frame, text="Faktör E", font=label_font_normal).grid(row=4, column=2, sticky="w", padx=5)
        self.factor_E = tk.DoubleVar(value=1.0)
        ttk.Entry(self.flow_design_frame, textvariable=self.factor_E, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P')).grid(row=4, column=3)

        ttk.Label(self.flow_design_frame, text="Faktör T", font=label_font_normal).grid(row=4, column=4, sticky="w", padx=5)
        self.factor_T = tk.DoubleVar(value=1.0)
        ttk.Entry(self.flow_design_frame, textvariable=self.factor_T, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P')).grid(row=4, column=5)


        # === Boru Özellikleri (Row 3 - Çap ve Kalınlık) ===
        self.pipe_frame = ttk.LabelFrame(parent, text="Mevcut Boru Geometrisi", padding=10)
        self.pipe_frame.grid(row=3, column=0, padx=5, pady=5, sticky="ew")

        ttk.Label(self.pipe_frame, text="Çap (mm)", font=label_font_normal).grid(row=0, column=0, sticky="w")
        self.pipe_diameter = tk.DoubleVar()
        self.pipe_diameter_entry = ttk.Entry(self.pipe_frame, textvariable=self.pipe_diameter, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.pipe_diameter_entry.grid(row=0, column=1)

        ttk.Label(self.pipe_frame, text="Et Kalınlığı (mm)", font=label_font_normal).grid(row=1, column=0, sticky="w")
        self.pipe_thickness = tk.DoubleVar()
        self.pipe_thickness_entry = ttk.Entry(self.pipe_frame, textvariable=self.pipe_thickness, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.pipe_thickness_entry.grid(row=1, column=1)

        self.length_label = ttk.Label(self.pipe_frame, text="Uzunluk (m)", font=label_font_normal)
        self.length_label.grid(row=2, column=0, sticky="w")
        self.pipe_length = tk.DoubleVar(value=100.0)
        self.pipe_length_entry = ttk.Entry(self.pipe_frame, textvariable=self.pipe_length, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.pipe_length_entry.grid(row=2, column=1)
        
        self.outlet_pressure_label = ttk.Label(self.pipe_frame, text="Çıkış Basıncı", font=label_font_normal)
        self.outlet_pressure_value = tk.DoubleVar()
        self.outlet_pressure_entry = ttk.Entry(self.pipe_frame, textvariable=self.outlet_pressure_value, width=10, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        self.outlet_pressure_unit = ttk.Combobox(self.pipe_frame, values=["Barg", "Bara", "Psig", "Psia"], width=8)
        self.outlet_pressure_unit.set("Barg")
        self.outlet_pressure_label.grid_remove()
        self.outlet_pressure_entry.grid_remove()
        self.outlet_pressure_unit.grid_remove()

        # === Boru Elemanları (Row 4) - ERGONOMİK 2 KOLONLU DÜZENLEME ===
        self.fittings_frame = ttk.LabelFrame(parent, text="Boru Elemanları (Adet)", padding=10)
        self.fittings_frame.grid(row=4, column=0, padx=5, pady=5, sticky="ew")
        
        fittings_items = list(self.fitting_k_factors.keys())
        half = (len(fittings_items) + 1) // 2
        
        for i, fitting in enumerate(fittings_items):
            col_start = 0 if i < half else 3
            row = i if i < half else i - half
            
            # Etiket
            ttk.Label(self.fittings_frame, text=fitting, font=label_font_normal).grid(row=row, column=col_start, sticky="w", padx=5, pady=2)
            
            # Adet Girişi
            self.fitting_counts[fitting] = tk.IntVar(value=0)
            ttk.Entry(self.fittings_frame, textvariable=self.fitting_counts[fitting], width=3, validate="key", validatecommand=(self.validate_int_positive, '%P')).grid(row=row, column=col_start + 1, padx=5, pady=2)

            # Kv/Cv girişleri
            if fitting == "Küresel Vana (Tam Açık)":
                ttk.Label(self.fittings_frame, text="Kv (m³/h):", font=label_font_normal).grid(row=row, column=col_start + 2, sticky="w", padx=(15, 0), pady=2)
                ttk.Entry(self.fittings_frame, textvariable=self.ball_valve_kv, width=6, validate="key", validatecommand=(self.validate_float_positive, '%P')).grid(row=row, column=col_start + 3, padx=5, pady=2)
                ttk.Label(self.fittings_frame, text="Cv:", font=label_font_normal).grid(row=row, column=col_start + 4, sticky="w", padx=(15, 0), pady=2)
                ttk.Entry(self.fittings_frame, textvariable=self.ball_valve_cv, width=6, validate="key", validatecommand=(self.validate_float_positive, '%P')).grid(row=row, column=col_start + 5, padx=5, pady=2)
                self.ball_valve_kv.trace("w", self.disable_cv_if_kv)
                self.ball_valve_cv.trace("w", self.disable_kv_if_cv)

        # === Hesaplama Seçenekleri (Row 5) ===
        self.calc_frame = ttk.LabelFrame(parent, text="Hesaplama Seçenekleri", padding=10)
        self.calc_frame.grid(row=5, column=0, padx=5, pady=5, sticky="ew")
        
        ttk.Label(self.calc_frame, text="Hesaplanacak Değer", font=label_font_normal).grid(row=0, column=2, padx=10, sticky="w")
        self.calc_target = ttk.Combobox(self.calc_frame, values=["Çıkış Basıncı", "Maksimum Uzunluk", "Minimum Çap"], width=20)
        self.calc_target.grid(row=0, column=3)
        self.calc_target.set("Çıkış Basıncı")
        self.calc_target.bind("<<ComboboxSelected>>", self.toggle_input_fields)
        
        ttk.Label(self.calc_frame, text="Akışkan Özelliği", font=label_font_normal).grid(row=0, column=0, sticky="w")
        self.flow_property = ttk.Combobox(self.calc_frame, values=["Sıkıştırılamaz", "Sıkıştırılabilir"], width=15)
        self.flow_property.grid(row=0, column=1)
        self.flow_property.set("Sıkıştırılamaz")

        ttk.Label(self.calc_frame, text="Termodinamik Model", font=label_font_normal).grid(row=1, column=0, sticky="w", pady=(10,0))
        self.thermo_library_choice = ttk.Combobox(self.calc_frame, 
            values=["CoolProp (High Accuracy EOS)", "Peng-Robinson (PR EOS)", "Soave-Redlich-Kwong (SRK EOS)", "Pseudo-Critical (Kay's Rule)"], width=25)
        self.thermo_library_choice.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(10,0), padx=(0, 200))
        self.thermo_library_choice.set("CoolProp (High Accuracy EOS)")

        # === Hesapla Butonu (Row 6) ===
        self.calc_button = tk.Button(parent, text="Hesapla", font=self.label_font_bold, bg="#4CAF50", fg="white", width=15, height=2, command=self.start_calculate_thread)
        self.calc_button.grid(row=6, column=0, pady=20)

    # --- Arayüz Kontrol Metotları ---
    def toggle_input_fields(self, event=None):
        target = self.calc_target.get()
        if target == "Minimum Çap":
            self.pipe_frame.grid_remove()
            self.fittings_frame.grid_remove()
            self.flow_design_frame.grid()
        else:
            self.pipe_frame.grid()
            self.fittings_frame.grid()
            self.flow_design_frame.grid()
            if target == "Çıkış Basıncı":
                self.length_label.grid(row=2, column=0, sticky="w")
                self.pipe_length_entry.grid(row=2, column=1)
                self.outlet_pressure_label.grid_remove()
                self.outlet_pressure_entry.grid_remove()
                self.outlet_pressure_unit.grid_remove()
            else:
                self.length_label.grid_remove()
                self.pipe_length_entry.grid_remove()
                self.outlet_pressure_label.grid(row=2, column=0, sticky="w")
                self.outlet_pressure_entry.grid(row=2, column=1)
                self.outlet_pressure_unit.grid(row=2, column=2)

    def filter_gas_list(self, event=None):
        search_term = self.gas_search_entry.get().lower()
        filtered_gases = [
            name for id, name in self.coolprop_gases.items()
            if search_term in name.lower() or search_term in id.lower()
        ]
        self.gas_dropdown['values'] = filtered_gases
        if not filtered_gases: self.gas_dropdown.set("Gaz bulunamadı")
        elif search_term == "": self.gas_dropdown['values'] = list(self.coolprop_gases.values())
        elif self.gas_dropdown.get() not in filtered_gases: self.gas_dropdown.set("Gaz Seçin")

    def add_gas_row(self):
        gas_name = self.gas_dropdown.get()
        if gas_name == "Gaz Seçin" or gas_name == "Gaz bulunamadı": messagebox.showwarning("Uyarı", "Lütfen geçerli bir gaz seçin."); return
        coolprop_id = next(k for k, v in self.coolprop_gases.items() if v == gas_name)
        if coolprop_id in self.gas_components: messagebox.showinfo("Bilgi", f"{gas_name} zaten listede."); return
        row = len(self.gas_components); var = tk.DoubleVar(value=0.0)
        self.gas_components[coolprop_id] = var
        ttk.Label(self.gas_list_frame, text=gas_name).grid(row=row, column=0, sticky="w", padx=2, pady=2)
        entry = ttk.Entry(self.gas_list_frame, textvariable=var, width=8, validate="key", validatecommand=(self.validate_float_positive, '%P'))
        entry.grid(row=row, column=1, padx=2, pady=2)
        ttk.Button(self.gas_list_frame, text="Sil", command=lambda g=coolprop_id: self.remove_gas_row(g)).grid(row=row, column=2, padx=2, pady=2)

    def remove_gas_row(self, gas_id):
        if gas_id in self.gas_components:
            del self.gas_components[gas_id]
            for widget in self.gas_list_frame.winfo_children(): widget.destroy()
            for i, (gid, var) in enumerate(self.gas_components.items()):
                ttk.Label(self.gas_list_frame, text=self.coolprop_gases[gid]).grid(row=i, column=0, sticky="w", padx=2, pady=2)
                entry = ttk.Entry(self.gas_list_frame, textvariable=var, width=8, validate="key", validatecommand=(self.validate_float_positive, '%P'))
                entry.grid(row=i, column=1, padx=2, pady=2)
                ttk.Button(self.gas_list_frame, text="Sil", command=lambda g=gid: self.remove_gas_row(g)).grid(row=i, column=2, padx=2, pady=2)

    def disable_cv_if_kv(self, *args):
        try:
            # Tkinter trace çağrılırken entry boş olabilir, bu kontrolü ekledik.
            if self.ball_valve_kv.get() > 0 and self.ball_valve_cv.get() > 0: self.ball_valve_cv.set(0)
        except: pass

    def disable_kv_if_cv(self, *args):
        try:
            # Tkinter trace çağrılırken entry boş olabilir, bu kontrolü ekledik.
            if self.ball_valve_cv.get() > 0 and self.ball_valve_kv.get() > 0: self.ball_valve_kv.set(0)
        except: pass

    def validate_float_positive_func(self, value):
        if value == "": return True
        try:
            f = float(value)
            return f >= 0
        except ValueError:
            return False

    def validate_int_positive_func(self, value):
        if value == "": return True
        try:
            i = int(value)
            return i >= 0
        except ValueError:
            return False

    def validate_inputs(self):
        def get_entry_value(var, entry_widget):
            try: return var.get()
            except tk.TclError:
                val_str = entry_widget.get().strip()
                if val_str == "": return None
                try: return float(val_str)
                except ValueError: return None

        if not self.gas_components: messagebox.showerror("Hata", "En az bir gaz bileşeni ekleyin!"); return False
        total_pct = sum(var.get() for var in self.gas_components.values())
        if total_pct == 0: messagebox.showerror("Hata", "Gaz bileşim yüzdesi toplamı sıfır!"); return False
        press_val = get_entry_value(self.pressure_value, self.pressure_value_entry)
        if press_val is None or press_val < 0: messagebox.showerror("Hata", "Giriş basıncı negatif olamaz!"); return False
        temp_val = get_entry_value(self.temperature_value, self.temperature_value_entry)
        if temp_val is None or temp_val <= 0: messagebox.showerror("Hata", "Sıcaklık pozitif bir sayı olmalıdır!"); return False
        flow_val = get_entry_value(self.flow_value, self.flow_value_entry)
        if flow_val is None or flow_val <= 0: messagebox.showerror("Hata", "Akış değeri pozitif bir sayı olmalıdır!"); return False
        max_vel_val = get_entry_value(self.max_velocity, self.max_velocity_entry)
        if max_vel_val is None or max_vel_val <= 0: messagebox.showerror("Hata", "Maksimum hız pozitif olmalıdır!"); return False
        design_press_val = get_entry_value(self.design_pressure_value, self.design_pressure_value_entry)
        if design_press_val is None or design_press_val < 0: messagebox.showerror("Hata", "Tasarım basıncı negatif olamaz!"); return False
        
        if not self.pipe_material.get(): messagebox.showerror("Hata", "Lütfen bir boru malzemesi seçin!"); return False

        target = self.calc_target.get()
        if target == "Minimum Çap": return True
        pipe_diam_val = get_entry_value(self.pipe_diameter, self.pipe_diameter_entry)
        if pipe_diam_val is None or pipe_diam_val <= 0: messagebox.showerror("Hata", "Boru çapı pozitif bir sayı olmalıdır!"); return False
        pipe_thick_val = get_entry_value(self.pipe_thickness, self.pipe_thickness_entry)
        if pipe_thick_val is None or pipe_thick_val <= 0: messagebox.showerror("Hata", "Et kalınlığı pozitif bir sayı olmalıdır!"); return False
        if pipe_diam_val <= 2 * pipe_thick_val: messagebox.showerror("Hata", "Et kalınlığı çapın yarısından fazla olamaz!"); return False
        if target == "Çıkış Basıncı":
            length_val = get_entry_value(self.pipe_length, self.pipe_length_entry)
            if length_val is None or length_val <= 0: messagebox.showerror("Hata", "Boru uzunluğu pozitif bir sayı olmalıdır!"); return False
        else:
            outlet_press_val = get_entry_value(self.outlet_pressure_value, self.outlet_pressure_entry)
            if outlet_press_val is None or outlet_press_val < 0: messagebox.showerror("Hata", "Çıkış basıncı negatif olamaz!"); return False
        return True


    # --- TERM. MODELLER ---
    
    def get_pure_component_props(self, gas_id):
        try:
            return {
                'Tc': CP.PropsSI('TCRIT', gas_id), 'Pc': CP.PropsSI('PCRIT', gas_id),
                'omega': CP.PropsSI('ACENTRIC', gas_id), 'MW': CP.PropsSI('M', gas_id) * 1000
            }
        except Exception:
            # Metan için varsayılan değerler (Örn: Hesaplamanın çökmesini engellemek için geri dönüş)
            self.log_message(f"UYARI: CoolProp'tan {gas_id} için kritik özellikler alınamadı. Varsayılan değerler kullanılıyor.", level="WARNING")
            return {'Tc': 190.5, 'Pc': 45.99e5, 'omega': 0.011, 'MW': 16.04}

    def calculate_cubic_eos_props(self, P, T, mole_fractions, EOS_type):
        self.log_message(f"Hesaplama: {EOS_type} modeli kullanılıyor.")
        A_c, B_c = (0.45724, 0.07780) if EOS_type == "PR" else (0.42748, 0.08664)
        kappa_coeffs = (0.37464, 1.54226, -0.26992) if EOS_type == "PR" else (0.48, 1.574, -0.176)
        
        b_mix = 0; sqrt_a_mix = 0; MW_mix = 0
        
        for gas, y in mole_fractions.items():
            props = self.get_pure_component_props(gas)
            
            omega = props['omega']
            kappa = kappa_coeffs[0] + kappa_coeffs[1] * omega + kappa_coeffs[2] * omega**2
            
            alpha = (1 + kappa * (1 - math.sqrt(T / props['Tc'])))**2
            a_i = A_c * (R_J_mol_K * props['Tc'])**2 / props['Pc'] * alpha
            b_i = B_c * R_J_mol_K * props['Tc'] / props['Pc']

            b_mix += y * b_i
            sqrt_a_mix += y * math.sqrt(a_i)
            MW_mix += y * props['MW']

        a_mix = sqrt_a_mix**2
        
        A = a_mix * P / (R_J_mol_K * T)**2
        B = b_mix * P / (R_J_mol_K * T)
        
        if EOS_type == "PR":
            coeffs = [1, (B - 1), (A - 3*B**2 - 2*B), (-A*B + B**2 + B**3)]
        else:
            coeffs = [1, -1, (A - B - B**2), -A*B]
        
        roots = np.roots(coeffs)
        real_roots = roots[np.isreal(roots)].real

        if len(real_roots) == 0:
            raise ValueError(f"{EOS_type} modelinde P={P/1e5:.1f} bara, T={T:.1f} K noktasında gerçek kök bulunamadı (muhtemelen faz bölgesi).")

        Z = max(real_roots)
        
        density = (P * MW_mix * 1e-3) / (Z * R_J_mol_K * T)
        standard_density = (101325 * MW_mix * 1e-3) / (1.0 * R_J_mol_K * 288.15) 
        viscosity = 1.5e-5 * math.sqrt(MW_mix / 16.04) # Basit tahmin

        Cp_mix, k_mix = 0, 0
        for gas, y in mole_fractions.items():
            try:
                # CoolProp'tan ideal gaz Cp0 değeri alınıyor (PR/SRK özgünlüğü için basitleştirme)
                Cp_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / 1000 
                k_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / CP.PropsSI('CV0MASS', 'T', T, 'P', 101325, gas)
            except:
                Cp_mix += y * 2.0; k_mix += y * 1.25 # Metan yaklaşık değerleri
        k_avg = k_mix / len(mole_fractions) if len(mole_fractions) > 0 else 1.25
        Cv_mix = Cp_mix / k_avg

        return {
            "MW": MW_mix, "Cp": Cp_mix, "Cv": Cv_mix, "Z": Z, "density": density,
            "viscosity": viscosity, "standard_density": standard_density,
            "EOS_model": EOS_type
        }

    def calculate_coolprop_properties(self, P, T, mixture):
        self.log_message("Hesaplama: CoolProp (Helmholtz EOS) kullanılıyor.")
        self.viscosity_fallback_warning = False
        standard_P = 101325; standard_T = 288.15

        try:
            standard_density = CP.PropsSI('D', 'P', standard_P, 'T', standard_T, mixture)
        except Exception as e:
            raise ValueError(f"CoolProp Standart Yoğunluk Hatası: {str(e)}")
        
        MW_mix = CP.PropsSI('M', 'P', P, 'T', T, mixture) * 1000

        try:
            viscosity = CP.PropsSI('V', 'P', P, 'T', T, mixture)
            self.log_message("CoolProp: Viskozite doğrudan hesaplandı.", level="DEBUG")
        except Exception:
            self.viscosity_fallback_warning = True
            viscosity = 1.5e-5 * math.sqrt(MW_mix / 16.04) # Basit tahmin
            self.log_message(f"UYARI: CoolProp viskozite hesaplamada hata verdi. Tahmini μ={viscosity*1e6:.2f} µPa·s kullanıldı.", level="WARNING")
        
        props = {
            "MW": MW_mix, "Cp": CP.PropsSI('C', 'P', P, 'T', T, mixture) / 1000,
            "Cv": CP.PropsSI('O', 'P', P, 'T', T, mixture) / 1000,
            "Z": CP.PropsSI('Z', 'P', P, 'T', T, mixture),
            "density": CP.PropsSI('D', 'P', P, 'T', T, mixture),
            "viscosity": viscosity, "standard_density": standard_density,
        }
        return props

    def calculate_pseudo_critical_properties(self, P, T, mole_fractions):
        self.log_message("Hesaplama: Pseudo-Critical (Kay's Rule) modeli kullanılıyor.")
        Ppc, Tpc, MW_mix = 0, 0, 0
        for gas, y in mole_fractions.items():
            props = self.get_pure_component_props(gas)
            Ppc += y * props['Pc']; Tpc += y * props['Tc']; MW_mix += y * props['MW']
        
        Pr = P / Ppc; Tr = T / Tpc
        Z = 1.0 + Pr / (14 * Tr) if Pr > 0.1 or Tr < 1.5 else 1.0 # Basitleştirilmiş Z faktörü
            
        density = (P * MW_mix * 1e-3) / (Z * R_J_mol_K * T)
        standard_density = (101325 * MW_mix * 1e-3) / (1.0 * R_J_mol_K * 288.15) 
        viscosity = 1.5e-5 * math.sqrt(MW_mix / 16.04)

        Cp_mix, k_mix = 0, 0
        for gas, y in mole_fractions.items():
            try:
                Cp_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / 1000
                k_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / CP.PropsSI('CV0MASS', 'T', T, 'P', 101325, gas)
            except:
                Cp_mix += y * 2.0; k_mix += y * 1.25 
        
        k_avg = k_mix / len(mole_fractions) if len(mole_fractions) > 0 else 1.25
        Cv_mix = Cp_mix / k_avg

        props = {
            "MW": MW_mix, "Cp": Cp_mix, "Cv": Cv_mix, "Z": Z, "density": density,
            "viscosity": viscosity, "standard_density": standard_density,
            "Ppc": Ppc, "Tpc": Tpc, "Pr": Pr, "Tr": Tr
        }
        return props
        

    def calculate_thermo_properties(self, P, T, mole_fractions, library_choice):
        if library_choice == "CoolProp (High Accuracy EOS)":
            mixture = "&".join([f"{k}[{v:.6f}]" for k, v in mole_fractions.items()])
            return self.calculate_coolprop_properties(P, T, mixture)
        
        elif library_choice == "Peng-Robinson (PR EOS)":
            return self.calculate_cubic_eos_props(P, T, mole_fractions, "PR")
            
        elif library_choice == "Soave-Redlich-Kwong (SRK EOS)":
            return self.calculate_cubic_eos_props(P, T, mole_fractions, "SRK")

        elif library_choice == "Pseudo-Critical (Kay's Rule)":
            return self.calculate_pseudo_critical_properties(P, T, mole_fractions)
        
        else:
            raise ValueError(f"Geçersiz termodinamik model seçimi: {library_choice}")

    # --- Yardımcı Metotlar (Birimler, Sürtünme, K Faktörleri) ---
    def mass_to_mole_fraction(self, mass_fractions):
        total_moles = 0.0; moles = {}
        for gas, mass_frac in mass_fractions.items():
            try: MW = CP.PropsSI('M', gas)
            except Exception as e: raise ValueError(f"{gas} için moleküler ağırlık alınamadı: {str(e)}")
            moles[gas] = mass_frac / MW; total_moles += moles[gas]
        if total_moles == 0: raise ValueError("Toplam mol sıfır!")
        return {gas: mole / total_moles for gas, mole in moles.items()}

    def convert_pressure(self, value, unit):
        conversions = {
            "Barg": lambda x: (x + 1.01325) * 1e5, "Bara": lambda x: x * 1e5,
            "Psig": lambda x: (x + 14.6959) * 6894.76, "Psia": lambda x: x * 6894.76
        }
        return conversions[unit](value)

    def convert_pressure_from_pa(self, delta_p_pa, unit):
        conversions = {"Bara": 1e5, "Barg": 1e5, "Psia": 6894.76, "Psig": 6894.76}
        return delta_p_pa / conversions[unit]

    def convert_temperature(self, value, unit):
        if unit == "K": return value
        elif unit == "°C": return value + 273.15
        elif unit == "°F": return (value - 32) * 5 / 9 + 273.15
        else: raise ValueError("Geçersiz sıcaklık birimi")

    def convert_flow_rate(self, value, unit, density, standard_density):
        if unit == "Sm³/h":
            # Akışkan, standart koşulda hacimsel debi * (standart yoğunluk) = kütlesel debi
            m_dot = (value / 3600) * standard_density
            return m_dot / density
        elif unit == "kg/s":
            # Q_akt = m_dot / rho_gercek
            return value / density
        else:
            raise ValueError("Geçersiz akış birimi")

    def get_friction_factor(self, Re, relative_roughness):
        if Re < 2000: return 64 / Re
        else:
            # Colebrook-White denklemi iteratif çözüm 
            f_old = 0.02
            for _ in range(20):
                inner = (relative_roughness / 3.7) + (2.51 / (Re * math.sqrt(f_old)))
                f_new = (-2 * math.log10(inner)) ** -2
                if abs(f_new - f_old) < 1e-6: return f_new
                f_old = f_new
            return f_old

    def calculate_total_k_and_report(self, D_inner):
        total_k = 0.0; fitting_report = []
        
        fittings_list = list(self.fitting_k_factors.keys())
        
        for fitting in fittings_list:
            count = self.fitting_counts[fitting].get()
            k_factor = self.fitting_k_factors[fitting] 
            
            if count > 0:
                k = k_factor
                if fitting == "Küresel Vana (Tam Açık)":
                    kv = self.ball_valve_kv.get(); cv = self.ball_valve_cv.get(); D_inch = D_inner * 39.3701
                    if kv > 0:
                        # Kv'den Cv'ye dönüşüm: Cv = 1.156 * Kv
                        cv_calc = kv * 1.156 
                        # Cv'den K'ya dönüşüm
                        k = 891 * (D_inch ** 4) / (cv_calc ** 2) if cv_calc > 0 else k_factor
                        fitting_report.append(f"  {fitting}: {count} adet (Kv'den K={k:.2f})")
                    elif cv > 0:
                        k = 891 * (D_inch ** 4) / (cv ** 2) if cv > 0 else k_factor
                        fitting_report.append(f"  {fitting}: {count} adet (Cv'den K={k:.2f})")
                    else:
                        fitting_report.append(f"  {fitting}: {count} adet (Varsayılan K={k:.2f})")
                
                else:
                    fitting_report.append(f"  {fitting}: {count} adet x K={k_factor:.2f}")

                total_k += k * count

        return total_k, fitting_report

    def get_output_pressure_value(self, P_out_abs):
        if self.pressure_unit.get() == "Barg": return (P_out_abs / 1e5) - 1.01325
        elif self.pressure_unit.get() == "Bara": return P_out_abs / 1e5
        elif self.pressure_unit.get() == "Psig": return (P_out_abs / 6894.76) - 14.6959
        elif self.pressure_unit.get() == "Psia": return P_out_abs / 6894.76
        return P_out_abs

    def select_commercial_pipe(self, D_min_inner_mm, P_design_pa, material, F, E, T):
        SMYS = self.pipe_materials[material] * 1e6 # MPa -> Pa
        
        all_pipes = []
        for nominal, data in self.asme_b36_10m.items():
            OD = data["OD_mm"]
            # Boru mukavemet formülü (ASME B31.8 - Hoop Stress)
            t_required = (P_design_pa * (OD / 1000)) / (2 * SMYS * F * E * T) * 1000
            for schedule, t in data["schedules"].items():
                D_inner = OD - 2 * t
                all_pipes.append({
                    "nominal": nominal, "OD_mm": OD, "schedule": schedule, "t_mm": t,
                    "D_inner_mm": D_inner, "t_required_mm": t_required
                })

        def sort_key(pipe): 
            # NPS'i float değere dönüştürme (Örn: "1 1/4" -> 1.25)
            nps_str = pipe['nominal']
            try:
                if ' ' in nps_str:
                    parts = nps_str.split(' ')
                    nps_val = float(parts[0]) + (eval(parts[1].replace(' ', '+')) if len(parts) > 1 else 0)
                elif '/' in nps_str:
                    nps_val = eval(nps_str)
                else:
                    nps_val = float(nps_str.replace('"', ''))
            except:
                nps_val = 999 

            # Önce çapa, sonra et kalınlığına göre sırala
            return (nps_val, pipe['t_mm']) 
            
        all_pipes.sort(key=sort_key)

        for pipe in all_pipes:
            # 1. Hız Kriteri: İç çap, minimum gerekli çaptan büyük olmalı
            if pipe['D_inner_mm'] < D_min_inner_mm: continue
            # 2. Mukavemet Kriteri: Et kalınlığı, minimum gerekli kalınlıktan büyük olmalı
            if pipe['t_mm'] < pipe['t_required_mm']: continue
            self.log_message(f"Ticari Boru Seçimi: {pipe['nominal']}\" Sch {pipe['schedule']} (t_seçilen/t_gerekli: {pipe['t_mm']/pipe['t_required_mm']:.2f})", level="DEBUG")
            return pipe
        
        return None

    # --- Ana Hesaplama Akışı ---
    
    def start_calculate_thread(self):
        if not self.validate_inputs(): return
        self.calc_button.config(state="disabled", text="Hesaplanıyor...", bg="#8BC34A")
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, "Hesaplama devam ediyor...")
        self.log_message("HESAPLAMA BAŞLATILIYOR...")
        self.calc_queue = queue.Queue()
        threading.Thread(target=self.calculate_thread, daemon=True).start()
        self.check_calc_queue()
        
    def check_calc_queue(self):
        try:
            report_str = self.calc_queue.get_nowait()
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, report_str)
            self.calc_button.config(state="normal", text="Hesapla", bg="#4CAF50")
            if not report_str.startswith("Hata:"):
                 if "Viskozite Tahmin Modu" in report_str:
                     messagebox.showwarning("Hesaplama Tamamlandı (UYARI)", "CoolProp viskozite hesaplamasında hata verdi, tahminî değer kullanıldı. Raporu kontrol edin.")
                 else:
                     messagebox.showinfo("Hesaplama Tamamlandı", "Hesaplama başarıyla tamamlandı.")
            
        except queue.Empty:
            self.root.after(100, self.check_calc_queue)

    def calculate_thread(self):
        try:
            self.viscosity_fallback_warning = False
            P_in_abs = self.convert_pressure(self.pressure_value.get(), self.pressure_unit.get())
            T = self.convert_temperature(self.temperature_value.get(), self.temperature_unit.get())
            library_choice = self.thermo_library_choice.get()

            percentages = {gas_id: var.get() for gas_id, var in self.gas_components.items() if var.get() > 0}
            if not percentages: raise ValueError("En az bir gaz bileşeni seçin!")

            total_pct = sum(var.get() for var in self.gas_components.values())
            mole_fractions_raw = {gas_id: (var.get() / 100.0) for gas_id, var in self.gas_components.items() if var.get() > 0}
            
            # Yüzdelerin toplamı 100 değilse normalize et
            if total_pct != 100.0:
                 self.log_message(f"UYARI: Gaz bileşenleri toplamı %{total_pct:.2f}. Normalize ediliyor.", level="WARNING")
                 mole_fractions = {g: x * (100.0 / total_pct) for g, x in mole_fractions_raw.items()}
            else:
                 mole_fractions = mole_fractions_raw
                 
            if self.composition_type.get() == "Kütle %": 
                mole_fractions = self.mass_to_mole_fraction(mole_fractions_raw)
            
            gas_props_in = self.calculate_thermo_properties(P_in_abs, T, mole_fractions, library_choice)
            actual_density_in = gas_props_in["density"]; standard_density = gas_props_in["standard_density"]
            
            # Hacimsel akış (Q_akt) [m³/s]
            flow_rate_actual = self.convert_flow_rate(self.flow_value.get(), self.flow_unit.get(), actual_density_in, standard_density)
            m_dot = flow_rate_actual * actual_density_in # Kütlesel akış [kg/s]
            
            max_vel = self.max_velocity.get(); target = self.calc_target.get()

            # Tasarım Basıncı (Gauge PA cinsinden)
            P_design_gauge = self.design_pressure_value.get()
            if self.design_pressure_unit.get() == "Barg":
                 P_design_pa = P_design_gauge * 1e5
            elif self.design_pressure_unit.get() == "Psig":
                 P_design_pa = P_design_gauge * 6894.76
            elif self.design_pressure_unit.get() == "Bara": # Bara'yı gauge'a çevir (P_abs - P_atm)
                 P_design_pa = max(0, self.design_pressure_value.get() * 1e5 - 101325)
            elif self.design_pressure_unit.get() == "Psia": # Psia'yı gauge'a çevir (P_abs - P_atm)
                 P_design_pa = max(0, self.design_pressure_value.get() * 6894.76 - 101325)
            else:
                 P_design_pa = 0 # should not happen

            if target == "Minimum Çap":
                # A_min = Q_akt / v_max. D_min = sqrt(4*A_min / pi)
                D_min_inner_m = math.sqrt(4 * (flow_rate_actual / max_vel) / math.pi) 
                D_min_inner_mm = D_min_inner_m * 1000
                material = self.pipe_material.get(); F = self.factor_F.get(); E = self.factor_E.get(); T_factor = self.factor_T.get()
                selected_pipe = self.select_commercial_pipe(D_min_inner_mm, P_design_pa, material, F, E, T_factor)

                report = [
                    f"Hesaplama Türü: Minimum Çap", f"Termodinamik Model: {library_choice}", f"Akışkan Özelliği: {self.flow_property.get()}",
                    f"Tasarım Malzemesi: {material} (SMYS: {self.pipe_materials[material]} MPa)",
                    f"Tasarım Faktörleri: F={F:.2f}, E={E:.2f}, T={T_factor:.2f}",
                    "\n=== TERMODİNAMİK ÖZELLİKLER (GİRİŞ) ===",
                    f"Moleküler Ağırlık: {gas_props_in['MW']:.2f} g/mol", f"Z: {gas_props_in['Z']:.3f}",
                    f"Gerçek Yoğunluk: {actual_density_in:.2f} kg/m³", f"Standart Yoğunluk: {standard_density:.2f} kg/m³",
                    "\n=== KRİTERLER ===", f"Verilen Maks. Hız: {max_vel:.2f} m/s",
                    f"Kütlesel Akış (ṁ): {m_dot:.3f} kg/s",
                    f"Gerekli Minimum İç Çap (Hız Kriteri): {D_min_inner_mm:.2f} mm",
                    f"Tasarım Basıncı: {self.design_pressure_value.get():.2f} {self.design_pressure_unit.get()}",
                ]
                
                if selected_pipe:
                    D_inner_calc = selected_pipe["D_inner_mm"] / 1000
                    velocity_selected = flow_rate_actual / (math.pi * (D_inner_calc ** 2) / 4)
                    velocity_status = "✔ Uygun" if velocity_selected <= max_vel else "⚠ Hız limiti aşıldı!"

                    report.extend([
                        "\n=== SEÇİLEN TİCARİ BORU (ASME B36.10M / B31.8) ===",
                        f"Gerekli Min. Et Kalınlığı (Mukavemet): {selected_pipe['t_required_mm']:.2f} mm",
                        f"- Nominal Çap: {selected_pipe['nominal']}\"", 
                        f"- Et Kalınlığı: {selected_pipe['t_mm']:.2f} mm ({selected_pipe['schedule']})",
                        f"- İç Çap: {selected_pipe['D_inner_mm']:.2f} mm", 
                        f"- Hesaplanan Hız: {velocity_selected:.2f} m/s ({velocity_status})",
                        f"- Hoop Stress Emniyeti (t_seçilen/t_gerekli): {selected_pipe['t_mm']/selected_pipe['t_required_mm']:.2f}"
                    ])
                else:
                    report.append(f"\n❌ Uyarı: Belirtilen şartlarda uygun ticari boru bulunamadı!")
                    t_required_max_od = self.select_commercial_pipe(0, P_design_pa, material, F, E, T_factor)
                    if t_required_max_od: report.append(f"    (En büyük çaptaki mukavemet gereksinimi: {t_required_max_od['t_required_mm']:.2f} mm)")

                if self.viscosity_fallback_warning: report.append("\n⚠️ UYARI: CoolProp viskozite hesaplamasında başarısız oldu. Tahmin Modu kullanıldı.")
                self.calc_queue.put("\n".join(report))
                self.log_message("HESAPLAMA TAMAMLANDI: Minimum Çap Sonucu Raporlandı.")
                return

            # --- Çıkış Basıncı / Maksimum Uzunluk Hesapları ---
            D_outer = self.pipe_diameter.get() / 1000; t = self.pipe_thickness.get() / 1000
            D_inner = D_outer - 2 * t; A = math.pi * (D_inner ** 2) / 4
            velocity_in = flow_rate_actual / A # Giriş hızı

            SMYS = self.pipe_materials[self.pipe_material.get()]
            
            # Giriş basıncı mukavemet hesapları için kullanılır.
            P_in_gauge_pa = P_in_abs - 101325
            if P_in_gauge_pa < 0: P_in_gauge_pa = 0
            
            t_required = (P_in_gauge_pa * D_outer) / (2 * SMYS * 1e6 * self.factor_F.get() * self.factor_E.get() * self.factor_T.get()) * 1000

            epsilon = self.pipe_roughness[self.pipe_material.get()]; relative_roughness = epsilon / D_inner
            total_k, fitting_report = self.calculate_total_k_and_report(D_inner)
            flow_property = self.flow_property.get()
            
            if target == "Çıkış Basıncı":
                self.log_message(f"Hedef: Çıkış Basıncı ({flow_property})")
                L = self.pipe_length.get()
                delta_p_total_pa = 0.0
                delta_p_fittings = 0.0
                Re_final = 0; f = 0

                if flow_property == "Sıkıştırılamaz":
                    mu = gas_props_in['viscosity']; Re = (actual_density_in * velocity_in * D_inner) / mu
                    f = self.get_friction_factor(Re, relative_roughness)
                    
                    # Darcy-Weisbach
                    delta_p_pipe = f * (L / D_inner) * (actual_density_in * velocity_in ** 2) / 2
                    delta_p_fittings = total_k * (actual_density_in * velocity_in ** 2) / 2
                    delta_p_total_pa = delta_p_pipe + delta_p_fittings
                    
                    P_out_abs = max(MIN_PRESSURE_PA, P_in_abs - delta_p_total_pa)

                    gas_props_out = self.calculate_thermo_properties(P_out_abs, T, mole_fractions, library_choice)
                    velocity_out = velocity_in # Sıkıştırılamaz varsayımda hız sabit kalır.
                    Re_final = Re
                    f_final = f
                else: 
                    # Sıkıştırılabilir Akış (Basitleştirilmiş Ortalama Basınç İterasyonu)
                    P1, P2 = P_in_abs, P_in_abs * 0.9 # Başlangıç tahmini
                    delta_p_pipe = 0; delta_p_fittings = 0
                    
                    for iter_count in range(50):
                        P_avg = (P1 + P2) / 2
                        gas_props_avg = self.calculate_thermo_properties(P_avg, T, mole_fractions, library_choice)
                        rho_avg, mu_avg = gas_props_avg['density'], gas_props_avg['viscosity']; v_avg = m_dot / (rho_avg * A)
                        Re_new = (rho_avg * v_avg * D_inner) / mu_avg; f_new = self.get_friction_factor(Re_new, relative_roughness)
                        
                        delta_p_pipe_new = f_new * (L / D_inner) * (rho_avg * v_avg ** 2) / 2
                        delta_p_fittings_new = total_k * (rho_avg * v_avg ** 2) / 2
                        delta_p_total_pa_new = delta_p_pipe_new + delta_p_fittings_new
                        
                        P2_new = max(MIN_PRESSURE_PA, P1 - delta_p_total_pa_new)
                        
                        if abs(P2_new - P2) < 100.0: # 100 Pa tolerans
                             delta_p_pipe = delta_p_pipe_new
                             delta_p_fittings = delta_p_fittings_new
                             delta_p_total_pa = delta_p_total_pa_new
                             Re_final = Re_new
                             f_final = f_new
                             break
                        P2 = P2_new
                    
                    P_out_abs = P2
                    gas_props_out = self.calculate_thermo_properties(P_out_abs, T, mole_fractions, library_choice)
                    velocity_out = m_dot / (gas_props_out['density'] * A) if gas_props_out['density'] > 0 else 0
                
                max_velocity_val = max(velocity_in, velocity_out)
                velocity_status = "✔ Uygun" if max_velocity_val <= max_vel else f"⚠ Hız limiti aşıldı! ({max_velocity_val:.2f} m/s)"
                delta_p_total_user = self.convert_pressure_from_pa(delta_p_total_pa, self.pressure_unit.get())
                outlet_pressure = self.get_output_pressure_value(P_out_abs)
                
                report = self.build_report(
                    gas_props_in, gas_props_out, standard_density, T, library_choice,
                    velocity_in, velocity_out, max_vel, velocity_status, t_required, flow_property, 
                    Re_final, f_final, L,
                    delta_p_pipe, delta_p_fittings, delta_p_total_user, outlet_pressure, fitting_report, P_out_abs, total_k
                )

                if self.viscosity_fallback_warning: report.append("\n⚠️ UYARI: CoolProp viskozite hesaplamasında başarısız oldu. Tahmin Modu kullanıldı.")
                self.calc_queue.put("\n".join(report))
                self.log_message("HESAPLAMA TAMAMLANDI: Çıkış Basıncı Sonucu Raporlandı.")

            else: # Maksimum Uzunluk
                self.log_message(f"Hedef: Maksimum Uzunluk ({flow_property})")
                P_out_abs_target = self.convert_pressure(self.outlet_pressure_value.get(), self.outlet_pressure_unit.get())
                if P_out_abs_target >= P_in_abs: raise ValueError("Çıkış basıncı giriş basıncından büyük veya eşit olamaz!")
                delta_p_total_pa = P_in_abs - P_out_abs_target
                
                gas_props_out_target = self.calculate_thermo_properties(P_out_abs_target, T, mole_fractions, library_choice)
                velocity_out = m_dot / (gas_props_out_target['density'] * A) if gas_props_out_target['density'] > 0 else 0
                gas_props_out = gas_props_out_target

                if flow_property == "Sıkıştırılamaz":
                    mu = gas_props_in['viscosity']; Re = (actual_density_in * velocity_in * D_inner) / mu
                    f = self.get_friction_factor(Re, relative_roughness)
                    delta_p_fittings_in = total_k * (actual_density_in * velocity_in ** 2) / 2
                    
                    if delta_p_fittings_in >= delta_p_total_pa: raise ValueError("Boru elemanı kayıpları, izin verilen toplam basınç kaybını aşıyor! Lmax = 0")
                    available_delta_p_pipe = delta_p_total_pa - delta_p_fittings_in
                    
                    # L_max = (delta_p_pipe * 2 * Di) / (f * rho_in * v_in^2)
                    L_max = (available_delta_p_pipe * 2 * D_inner) / (f * actual_density_in * velocity_in ** 2)
                    
                    delta_p_fittings = delta_p_fittings_in
                    Re_final = Re
                    f_final = f
                    delta_p_pipe_final = available_delta_p_pipe
                else: 
                    # Sıkıştırılabilir Akış (Binary Search ile L'yi bulma)
                    L_low, L_high = 0.001, 10000000.0; L_max = None
                    P1 = P_in_abs
                    f_final = 0; Re_final = 0; delta_p_fittings_in = 0; delta_p_pipe_final = 0
                    
                    for iter_l in range(50):
                        L_mid = (L_low + L_high) / 2; P2_mid_calc = P1 * 0.9 # P2 başlangıç tahmini
                        
                        # İç iterasyon (Çıkış Basıncı hesaplama)
                        for _ in range(30):
                            P_avg = (P1 + P2_mid_calc) / 2
                            gas_props_avg = self.calculate_thermo_properties(P_avg, T, mole_fractions, library_choice)
                            rho_avg, mu_avg = gas_props_avg['density'], gas_props_avg['viscosity']; v_avg = m_dot / (rho_avg * A)
                            Re_avg = (rho_avg * v_avg * D_inner) / mu_avg; f_avg = self.get_friction_factor(Re_avg, relative_roughness)
                            
                            delta_p_pipe = f_avg * (L_mid / D_inner) * (rho_avg * v_avg ** 2) / 2
                            delta_p_fittings_avg = total_k * (rho_avg * v_avg ** 2) / 2
                            P2_new = max(MIN_PRESSURE_PA, P1 - (delta_p_pipe + delta_p_fittings_avg))
                            
                            if abs(P2_new - P2_mid_calc) < 100: break # 100 Pa tolerans
                            P2_mid_calc = P2_new
                            
                        # Dış iterasyon (L'yi ayarlama)
                        if P2_mid_calc > P_out_abs_target: L_low = L_mid
                        else: L_high = L_mid
                        
                        if abs(L_high - L_low) < 0.1: L_max = L_mid; break # 10 cm tolerans
                    
                    if L_max is None: L_max = L_mid
                    
                    # Final durumdaki ortalama koşulları ve kayıpları hesaplama
                    P_avg_final = (P_in_abs + P_out_abs_target) / 2
                    gas_props_avg_final = self.calculate_thermo_properties(P_avg_final, T, mole_fractions, library_choice)
                    rho_avg_final = gas_props_avg_final['density']; v_avg_final = m_dot / (rho_avg_final * A)
                    Re_final = (rho_avg_final * v_avg_final * D_inner) / gas_props_avg_final['viscosity']
                    f_final = self.get_friction_factor(Re_final, relative_roughness)
                    
                    delta_p_pipe_final = f_final * (L_max / D_inner) * (rho_avg_final * v_avg_final ** 2) / 2
                    delta_p_fittings_in = total_k * (rho_avg_final * v_avg_final ** 2) / 2
                    
                max_velocity_val = max(velocity_in, velocity_out)
                velocity_status = "✔ Uygun" if max_velocity_val <= max_vel else f"⚠ Hız limiti aşıldı! ({max_velocity_val:.2f} m/s)"

                length_str = f"{L_max:.2f} m" if L_max < 10000 else f"{L_max/1000:.2f} km"

                report = [
                    f"Hesaplama Türü: Maksimum Uzunluk", f"Termodinamik Model: {library_choice}",
                    f"Akışkan Özelliği: {flow_property}",
                    f"Giriş Basıncı: {self.get_output_pressure_value(P_in_abs):.2f} {self.pressure_unit.get()}",
                    f"İstenen Çıkış Basıncı: {self.outlet_pressure_value.get():.2f} {self.outlet_pressure_unit.get()}",
                    "\n=== TERMODİNAMİK ÖZELLİKLER (GİRİŞ) ===", f"Moleküler Ağırlık: {gas_props_in['MW']:.2f} g/mol", f"Z: {gas_props_in['Z']:.3f}",
                    f"Gerçek Yoğunluk: {actual_density_in:.2f} kg/m³", f"Standart Yoğunluk: {standard_density:.2f} kg/m³",
                ]
                if flow_property == "Sıkıştırılabilir":
                    report.extend(["\n=== TERMODİNAMİK ÖZELLİKLER (ÇIKIŞ) ===", f"Z: {gas_props_out['Z']:.3f}", f"Gerçek Yoğunluk: {gas_props_out['density']:.2f} kg/m³",])
                report.extend([
                    "\n=== AKIŞ ANALİZİ (Ortalama Şartlar) ===", f"Giriş Hızı: {velocity_in:.2f} m/s", f"Çıkış Hızı: {velocity_out:.2f} m/s",
                    f"Durum: {velocity_status}", "\n=== MUKAVEMET HESAPLARI (ASME B31.8) ===",
                    f"Gerekli Min. Et Kalınlığı: {t_required:.2f} mm", f"Seçilen Et Kalınlığı: {self.pipe_thickness.get():.2f} mm",
                    f"Emniyet Faktörü: {self.pipe_thickness.get()/t_required:.2f}" if t_required > 0 else "Emniyet Faktörü: -",
                    f"\n=== SÜRTÜNME KATSAYILARI (Ortalama) ===",
                    f"Reynolds Sayısı: {Re_final:.2f}", f"Sürtünme Faktörü (f): {f_final:.4f}",
                    f"Toplam K: {total_k:.2f}",
                    "\n=== SONUÇ ===", f"Maksimum Boru Uzunluğu: {length_str}",
                    f"Toplam Basınç Farkı: {delta_p_total_pa/1e5:.2f} bara ({self.convert_pressure_from_pa(delta_p_total_pa, self.pressure_unit.get()):.2f} {self.pressure_unit.get()})",
                    f"Boru Kaybı (ΔPpipe): {delta_p_pipe_final/1e5:.2f} bara",
                    f"Eleman Kaybı (ΔPfittings): {delta_p_fittings_in/1e5:.2f} bara",
                ])
                if self.viscosity_fallback_warning: report.append("\n⚠️ UYARI: CoolProp viskozite hesaplamasında başarısız oldu. Tahmin Modu kullanıldı.")
                self.calc_queue.put("\n".join(report))
                self.log_message("HESAPLAMA TAMAMLANDI: Maksimum Uzunluk Sonucu Raporlandı.")

        except Exception as e:
            error_msg = f"Hata: {str(e)}"
            self.log_message(error_msg, level="ERROR")
            self.calc_queue.put(error_msg)


    def build_report(self, gas_props_in, gas_props_out, standard_density, T, library_choice,
                     velocity_in, velocity_out, max_vel, velocity_status, t_required, flow_property, Re, f, L,
                     delta_p_pipe, delta_p_fittings, delta_p_total_user, outlet_pressure, fitting_report, P_out_abs, total_k):
        
        report = []
        report.append(f"Hesaplama Türü: Çıkış Basıncı")
        report.append(f"Termodinamik Model: {library_choice}")
        report.append(f"Akışkan Özelliği: {flow_property}")
        report.append(f"Boru Uzunluğu: {L:.2f} m")
        report.append(f"Birimler: Basınç ({self.pressure_unit.get()}: {'Gösterge' if 'g' in self.pressure_unit.get() else 'Mutlak'})")
        
        report.append("\n=== TERMODİNAMİK ÖZELLİKLER (GİRİŞ) ===")
        report.append(f"Moleküler Ağırlık: {gas_props_in['MW']:.2f} g/mol")
        report.append(f"Cp: {gas_props_in.get('Cp', 0):.2f} kJ/kg·K")
        report.append(f"Cv: {gas_props_in.get('Cv', 0):.2f} kJ/kg·K")
        report.append(f"Z: {gas_props_in['Z']:.3f}")
        report.append(f"Gerçek Yoğunluk: {gas_props_in['density']:.2f} kg/m³")
        report.append(f"Standart Yoğunluk: {standard_density:.2f} kg/m³")
        report.append(f"Viskozite: {gas_props_in['viscosity']*1e6:.4f} µPa·s")
        
        if library_choice == "Pseudo-Critical (Kay's Rule)":
            report.append(f"Ppc: {gas_props_in.get('Ppc', 0)/1e5:.2f} bara, Tpc: {gas_props_in.get('Tpc', 0):.2f} K")
            report.append(f"Pr: {gas_props_in.get('Pr', 0):.2f}, Tr: {gas_props_in.get('Tr', 0):.2f}")
            
        if flow_property == "Sıkıştırılabilir":
            report.append("\n=== TERMODİNAMİK ÖZELLİKLER (ÇIKIŞ) ===")
            report.append(f"Z: {gas_props_out['Z']:.3f}")
            report.append(f"Gerçek Yoğunluk: {gas_props_out['density']:.2f} kg/m³")
            report.append(f"Viskozite: {gas_props_out['viscosity']*1e6:.4f} µPa·s")
            
        report.append("\n=== AKIŞ ANALİZİ ===")
        if flow_property == "Sıkıştırılamaz": 
            report.append(f"Hız: {velocity_in:.2f} m/s")
        else: 
            report.append(f"Giriş Hızı: {velocity_in:.2f} m/s")
            report.append(f"Çıkış Hızı: {velocity_out:.2f} m/s")
            
        report.append(f"Maks. İzin Verilen Hız: {max_vel:.2f} m/s")
        report.append(f"Durum: {velocity_status}")
        
        report.append("\n=== MUKAVEMET HESAPLARI (ASME B31.8) ===")
        report.append(f"Gerekli Min. Et Kalınlığı: {t_required:.2f} mm")
        report.append(f"Seçilen Et Kalınlığı: {self.pipe_thickness.get():.2f} mm")
        report.append(f"Emniyet Faktörü: {self.pipe_thickness.get()/t_required:.2f}" if t_required > 0 else "Emniyet Faktörü: -")
        
        report.append("\n=== BASINÇ KAYBI ===")
        if Re is not None and f is not None:
              report.append(f"Reynolds: {Re:.2f}, f: {f:.4f}")
        
        report.append(f"Boru Kaybı: {self.convert_pressure_from_pa(delta_p_pipe, self.pressure_unit.get()):.2f} {self.pressure_unit.get()}")
        report.append("\n=== BORU ELEMANLARI ===")
        report.extend(fitting_report)
        report.append(f"Toplam K: {total_k:.2f}")
        report.append(f"Eleman Kaybı: {self.convert_pressure_from_pa(delta_p_fittings, self.pressure_unit.get()):.2f} {self.pressure_unit.get()}")
        report.append(f"Toplam Kayıp: {delta_p_total_user:.2f} {self.pressure_unit.get()}")
        report.append(f"Çıkış Basıncı: {outlet_pressure:.2f} {self.pressure_unit.get()}")
        
        if P_out_abs < 101325 and self.pressure_unit.get() in ["Barg", "Psig"]:
            report.append("\n⚠ Uyarı: Çıkış basıncı atmosferik basıncın altında!")
        return report

    def print_report(self):
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.report_text.get(1.0, tk.END))
                messagebox.showinfo("Başarılı", "Rapor kaydedildi!")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def show_about(self):
        about_window = tk.Toplevel(self.root)
        about_window.title("Hakkında - Formüller ve Referanslar")
        about_window.geometry("800x650")
        text = ScrolledText(about_window, wrap=tk.WORD, font=("Arial", 10))
        text.pack(fill="both", expand=True)
        
        info = """
PROGRAM DETAYI VE REFERANSLAR
=============================

Bu program, Gaz Kompresörleri, Pompalar, Turbo Makinalar ve Akışkanlar Mekaniği alanındaki uzmanlığınızı yansıtacak şekilde tasarlanmıştır.

KULLANILAN TEMEL PRENSİPLER:

1.  AKIM ANALİZİ:
    - **Hız Kriteri:** Hız kontrolü için minimum gerekli iç çap hesaplanır:
        $$A_{\\text{min}} = \\frac{Q_{\\text{akt}}}{v_{\\text{max}}}$$
    - **Sürtünme Faktörü (f):** Darcy-Weisbach denklemi için Colebrook-White korelasyonunun iteratif çözümü kullanılır.
    - **Basınç Kaybı (\\Delta P):** Darcy-Weisbach denklemi ve lokal kayıp katsayıları (\\Sigma K):
        $$\\Delta P_{\\text{toplam}} = f \\cdot \\frac{L}{D_{\\text{i}}} \\cdot \\frac{\\rho \\cdot v^2}{2} + \\sum K \\cdot \\frac{\\rho \\cdot v^2}{2}$$
    - **Sıkıştırılabilir Akış:** İzotermal akış varsayımı altında ortalama koşulların iteratif çözümü.

2.  TERMODİNAMİK MODELLER (Z, \\rho, Cp, \\mu Hesaplamaları):
    - **CoolProp (Yüksek Hassasiyet):** Helmholtz Serbest Enerji denklemlerine dayalı, en yüksek doğruluk seviyesinde termodinamik özellik hesaplaması yapar. Viskozite hesaplamasındaki kritik nokta hataları, Lee-Kesler/LBC korelasyonlarına dayalı kaba tahmin ile güvenli bir şekilde aşılır.
    - **Peng-Robinson (PR EOS):** Hidrokarbon işleme endüstrisinde faz denge ve yoğunluk hesaplamaları için Kübik Durum Denklemi standardıdır.
    - **Soave-Redlich-Kwong (SRK EOS):** PR'a alternatif olarak kullanılan bir diğer yaygın Kübik Durum Denklemi.
    - **Pseudo-Critical (Kay's Rule):** Karışımın sahte-kritik noktalarını belirleyerek Z faktörünü Standing-Katz diyagramı korelasyonları ile tahmin eden, hızlı mühendislik kestirim modelidir.

3.  BORU MUKAVEMETİ VE SEÇİMİ:
    - **Boru Et Kalınlığı (ASME B31.8 - Gaz İletim):** Gerekli minimum et kalınlığı (Hoop Stress için) aşağıdaki formülle hesaplanır:
        $$t_{\\text{gerekli}} = \\frac{P_{\\text{tasarım}} \\cdot D_{\\text{d}}}{2 \\cdot SMYS \\cdot F \\cdot E \\cdot T}$$
        $P_{\\text{tasarım}}$: Tasarım Basıncı (Gauge) | $D_{\\text{d}}$: Dış Çap | $SMYS$: Malzemenin Akma Dayanımı | $F$, $E$, $T$: ASME B31.8 tasarım faktörleri.
    - **Ticari Boru Seçimi:** ASME B36.10M-2018 standardına göre listelenen tüm ticari NPS ve Schedule'lar denenir ve hem hız kriterini hem de mukavemet kriterini sağlayan en küçük boru seçilir.

REFERANSLAR:
- ASME B31.8 (Gas Transmission and Distribution Piping Systems)
- ASME B36.10M (Welded and Seamless Wrought Steel Pipe)
- CoolProp Documentation (EOS implementations for fluid properties)
- Peng, D.-Y.; Robinson, D. B. (1976). Ind. Eng. Chem. Fundam., 15(1), 59-64.
- Soave, G. (1972). Chem. Eng. Sci., 27(6), 1197-1203.
- Kay, W.B. (1936). Ind. Eng. Chem., 28(9), 1014-1019.
        """
        text.insert(tk.END, info)
        text.config(state=tk.DISABLED)

    def show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("Yardım - Kullanım Kılavuzu")
        help_window.geometry("800x650")
        text = ScrolledText(help_window, wrap=tk.WORD, font=("Arial", 10))
        text.pack(fill="both", expand=True)
        
        guide = """
KULLANIM KILAVUZU
=================

Program, gaz akış, basınç kaybı ve boru mukavemet hesaplamalarını mühendislik standartlarına göre yapar.

1.  GAZ KARIŞIMI:
    - Bileşenleri seçip yüzdeleri girin. **Canlı Arama** ile gaz listesini kolayca filtreleyebilirsiniz.
    - Bileşim Türü (Mol % / Kütle %) seçimi yapın.

2.  GİRİŞ KOŞULLARI:
    - Giriş Basıncı, Sıcaklık ve birimlerini seçin.

3.  AKIŞ VE TASARIM KRİTERLERİ:
    - **Akış Değeri** ve **Maks. Hız** limitini girin.
    - **Tasarım Basıncı**, **Malzeme** ve ASME B31.8 tasarım faktörlerini (F, E, T) belirleyin. Bu veriler, boru mukavemet kontrolü için kritik öneme sahiptir.

4.  HESAPLAMA SEÇENEKLERİ:
    - **Akışkan Özelliği:** Akışkanın boru boyunca yoğunluk değişimini ihmal edip etmeyeceğinizi seçin. Uzun boru hatları için "Sıkıştırılabilir" seçilmelidir.
    - **Termodinamik Model:** Gaz özelliklerini hesaplamak için kullanılacak matematiksel modeli seçin (Örn: Peng-Robinson veya CoolProp).
    - **Hesaplanacak Değer:**
        - **Çıkış Basıncı:** Belirtilen uzunluk için çıkış basıncını hesaplar.
        - **Maksimum Uzunluk:** Giriş ve istenen çıkış basıncı arasındaki maksimum boru uzunluğunu hesaplar.
        - **Minimum Çap:** Hız limiti ve tasarım basıncına göre **en hafif ticari boruyu** seçer (ASME B36.10M listesi taranır).

5.  BORU GEOMETRİSİ VE ELEMANLARI:
    - **Çap / Et Kalınlığı:** Sadece "Çıkış Basıncı" ve "Maksimum Uzunluk" modlarında kullanılır.
    - **Boru Elemanları:** Boru hattındaki valf ve dirsek gibi ekipmanlardan kaynaklanan lokal kayıpları hesaplamak için adetlerini girin. Bu kısım **iki kolonlu ergonomik** olarak düzenlenmiştir. Kv/Cv girişleri, küresel vanaların K-faktörünü daha hassas hesaplamaya yarar.

6.  PROGRAM LOGLARI SEKmesi:
    - Tüm iterasyonlar, kritik kararlar ve hatalar bu sekmede zaman damgasıyla takip edilebilir.
"""
        text.insert(tk.END, guide)
        text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = GasFlowCalculatorApp(root)
    root.mainloop()