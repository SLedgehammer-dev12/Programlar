from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from app_metadata import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    RELEASES_PAGE_URL,
    SPEC_DOCUMENT_CODE,
    SPEC_DOCUMENT_TITLE,
)
from coefficient_reference import find_reference_point, get_reference_option_labels
from hydrotest_core import (
    SEAMLESS_PIPE_K,
    WELDED_PIPE_K,
    AirContentInputs,
    PipeGeometry,
    PipeSection,
    PressureVariationInputs,
    ValidationError,
    calculate_b_coefficient,
    calculate_water_compressibility_a,
    calculate_water_thermal_expansion_beta,
    evaluate_air_content_test,
    evaluate_pressure_variation_test,
)
from pipe_catalog import find_pipe_size, find_schedule, get_pipe_size_options, get_schedule_options
from updater import UpdateError, UpdateInfo, fetch_latest_update_info, install_update, open_release_page

DEFAULT_DECISION_TITLE = "Henuz degerlendirme yapilmadi"
DEFAULT_DECISION_STATUS = "BEKLIYOR"
DEFAULT_DECISION_SUMMARY = (
    "Girdileri tamamlayip ilgili testi calistirdiginizde nihai karar burada gosterilecek."
)
AUTO_A_MODE = "Otomatik - Su ozelliginden hesapla"
REFERENCE_A_MODE = "Referans - Hazir dogrulanmis nokta"
MANUAL_A_MODE = "Manuel - Tablo/prosedur degeri gir"
AUTO_B_MODE = "Otomatik - Su beta ve celik alpha"
REFERENCE_B_MODE = "Referans - Hazir dogrulanmis nokta"
MANUAL_B_MODE = "Manuel - Tablo/prosedur degeri gir"


class HydrostaticTestApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_TITLE} v{APP_VERSION}")
        self.root.geometry("1240x820")
        self.root.minsize(1080, 760)

        self.geometry_vars = {
            "outside_diameter_mm": tk.StringVar(),
            "wall_thickness_mm": tk.StringVar(),
            "length_m": tk.StringVar(),
        }
        self.geometry_catalog_vars = {
            "size_option": tk.StringVar(),
            "schedule_option": tk.StringVar(),
        }
        self.air_vars = {
            "temperature_c": tk.StringVar(),
            "pressure_bar": tk.StringVar(),
            "a_micro_per_bar": tk.StringVar(),
            "pressure_rise_bar": tk.StringVar(value="1.0"),
            "k_factor": tk.StringVar(value=f"{WELDED_PIPE_K:.2f}"),
            "actual_added_water_m3": tk.StringVar(),
        }
        self.pressure_vars = {
            "temperature_c": tk.StringVar(),
            "pressure_bar": tk.StringVar(),
            "a_micro_per_bar": tk.StringVar(),
            "b_micro_per_c": tk.StringVar(),
            "delta_t_c": tk.StringVar(),
            "actual_pressure_change_bar": tk.StringVar(),
        }
        self.air_a_mode_var = tk.StringVar(value=AUTO_A_MODE)
        self.pressure_a_mode_var = tk.StringVar(value=AUTO_A_MODE)
        self.pressure_b_mode_var = tk.StringVar(value=AUTO_B_MODE)
        self.air_a_reference_var = tk.StringVar()
        self.pressure_a_reference_var = tk.StringVar()
        self.pressure_b_reference_var = tk.StringVar()
        self.k_preset_var = tk.StringVar(value="Kaynakli boru - 1.02")
        self.steel_preset_var = tk.StringVar(value="Karbon celik - 12.0")
        self.use_b_helper_var = tk.BooleanVar(value=True)
        self.b_helper_vars = {
            "steel_alpha_micro_per_c": tk.StringVar(value="12.0"),
            "water_beta_micro_per_c": tk.StringVar(),
        }
        self.banner_var = tk.StringVar(
            value=(
                "Akis: geometriyi girin, katsayilari kontrol edin ve ilgili testi degerlendirin. "
                "Helper aciksa B otomatik uretilecek, A ise gerektiginde yeniden hesaplanacaktir."
            )
        )
        self.section_feedback_vars = {
            "geometry": tk.StringVar(),
            "air": tk.StringVar(),
            "pressure": tk.StringVar(),
        }
        self.live_notice_var = tk.StringVar(value="Canli kontrol hazir. Girdiler izleniyor.")
        self.geometry_summary_var = tk.StringVar(
            value="Geometri girildiginde ic cap, ic yaricap ve hacim ozeti burada gosterilir."
        )
        self.segment_summary_var = tk.StringVar(
            value="Segmentasyon kullanilmazsa ustteki geometri alanlari tek boru kesiti olarak kullanilir."
        )
        self.workflow_hint_var = tk.StringVar()
        self.helper_mode_summary_var = tk.StringVar()
        self.decision_title_var = tk.StringVar(value=DEFAULT_DECISION_TITLE)
        self.decision_status_var = tk.StringVar(value=DEFAULT_DECISION_STATUS)
        self.decision_summary_var = tk.StringVar(value=DEFAULT_DECISION_SUMMARY)
        self.update_status_var = tk.StringVar(value=f"Surum {APP_VERSION} aktif. Guncelleme henuz kontrol edilmedi.")
        self.update_detail_var = tk.StringVar(
            value="Acilista otomatik kontrol yapilir. Isterseniz elle de guncelleme kontrolu baslatabilirsiniz."
        )
        self.coefficient_states = {
            "air_a": "empty",
            "pressure_a": "empty",
            "pressure_b": "empty",
        }
        self.coefficient_status_vars = {
            "air_a": tk.StringVar(value="Bekleniyor"),
            "pressure_a": tk.StringVar(value="Bekleniyor"),
            "pressure_b": tk.StringVar(value="Bekleniyor"),
        }
        self._programmatic_coefficient_updates: set[str] = set()
        self.entry_widgets: dict[str, ttk.Entry] = {}
        self.field_meta: dict[str, dict[str, str | bool]] = {}
        self.field_message_vars: dict[str, tk.StringVar] = {}
        self.touched_fields: set[str] = set()
        self.report_entries: list[str] = []
        self.geometry_segments: list[dict[str, object]] = []
        self.latest_update_info: UpdateInfo | None = None
        self.update_check_in_progress = False
        self.update_install_in_progress = False

        self._build_menu()
        self._build_ui()
        self._register_traces()
        self._bind_shortcuts()
        self._refresh_coefficient_statuses()
        self._refresh_geometry_summary()
        self._update_workflow_hint()
        self._on_air_a_mode_changed()
        self._on_pressure_a_mode_changed()
        self._apply_b_helper_mode()
        self.root.after(1200, self._check_for_updates_on_startup)

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Raporu Kaydet", command=self._save_report)
        file_menu.add_separator()
        file_menu.add_command(label="Cikis", command=self.root.destroy)
        menu_bar.add_cascade(label="Dosya", menu=file_menu)

        report_menu = tk.Menu(menu_bar, tearoff=False)
        report_menu.add_command(label="Raporu Kaydet", command=self._save_report)
        report_menu.add_command(label="Sonuclari Temizle", command=self._clear_results)
        menu_bar.add_cascade(label="Rapor", menu=report_menu)

        update_menu = tk.Menu(menu_bar, tearoff=False)
        update_menu.add_command(label="Guncelleme Kontrol Et", command=self._check_for_updates_manually)
        update_menu.add_command(label="Guncellemeyi Uygula", command=self._apply_available_update)
        update_menu.add_separator()
        update_menu.add_command(label="Release Sayfasini Ac", command=self._open_release_page)
        menu_bar.add_cascade(label="Guncelleme", menu=update_menu)

        about_menu = tk.Menu(menu_bar, tearoff=False)
        about_menu.add_command(label="Uygulama Hakkinda", command=self._show_about_dialog)
        menu_bar.add_cascade(label="Hakkinda", menu=about_menu)

        self.root.configure(menu=menu_bar)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)

        intro = ttk.Label(
            container,
            text=(
                "Bu arayuz, hidrostatik test degerlendirmesini sahada daha hizli ve daha kontrollu "
                "yapmak icin tasarlandi. Solda veri girisi, sagda ise karar, katsayi durumu ve "
                "oturum kaydi birlikte gorulur. Mevcut akista hesap ve isaret tanimlari "
                f"{SPEC_DOCUMENT_CODE} {SPEC_DOCUMENT_TITLE} ile hizalanmistir."
            ),
            wraplength=1180,
            justify="left",
        )
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self.banner_label = tk.Label(
            container,
            textvariable=self.banner_var,
            anchor="w",
            justify="left",
            bg="#EEF4FF",
            fg="#16365D",
            padx=10,
            pady=8,
        )
        self.banner_label.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        geometry_frame = ttk.LabelFrame(container, text="Boru Kesiti", padding=12)
        geometry_frame.grid(row=2, column=0, sticky="ew")
        geometry_frame.columnconfigure(1, weight=1)
        geometry_frame.columnconfigure(3, weight=1)
        geometry_frame.columnconfigure(5, weight=1)

        ttk.Label(geometry_frame, text="ASME B36.10 NPS").grid(row=0, column=0, sticky="w", pady=6)
        self.pipe_size_combo = ttk.Combobox(
            geometry_frame,
            textvariable=self.geometry_catalog_vars["size_option"],
            state="readonly",
            values=get_pipe_size_options(),
        )
        self.pipe_size_combo.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=6)
        self.pipe_size_combo.bind("<<ComboboxSelected>>", self._on_pipe_size_selected)

        ttk.Label(geometry_frame, text="Schedule / Et kalinligi").grid(row=0, column=2, sticky="w", pady=6)
        self.pipe_schedule_combo = ttk.Combobox(
            geometry_frame,
            textvariable=self.geometry_catalog_vars["schedule_option"],
            state="readonly",
            values=(),
        )
        self.pipe_schedule_combo.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=6)
        ttk.Button(geometry_frame, text="Listeden Doldur", command=self._apply_catalog_selection).grid(
            row=0, column=4, sticky="w", pady=6
        )

        self._add_entry(
            geometry_frame,
            row=1,
            label="Dis cap (mm)",
            variable=self.geometry_vars["outside_diameter_mm"],
            field_key="geometry.outside_diameter_mm",
        )
        self._add_entry(
            geometry_frame,
            row=1,
            label="Et kalinligi (mm)",
            variable=self.geometry_vars["wall_thickness_mm"],
            field_key="geometry.wall_thickness_mm",
            column=2,
        )
        self._add_entry(
            geometry_frame,
            row=2,
            label="Hat uzunlugu (m)",
            variable=self.geometry_vars["length_m"],
            field_key="geometry.length_m",
        )
        segment_actions = ttk.Frame(geometry_frame)
        segment_actions.grid(row=2, column=2, columnspan=3, sticky="w", pady=6)
        ttk.Button(segment_actions, text="Segment Ekle", command=self._add_geometry_segment).pack(side="left")
        ttk.Button(segment_actions, text="Secili Segmenti Sil", command=self._remove_selected_segment).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(segment_actions, text="Segmentleri Temizle", command=self._clear_geometry_segments).pack(
            side="left", padx=(8, 0)
        )

        segment_frame = ttk.Frame(geometry_frame)
        segment_frame.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        segment_frame.columnconfigure(0, weight=1)
        self.segment_tree = ttk.Treeview(
            segment_frame,
            columns=("segment", "nps", "schedule", "od", "wt", "length"),
            show="headings",
            height=5,
        )
        self.segment_tree.heading("segment", text="Segment")
        self.segment_tree.heading("nps", text="NPS / DN")
        self.segment_tree.heading("schedule", text="Schedule")
        self.segment_tree.heading("od", text="OD (mm)")
        self.segment_tree.heading("wt", text="Et (mm)")
        self.segment_tree.heading("length", text="Uzunluk (m)")
        self.segment_tree.column("segment", width=70, anchor="center")
        self.segment_tree.column("nps", width=140, anchor="w")
        self.segment_tree.column("schedule", width=150, anchor="w")
        self.segment_tree.column("od", width=90, anchor="e")
        self.segment_tree.column("wt", width=90, anchor="e")
        self.segment_tree.column("length", width=100, anchor="e")
        self.segment_tree.grid(row=0, column=0, sticky="ew")
        segment_scroll = ttk.Scrollbar(segment_frame, orient="vertical", command=self.segment_tree.yview)
        segment_scroll.grid(row=0, column=1, sticky="ns")
        self.segment_tree.configure(yscrollcommand=segment_scroll.set)
        ttk.Label(
            geometry_frame,
            textvariable=self.section_feedback_vars["geometry"],
            foreground="#A4262C",
            wraplength=1140,
            justify="left",
        ).grid(row=4, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Label(
            geometry_frame,
            textvariable=self.geometry_summary_var,
            wraplength=1140,
            justify="left",
            foreground="#35506B",
        ).grid(row=5, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Label(
            geometry_frame,
            textvariable=self.segment_summary_var,
            wraplength=1140,
            justify="left",
            foreground="#35506B",
        ).grid(row=6, column=0, columnspan=6, sticky="w", pady=(6, 0))

        content_pane = ttk.Panedwindow(container, orient="horizontal")
        content_pane.grid(row=3, column=0, sticky="nsew", pady=12)

        left_panel = ttk.Frame(content_pane, padding=(0, 0, 12, 0))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=1)
        content_pane.add(left_panel, weight=3)

        side_panel = ttk.Frame(content_pane)
        side_panel.columnconfigure(0, weight=1)
        side_panel.rowconfigure(4, weight=1)
        content_pane.add(side_panel, weight=2)

        self.notebook = ttk.Notebook(left_panel)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        air_frame = ttk.Frame(self.notebook, padding=16)
        pressure_frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(air_frame, text="Hava Icerik Testi")
        self.notebook.add(pressure_frame, text="Basinc Degisim Testi")

        for frame in (air_frame, pressure_frame):
            frame.columnconfigure(0, weight=1)

        self._build_air_tab(air_frame)
        self._build_pressure_tab(pressure_frame)

        update_frame = ttk.LabelFrame(side_panel, text="Uygulama ve Guncelleme", padding=12)
        update_frame.grid(row=0, column=0, sticky="ew")
        update_frame.columnconfigure(0, weight=1)
        ttk.Label(
            update_frame,
            text=f"Surum: {APP_VERSION}",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            update_frame,
            textvariable=self.update_status_var,
            wraplength=340,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(
            update_frame,
            textvariable=self.update_detail_var,
            wraplength=340,
            justify="left",
            foreground="#35506B",
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        update_actions = ttk.Frame(update_frame)
        update_actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(
            update_actions,
            text="Guncelleme Kontrol Et",
            command=self._check_for_updates_manually,
        ).pack(side="left")
        ttk.Button(
            update_actions,
            text="Guncellemeyi Uygula",
            command=self._apply_available_update,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            update_actions,
            text="Release Sayfasi",
            command=self._open_release_page,
        ).pack(side="left", padx=(8, 0))

        workflow_frame = ttk.LabelFrame(side_panel, text="Hizli Akis", padding=12)
        workflow_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        workflow_frame.columnconfigure(0, weight=1)
        ttk.Label(
            workflow_frame,
            textvariable=self.workflow_hint_var,
            wraplength=340,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            workflow_frame,
            textvariable=self.live_notice_var,
            wraplength=340,
            justify="left",
            foreground="#35506B",
        ).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        workflow_actions = ttk.Frame(workflow_frame)
        workflow_actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(
            workflow_actions,
            text="Aktif Testi Degerlendir",
            command=self._run_selected_test,
        ).pack(side="left")
        ttk.Button(
            workflow_actions,
            text="Katsayilari Yenile",
            command=self._recalculate_active_coefficients,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            workflow_actions,
            text="Aktif Formu Temizle",
            command=self._clear_active_form,
        ).pack(side="left", padx=(8, 0))

        coefficient_frame = ttk.LabelFrame(side_panel, text="Katsayi Durumu", padding=12)
        coefficient_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        coefficient_frame.columnconfigure(1, weight=1)
        ttk.Label(coefficient_frame, text="Hava testi A").grid(row=0, column=0, sticky="w")
        ttk.Label(
            coefficient_frame,
            textvariable=self.coefficient_status_vars["air_a"],
            foreground="#8A6D3B",
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(coefficient_frame, text="Basinc testi A").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(
            coefficient_frame,
            textvariable=self.coefficient_status_vars["pressure_a"],
            foreground="#8A6D3B",
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(coefficient_frame, text="Basinc testi B").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(
            coefficient_frame,
            textvariable=self.coefficient_status_vars["pressure_b"],
            foreground="#8A6D3B",
        ).grid(row=2, column=1, sticky="w", pady=(6, 0))
        ttk.Label(
            coefficient_frame,
            textvariable=self.helper_mode_summary_var,
            wraplength=340,
            justify="left",
            foreground="#35506B",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        decision_frame = ttk.LabelFrame(side_panel, text="Nihai Karar", padding=12)
        decision_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        decision_frame.columnconfigure(1, weight=1)

        ttk.Label(
            decision_frame,
            textvariable=self.decision_title_var,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.decision_status_label = tk.Label(
            decision_frame,
            textvariable=self.decision_status_var,
            bg="#EEF2FF",
            fg="#243B73",
            padx=12,
            pady=6,
            font=("Segoe UI", 10, "bold"),
        )
        self.decision_status_label.grid(row=0, column=1, sticky="e")
        tk.Label(
            decision_frame,
            textvariable=self.decision_summary_var,
            justify="left",
            anchor="w",
            wraplength=340,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        results_frame = ttk.LabelFrame(side_panel, text="Oturum Kaydi", padding=12)
        results_frame.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        self.results_text = ScrolledText(results_frame, height=18, wrap="word")
        self.results_text.grid(row=0, column=0, sticky="nsew")
        self.results_text.insert(
            "end",
            "Oturum sonuclari burada zaman damgasi ile listelenecek.\n"
            "Not: Bu panel bir karar ozeti degil, kayit gunlugudur.\n",
        )
        self.results_text.configure(state="disabled")

        results_actions = ttk.Frame(results_frame)
        results_actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(results_actions, text="Raporu Kaydet", command=self._save_report).pack(side="left")
        ttk.Button(results_actions, text="Sonuclari Temizle", command=self._clear_results).pack(
            side="left", padx=(8, 0)
        )

    def _build_air_tab(self, frame: ttk.Frame) -> None:
        frame.rowconfigure(3, weight=1)

        conditions_frame = ttk.LabelFrame(frame, text="1. Test Kosullari", padding=12)
        conditions_frame.grid(row=0, column=0, sticky="ew")
        conditions_frame.columnconfigure(1, weight=1)
        conditions_frame.columnconfigure(3, weight=1)
        self._add_entry(
            conditions_frame,
            0,
            "Su sicakligi (degC)",
            self.air_vars["temperature_c"],
            field_key="air.temperature_c",
        )
        self._add_entry(
            conditions_frame,
            0,
            "Su basinci (bar)",
            self.air_vars["pressure_bar"],
            field_key="air.pressure_bar",
            column=2,
        )
        self._add_entry(
            conditions_frame,
            1,
            "A (10^-6 / bar)",
            self.air_vars["a_micro_per_bar"],
            field_key="air.a_micro_per_bar",
            readonly=True,
        )
        ttk.Label(
            conditions_frame,
            textvariable=self.coefficient_status_vars["air_a"],
            foreground="#8A6D3B",
        ).grid(row=1, column=2, columnspan=2, sticky="w", pady=6)
        ttk.Label(conditions_frame, text="A secenegi").grid(row=2, column=0, sticky="w", pady=6)
        air_a_mode_combo = ttk.Combobox(
            conditions_frame,
            textvariable=self.air_a_mode_var,
            state="readonly",
            values=(AUTO_A_MODE, REFERENCE_A_MODE, MANUAL_A_MODE),
        )
        air_a_mode_combo.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=6)
        air_a_mode_combo.bind("<<ComboboxSelected>>", self._on_air_a_mode_changed)
        ttk.Label(conditions_frame, text="A referans noktasi").grid(row=2, column=2, sticky="w", pady=6)
        self.air_a_reference_combo = ttk.Combobox(
            conditions_frame,
            textvariable=self.air_a_reference_var,
            state="disabled",
            values=get_reference_option_labels(),
        )
        self.air_a_reference_combo.grid(row=2, column=3, sticky="ew", padx=(0, 12), pady=6)
        self.air_a_reference_combo.bind("<<ComboboxSelected>>", self._on_air_a_reference_changed)
        ttk.Label(
            conditions_frame,
            text="Sicaklik veya basinc degisirse A yeniden hesaplanmalidir.",
            wraplength=860,
            justify="left",
            foreground="#35506B",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

        measurements_frame = ttk.LabelFrame(frame, text="2. Olculen Degerler", padding=12)
        measurements_frame.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        measurements_frame.columnconfigure(1, weight=1)
        measurements_frame.columnconfigure(3, weight=1)
        self._add_entry(
            measurements_frame,
            0,
            "Basinc artisi P (bar, sartname: 1.0)",
            self.air_vars["pressure_rise_bar"],
            field_key="air.pressure_rise_bar",
        )
        self._add_entry(
            measurements_frame,
            0,
            "Fiili ilave su Vpa (m3)",
            self.air_vars["actual_added_water_m3"],
            field_key="air.actual_added_water_m3",
            column=2,
        )
        ttk.Label(measurements_frame, text="K faktor preset").grid(row=1, column=0, sticky="w", pady=6)
        k_preset = ttk.Combobox(
            measurements_frame,
            textvariable=self.k_preset_var,
            state="readonly",
            values=("Kaynakli boru - 1.02", "Dikissiz boru - 1.00", "Ozel"),
        )
        k_preset.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=6)
        k_preset.bind("<<ComboboxSelected>>", self._on_k_preset_changed)
        self._add_entry(
            measurements_frame,
            1,
            "K faktor",
            self.air_vars["k_factor"],
            field_key="air.k_factor",
            column=2,
        )

        actions_frame = ttk.Frame(frame)
        actions_frame.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.air_a_calculate_button = ttk.Button(actions_frame, text="A Hesapla", command=self._calculate_air_a)
        self.air_a_calculate_button.pack(side="left")
        ttk.Button(actions_frame, text="Hava Testini Degerlendir", command=self._run_air_test).pack(
            side="left", padx=(8, 0)
        )

        ttk.Label(
            frame,
            text=(
                "Operasyon sirasi: 1) sicaklik ve basinci girin, 2) A'yi dogrulayin, "
                "3) sartname geregi 1.0 bar P, K ve Vpa degerleriyle testi degerlendirin."
            ),
            wraplength=860,
            justify="left",
        ).grid(row=3, column=0, sticky="nw", pady=(12, 0))
        ttk.Label(
            frame,
            textvariable=self.section_feedback_vars["air"],
            foreground="#A4262C",
            wraplength=860,
            justify="left",
        ).grid(row=4, column=0, sticky="w", pady=(10, 0))

    def _build_pressure_tab(self, frame: ttk.Frame) -> None:
        frame.rowconfigure(4, weight=1)

        conditions_frame = ttk.LabelFrame(frame, text="1. Test Kosullari", padding=12)
        conditions_frame.grid(row=0, column=0, sticky="ew")
        conditions_frame.columnconfigure(1, weight=1)
        conditions_frame.columnconfigure(3, weight=1)
        self._add_entry(
            conditions_frame,
            0,
            "Su sicakligi (degC)",
            self.pressure_vars["temperature_c"],
            field_key="pressure.temperature_c",
        )
        self._add_entry(
            conditions_frame,
            0,
            "Su basinci (bar)",
            self.pressure_vars["pressure_bar"],
            field_key="pressure.pressure_bar",
            column=2,
        )
        self._add_entry(
            conditions_frame,
            1,
            "A (10^-6 / bar)",
            self.pressure_vars["a_micro_per_bar"],
            field_key="pressure.a_micro_per_bar",
        )
        self._add_entry(
            conditions_frame,
            1,
            "B (10^-6 / degC)",
            self.pressure_vars["b_micro_per_c"],
            field_key="pressure.b_micro_per_c",
            column=2,
        )
        ttk.Label(
            conditions_frame,
            textvariable=self.coefficient_status_vars["pressure_a"],
            foreground="#8A6D3B",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(
            conditions_frame,
            textvariable=self.coefficient_status_vars["pressure_b"],
            foreground="#8A6D3B",
        ).grid(row=2, column=2, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(conditions_frame, text="A secenegi").grid(row=3, column=0, sticky="w", pady=6)
        pressure_a_mode_combo = ttk.Combobox(
            conditions_frame,
            textvariable=self.pressure_a_mode_var,
            state="readonly",
            values=(AUTO_A_MODE, REFERENCE_A_MODE, MANUAL_A_MODE),
        )
        pressure_a_mode_combo.grid(row=3, column=1, sticky="ew", padx=(0, 12), pady=6)
        pressure_a_mode_combo.bind("<<ComboboxSelected>>", self._on_pressure_a_mode_changed)
        ttk.Label(conditions_frame, text="B secenegi").grid(row=3, column=2, sticky="w", pady=6)
        pressure_b_mode_combo = ttk.Combobox(
            conditions_frame,
            textvariable=self.pressure_b_mode_var,
            state="readonly",
            values=(AUTO_B_MODE, REFERENCE_B_MODE, MANUAL_B_MODE),
        )
        pressure_b_mode_combo.grid(row=3, column=3, sticky="ew", padx=(0, 12), pady=6)
        pressure_b_mode_combo.bind("<<ComboboxSelected>>", self._on_pressure_b_mode_changed)
        ttk.Label(conditions_frame, text="A referans noktasi").grid(row=4, column=0, sticky="w", pady=6)
        self.pressure_a_reference_combo = ttk.Combobox(
            conditions_frame,
            textvariable=self.pressure_a_reference_var,
            state="disabled",
            values=get_reference_option_labels(),
        )
        self.pressure_a_reference_combo.grid(row=4, column=1, sticky="ew", padx=(0, 12), pady=6)
        self.pressure_a_reference_combo.bind("<<ComboboxSelected>>", self._on_pressure_a_reference_changed)
        ttk.Label(conditions_frame, text="B referans noktasi").grid(row=4, column=2, sticky="w", pady=6)
        self.pressure_b_reference_combo = ttk.Combobox(
            conditions_frame,
            textvariable=self.pressure_b_reference_var,
            state="disabled",
            values=get_reference_option_labels(),
        )
        self.pressure_b_reference_combo.grid(row=4, column=3, sticky="ew", padx=(0, 12), pady=6)
        self.pressure_b_reference_combo.bind("<<ComboboxSelected>>", self._on_pressure_b_reference_changed)

        measurements_frame = ttk.LabelFrame(frame, text="2. Olculen Degerler", padding=12)
        measurements_frame.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        measurements_frame.columnconfigure(1, weight=1)
        measurements_frame.columnconfigure(3, weight=1)
        self._add_entry(
            measurements_frame,
            0,
            "Su sicaklik degisimi dT = Tilk - Tson (degC)",
            self.pressure_vars["delta_t_c"],
            field_key="pressure.delta_t_c",
        )
        self._add_entry(
            measurements_frame,
            0,
            "Fiili basinc degisimi Pa = Pilk - Pson (bar)",
            self.pressure_vars["actual_pressure_change_bar"],
            field_key="pressure.actual_pressure_change_bar",
            column=2,
        )

        helper_frame = ttk.LabelFrame(frame, text="3. B Yardimcisi", padding=12)
        helper_frame.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        helper_frame.columnconfigure(1, weight=1)
        helper_frame.columnconfigure(3, weight=1)
        ttk.Label(
            helper_frame,
            text=(
                "B secenegi ustte belirlenir. Otomatik modda su beta ve celik alpha ile hesaplanir; "
                "manuel modda ise B degeri dogrudan girilir."
            ),
            wraplength=860,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        ttk.Label(helper_frame, text="Celik preset").grid(row=1, column=0, sticky="w", pady=6)
        self.steel_preset_combo = ttk.Combobox(
            helper_frame,
            textvariable=self.steel_preset_var,
            state="readonly",
            values=(
                "Karbon celik - 12.0",
                "Dusuk alasimli celik - 12.5",
                "Paslanmaz celik - 16.0",
                "Ozel",
            ),
        )
        self.steel_preset_combo.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=6)
        self.steel_preset_combo.bind("<<ComboboxSelected>>", self._on_steel_preset_changed)

        self._add_entry(
            helper_frame,
            1,
            "Celik alpha (10^-6 / degC)",
            self.b_helper_vars["steel_alpha_micro_per_c"],
            field_key="helper.steel_alpha_micro_per_c",
            column=2,
        )
        self._add_entry(
            helper_frame,
            1,
            "Su beta (10^-6 / degC)",
            self.b_helper_vars["water_beta_micro_per_c"],
            field_key="helper.water_beta_micro_per_c",
            readonly=True,
        )
        self.pressure_a_calculate_button = ttk.Button(helper_frame, text="A Hesapla", command=self._calculate_pressure_a)
        self.pressure_a_calculate_button.grid(
            row=2, column=0, sticky="w", pady=6
        )
        self.b_helper_calculate_button = ttk.Button(helper_frame, text="B Hesapla", command=self._calculate_b_helper)
        self.b_helper_calculate_button.grid(
            row=2, column=1, sticky="w", pady=6
        )
        ttk.Button(
            helper_frame,
            text="Basinc Testini Degerlendir",
            command=self._run_pressure_test,
        ).grid(row=2, column=2, sticky="w", pady=6)
        ttk.Label(
            helper_frame,
            text=(
                "B degeri manuel girilebilir veya helper ile hesaplanabilir. Helper kullanilirsa "
                "sicaklik ya da basinc degisince B guncellenmeli durumuna duser."
            ),
            wraplength=860,
            justify="left",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Label(
            frame,
            text=(
                "Operasyon sirasi: 1) sicaklik ve basinci girin, 2) A ve gerekiyorsa B'yi hazirlayin, "
                "3) dT = Tilk - Tson ve Pa = Pilk - Pson degerleriyle testi degerlendirin."
            ),
            wraplength=860,
            justify="left",
        ).grid(row=3, column=0, sticky="nw", pady=(12, 0))
        ttk.Label(
            frame,
            textvariable=self.section_feedback_vars["pressure"],
            foreground="#A4262C",
            wraplength=860,
            justify="left",
        ).grid(row=4, column=0, sticky="w", pady=(10, 0))

    def _add_entry(
        self,
        frame: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        column: int = 0,
        field_key: str | None = None,
        readonly: bool = False,
    ) -> None:
        section = "general"
        required = not readonly
        if field_key is not None:
            prefix = field_key.split(".", 1)[0]
            section = "pressure" if prefix == "helper" else prefix
            if field_key in {"air.a_micro_per_bar", "pressure.a_micro_per_bar", "helper.water_beta_micro_per_c"}:
                required = False
        label_text = f"{label} *" if required else label
        ttk.Label(frame, text=label_text).grid(row=row, column=column, sticky="w", pady=6)
        state = "readonly" if readonly else "normal"
        entry_container = ttk.Frame(frame)
        entry_container.grid(
            row=row,
            column=column + 1,
            sticky="ew",
            padx=(0, 12),
            pady=6,
        )
        entry_container.columnconfigure(0, weight=1)
        entry = ttk.Entry(entry_container, textvariable=variable, state=state)
        entry.grid(row=0, column=0, sticky="ew")
        if field_key is not None:
            self.entry_widgets[field_key] = entry
            self.field_meta[field_key] = {
                "label": label,
                "section": section,
                "required": required,
                "readonly": readonly,
            }
            message_var = tk.StringVar()
            self.field_message_vars[field_key] = message_var
            ttk.Label(
                entry_container,
                textvariable=message_var,
                foreground="#6B7280",
                wraplength=280,
                justify="left",
            ).grid(row=1, column=0, sticky="w", pady=(3, 0))

    def _register_traces(self) -> None:
        for variable in self.geometry_vars.values():
            variable.trace_add("write", lambda *_: self._refresh_geometry_summary())
        for field_key, variable in (
            [(f"geometry.{key}", variable) for key, variable in self.geometry_vars.items()]
            + [(f"air.{key}", variable) for key, variable in self.air_vars.items()]
            + [(f"pressure.{key}", variable) for key, variable in self.pressure_vars.items()]
            + [(f"helper.{key}", variable) for key, variable in self.b_helper_vars.items()]
        ):
            if field_key in self.field_meta:
                variable.trace_add("write", lambda *_args, key=field_key, var=variable: self._on_live_field_change(key, var))
        self.air_vars["temperature_c"].trace_add("write", lambda *_: self._mark_dependencies_changed(("air_a",)))
        self.air_vars["pressure_bar"].trace_add("write", lambda *_: self._mark_dependencies_changed(("air_a",)))
        self.pressure_vars["temperature_c"].trace_add(
            "write", lambda *_: self._mark_dependencies_changed(("pressure_a", "pressure_b"))
        )
        self.pressure_vars["pressure_bar"].trace_add(
            "write", lambda *_: self._mark_dependencies_changed(("pressure_a", "pressure_b"))
        )
        self.b_helper_vars["steel_alpha_micro_per_c"].trace_add(
            "write", lambda *_: self._mark_dependencies_changed(("pressure_b",))
        )
        self.air_vars["a_micro_per_bar"].trace_add(
            "write", lambda *_: self._on_coefficient_field_changed("air_a", self.air_vars["a_micro_per_bar"])
        )
        self.pressure_vars["a_micro_per_bar"].trace_add(
            "write", lambda *_: self._on_coefficient_field_changed("pressure_a", self.pressure_vars["a_micro_per_bar"])
        )
        self.pressure_vars["b_micro_per_c"].trace_add(
            "write", lambda *_: self._on_coefficient_field_changed("pressure_b", self.pressure_vars["b_micro_per_c"])
        )

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-Return>", lambda *_: self._run_selected_test())
        self.root.bind("<F5>", lambda *_: self._recalculate_active_coefficients())

    def _check_for_updates_on_startup(self) -> None:
        self._start_update_check(user_requested=False)

    def _check_for_updates_manually(self) -> None:
        self._start_update_check(user_requested=True)

    def _start_update_check(self, user_requested: bool) -> None:
        if self.update_check_in_progress:
            if user_requested:
                messagebox.showinfo("Bilgi", "Guncelleme kontrolu zaten devam ediyor.")
            return
        self.update_check_in_progress = True
        self.update_status_var.set("Guncelleme kontrol ediliyor...")
        self.update_detail_var.set("GitHub release listesi sorgulaniyor.")
        worker = threading.Thread(
            target=self._perform_update_check,
            args=(user_requested,),
            daemon=True,
        )
        worker.start()

    def _perform_update_check(self, user_requested: bool) -> None:
        try:
            update_info = fetch_latest_update_info()
        except UpdateError as exc:
            self.root.after(0, lambda: self._handle_update_check_error(str(exc), user_requested))
            return
        self.root.after(0, lambda: self._handle_update_check_result(update_info, user_requested))

    def _handle_update_check_error(self, message: str, user_requested: bool) -> None:
        self.update_check_in_progress = False
        self.update_status_var.set("Guncelleme kontrolu tamamlanamadi.")
        self.update_detail_var.set(message)
        if user_requested:
            self._set_banner(message, "warning")
            messagebox.showwarning("Guncelleme Kontrolu", message)

    def _handle_update_check_result(self, update_info: UpdateInfo, user_requested: bool) -> None:
        self.update_check_in_progress = False
        self.latest_update_info = update_info
        if update_info.update_available:
            asset_name = update_info.asset.name if update_info.asset is not None else "uygun zip asset bulunamadi"
            self.update_status_var.set(
                f"Yeni surum bulundu: {update_info.latest_version} ({update_info.tag_name})"
            )
            self.update_detail_var.set(
                f"Yayin tarihi: {update_info.published_at or '-'} | Paket: {asset_name}"
            )
            self._set_banner(
                f"Yeni surum bulundu: {update_info.latest_version}. Isterseniz uygulama icinden guncellemeyi baslatabilirsiniz.",
                "warning",
            )
            if not user_requested:
                if messagebox.askyesno(
                    "Guncelleme Bulundu",
                    (
                        f"Yeni surum bulundu: {update_info.latest_version}\n\n"
                        "Simdi indirip uygulamak ister misiniz?"
                    ),
                ):
                    self._apply_available_update()
            return

        self.update_status_var.set(f"Guncel surum kullaniyorsunuz: {APP_VERSION}")
        self.update_detail_var.set("Bu uygulama icin daha yeni bir release bulunmadi.")
        if user_requested:
            self._set_banner("En guncel surumu kullaniyorsunuz.", "success")
            messagebox.showinfo("Guncelleme Kontrolu", "En guncel surumu kullaniyorsunuz.")

    def _apply_available_update(self) -> None:
        if self.update_install_in_progress:
            messagebox.showinfo("Bilgi", "Guncelleme kurulumu zaten devam ediyor.")
            return
        if self.latest_update_info is None:
            self._check_for_updates_manually()
            return
        if not self.latest_update_info.update_available:
            messagebox.showinfo("Bilgi", "Kurulacak yeni bir surum bulunmuyor.")
            return
        self.update_install_in_progress = True
        self.update_status_var.set(f"Guncelleme indiriliyor: {self.latest_update_info.latest_version}")
        self.update_detail_var.set("Release paketi indiriliyor ve kurulum hazirlaniyor.")
        worker = threading.Thread(target=self._perform_update_install, daemon=True)
        worker.start()

    def _perform_update_install(self) -> None:
        if self.latest_update_info is None:
            self.root.after(0, lambda: self._handle_update_install_error("Guncel release bilgisi bulunamadi."))
            return
        try:
            install_mode = install_update(self.latest_update_info)
        except UpdateError as exc:
            self.root.after(0, lambda: self._handle_update_install_error(str(exc)))
            return
        self.root.after(0, lambda: self._handle_update_install_result(install_mode))

    def _handle_update_install_error(self, message: str) -> None:
        self.update_install_in_progress = False
        self.update_status_var.set("Guncelleme kurulumu basarisiz oldu.")
        self.update_detail_var.set(message)
        self._set_banner(message, "error")
        messagebox.showerror("Guncelleme", message)

    def _handle_update_install_result(self, install_mode: str) -> None:
        self.update_install_in_progress = False
        if install_mode == "browser":
            self.update_status_var.set("Tarayici uzerinden guncelleme yonlendirmesi acildi.")
            self.update_detail_var.set(
                "Bu ortam kendini otomatik guncelleyemiyor. Release sayfasi tarayicida acildi."
            )
            self._set_banner("Release sayfasi acildi. Guncel paketi indirip mevcut klasorun yerine koyabilirsiniz.", "warning")
            messagebox.showinfo(
                "Guncelleme",
                "Bu calisma ortami kendini otomatik guncelleyemiyor. Release sayfasi acildi.",
            )
            return
        if install_mode == "up_to_date":
            self.update_status_var.set(f"Guncel surum kullaniyorsunuz: {APP_VERSION}")
            self.update_detail_var.set("Kurulacak yeni bir surum bulunmuyor.")
            messagebox.showinfo("Guncelleme", "Kurulacak yeni bir surum bulunmuyor.")
            return
        self.update_status_var.set("Guncelleme baslatildi. Uygulama yeniden acilacak.")
        self.update_detail_var.set("Indirme tamamlandi. Uygulama kapanirken yeni surum uygulanacak.")
        self._set_banner("Guncelleme indirildi. Uygulama kapatilip yeni surumle yeniden baslatilacak.", "success")
        messagebox.showinfo(
            "Guncelleme",
            "Indirme tamamlandi. Uygulama kapanacak ve guncelleme uygulanacaktir.",
        )
        self.root.after(250, self.root.destroy)

    def _open_release_page(self) -> None:
        target_url = RELEASES_PAGE_URL
        if self.latest_update_info is not None and self.latest_update_info.html_url:
            target_url = self.latest_update_info.html_url
        open_release_page(target_url)

    def _mark_dependencies_changed(self, keys: tuple[str, ...]) -> None:
        for key in keys:
            if self.coefficient_states[key] in {"computed", "reference"}:
                self.coefficient_states[key] = "stale"
        self._refresh_coefficient_statuses()
        self._update_workflow_hint()

    def _safe_float(self, value: str) -> float | None:
        normalized = value.strip().replace(",", ".")
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None

    def _set_field_message(self, field_key: str, message: str, level: str = "info") -> None:
        var = self.field_message_vars.get(field_key)
        if var is None:
            return
        prefixes = {
            "info": "",
            "success": "Hazir: ",
            "warning": "Uyari: ",
            "error": "Hata: ",
        }
        var.set(f"{prefixes.get(level, '')}{message}" if message else "")

    def _clear_field_message(self, field_key: str) -> None:
        var = self.field_message_vars.get(field_key)
        if var is not None:
            var.set("")

    def _auto_field_hint(self, field_key: str) -> str:
        if field_key == "air.a_micro_per_bar":
            if self._air_a_is_auto():
                return "Otomatik modda A Hesapla ile veya test sirasinda doldurulur."
            if self._air_a_is_reference():
                return "Referans modda dogrulanmis bir nokta secerek A degerini yukleyin."
            return "Manuel modda tablo/prosedurden A degerini girin."
        if field_key == "pressure.a_micro_per_bar":
            if self._pressure_a_is_auto():
                return "Otomatik modda A Hesapla ile veya test sirasinda doldurulur."
            if self._pressure_a_is_reference():
                return "Referans modda dogrulanmis bir nokta secerek A degerini yukleyin."
            return "Manuel modda tablo/prosedurden A degerini girin."
        if field_key == "pressure.b_micro_per_c":
            if self.use_b_helper_var.get():
                if self._pressure_b_is_reference():
                    return "Referans modda su beta referansi ve celik alpha ile B olusturulur."
                return "Otomatik modda B, su beta ve celik alpha ile hesaplanir."
            return "Manuel modda tablo/prosedurden B degerini girin."
        if field_key == "air.pressure_rise_bar":
            return "Sartnameye gore bu alan 1.0 bar olmalidir."
        if field_key == "pressure.delta_t_c":
            return "dT degeri Tilk - Tson olarak girilir."
        if field_key == "pressure.actual_pressure_change_bar":
            return "Pa degeri Pilk - Pson olarak girilir."
        if field_key == "helper.steel_alpha_micro_per_c" and self.use_b_helper_var.get():
            if self._pressure_b_is_reference():
                return "Referans B icin celik alpha secin; secili beta ile birlikte B olusturulur."
            return "Otomatik B icin celik alpha preset secin veya ozel deger girin."
        if field_key == "helper.water_beta_micro_per_c" and self.use_b_helper_var.get():
            if self._pressure_b_is_reference():
                return "Secilen referans noktanin su beta degeri burada gosterilir."
            return "B hesaplandiginda su beta burada gosterilir."
        return ""

    def _update_live_notice(self) -> None:
        invalid_count = 0
        warning_count = 0
        stale_coefficients = [
            key
            for key, value in self.coefficient_states.items()
            if value == "stale" and key in self._relevant_coefficient_keys()
        ]
        for field_key in self._relevant_field_keys():
            meta = self.field_meta[field_key]
            if meta.get("readonly"):
                continue
            value = ""
            prefix, name = field_key.split(".", 1)
            if prefix == "geometry":
                value = self.geometry_vars[name].get()
            elif prefix == "air":
                value = self.air_vars[name].get()
            elif prefix == "pressure":
                value = self.pressure_vars[name].get()
            elif prefix == "helper":
                value = self.b_helper_vars[name].get()
            normalized = value.strip().replace(",", ".")
            if normalized and self._safe_float(value) is None:
                invalid_count += 1
            elif field_key in self.touched_fields and meta.get("required") and not normalized:
                warning_count += 1
        if invalid_count:
            self.live_notice_var.set(
                f"Canli kontrol: {invalid_count} alan sayisal olarak gecersiz. Devam etmeden duzeltin."
            )
        elif stale_coefficients:
            self.live_notice_var.set(
                f"Canli kontrol: {len(stale_coefficients)} katsayi guncellenmeli. Yeniden hesaplama onerilir."
            )
        elif warning_count:
            self.live_notice_var.set(
                f"Canli kontrol: {warning_count} zorunlu alan henuz tamamlanmadi."
            )
        else:
            self.live_notice_var.set("Canli kontrol: aktif gorunen girdiler tutarli gorunuyor.")

    def _on_live_field_change(self, field_key: str, variable: tk.StringVar) -> None:
        self.touched_fields.add(field_key)
        meta = self.field_meta.get(field_key)
        if meta is None:
            return
        normalized = variable.get().strip().replace(",", ".")
        if not normalized:
            hint = self._auto_field_hint(field_key)
            if hint:
                self._set_field_message(field_key, hint, "info")
            elif meta.get("required"):
                self._set_field_message(field_key, "Bu alan gerekli.", "warning")
            else:
                self._clear_field_message(field_key)
            self._update_live_notice()
            return
        if self._safe_float(variable.get()) is None:
            self._set_field_message(field_key, "Gecerli bir sayi girin.", "error")
            self._update_live_notice()
            return
        if field_key == "pressure.b_micro_per_c" and self.use_b_helper_var.get():
            self._set_field_message(field_key, "Helper modu bu degeri yonetiyor.", "info")
            self._update_live_notice()
            return
        self._clear_field_message(field_key)
        self._update_live_notice()

    def _refresh_geometry_summary(self) -> None:
        if self.geometry_segments:
            try:
                geometry = PipeGeometry(
                    sections=tuple(segment_info["pipe"] for segment_info in self.geometry_segments)  # type: ignore[arg-type]
                )
            except ValidationError as exc:
                self.geometry_summary_var.set(f"Segment ozeti hazir degil: {exc}")
                return
            self.geometry_summary_var.set(
                "Segmentli geometri aktif. Esdeger ic yaricap = "
                f"{geometry.internal_radius_mm:.3f} mm, toplam ic hacim Vt = {geometry.internal_volume_m3:.6f} m3, "
                f"toplam uzunluk = {geometry.total_length_m:.3f} m"
            )
            return
        outside = self._safe_float(self.geometry_vars["outside_diameter_mm"].get())
        wall = self._safe_float(self.geometry_vars["wall_thickness_mm"].get())
        length = self._safe_float(self.geometry_vars["length_m"].get())
        if outside is None or wall is None or length is None:
            self.geometry_summary_var.set(
                "Geometri girildiginde ic cap, ic yaricap ve hacim ozeti burada gosterilir."
            )
            return
        try:
            pipe = PipeSection(
                outside_diameter_mm=outside,
                wall_thickness_mm=wall,
                length_m=length,
            )
        except ValidationError as exc:
            self.geometry_summary_var.set(f"Geometri ozeti hazir degil: {exc}")
            return
        internal_diameter_mm = pipe.internal_radius_mm * 2
        self.geometry_summary_var.set(
            "Ic cap = "
            f"{internal_diameter_mm:.3f} mm, ic yaricap = {pipe.internal_radius_mm:.3f} mm, "
            f"ic hacim Vt = {pipe.internal_volume_m3:.6f} m3"
        )

    def _on_coefficient_field_changed(self, key: str, variable: tk.StringVar) -> None:
        if key in self._programmatic_coefficient_updates:
            return
        self.coefficient_states[key] = "manual" if variable.get().strip() else "empty"
        self._refresh_coefficient_statuses()
        self._update_workflow_hint()

    def _refresh_coefficient_statuses(self) -> None:
        self.coefficient_status_vars["air_a"].set(self._coefficient_status_text("air_a"))
        self.coefficient_status_vars["pressure_a"].set(self._coefficient_status_text("pressure_a"))
        self.coefficient_status_vars["pressure_b"].set(self._coefficient_status_text("pressure_b"))
        self._sync_coefficient_field_messages()
        self._update_workflow_hint()

    def _coefficient_status_text(self, key: str) -> str:
        state = self.coefficient_states[key]
        if state == "computed":
            return "Hazir: otomatik hesap"
        if state == "reference":
            return "Hazir: referans nokta"
        if state == "stale":
            return "Guncellenmeli: secenek veya kosullar degisti"
        if state == "manual":
            return "Hazir: manuel giris"
        return "Bekleniyor"

    def _sync_coefficient_field_messages(self) -> None:
        mapping = {
            "air_a": "air.a_micro_per_bar",
            "pressure_a": "pressure.a_micro_per_bar",
            "pressure_b": "pressure.b_micro_per_c",
        }
        for coefficient_key, field_key in mapping.items():
            state = self.coefficient_states[coefficient_key]
            existing_message = self.field_message_vars.get(field_key)
            if state == "stale":
                self._set_field_message(field_key, "Kosullar degisti, yeniden hesaplayin.", "warning")
            elif state == "computed":
                self._set_field_message(field_key, "Hesap guncel.", "success")
            elif state == "reference":
                self._set_field_message(field_key, "Referans noktadan yuklendi.", "success")
            elif state == "manual":
                self._set_field_message(field_key, "Manuel giris aktif.", "info")
            elif existing_message is not None and not existing_message.get():
                hint = self._auto_field_hint(field_key)
                if hint:
                    self._set_field_message(field_key, hint, "info")

    def _set_feedback(self, section: str, message: str) -> None:
        self.section_feedback_vars[section].set(message)
        self._update_live_notice()

    def _clear_feedback(self, section: str) -> None:
        self.section_feedback_vars[section].set("")
        for field_key, meta in self.field_meta.items():
            if meta.get("section") == section:
                if field_key in {"air.a_micro_per_bar", "pressure.a_micro_per_bar", "pressure.b_micro_per_c"}:
                    continue
                hint = self._auto_field_hint(field_key)
                if hint:
                    self._set_field_message(field_key, hint, "info")
                else:
                    self._clear_field_message(field_key)
        self._update_live_notice()

    def _clear_all_feedback(self) -> None:
        for key in self.section_feedback_vars:
            self.section_feedback_vars[key].set("")
        self._update_live_notice()

    def _set_banner(self, message: str, level: str = "info") -> None:
        colors = {
            "info": ("#EEF4FF", "#16365D"),
            "success": ("#EAF7EA", "#1D5F2F"),
            "warning": ("#FFF6E5", "#8A5B00"),
            "error": ("#FDEAEA", "#8B1E1E"),
        }
        bg, fg = colors.get(level, colors["info"])
        self.banner_var.set(message)
        self.banner_label.configure(bg=bg, fg=fg)

    def _active_tab_key(self) -> str:
        if not hasattr(self, "notebook"):
            return "air"
        current_text = self.notebook.tab(self.notebook.select(), "text")
        return "pressure" if "Basinc" in current_text else "air"

    def _relevant_field_keys(self) -> set[str]:
        active_tab = self._active_tab_key()
        relevant_fields: set[str] = set()
        for field_key, meta in self.field_meta.items():
            section = meta.get("section")
            if self.geometry_segments and section == "geometry":
                continue
            if section not in {"geometry", active_tab}:
                continue
            if field_key.startswith("helper.") and not self.use_b_helper_var.get():
                continue
            relevant_fields.add(field_key)
        return relevant_fields

    def _relevant_coefficient_keys(self) -> tuple[str, ...]:
        if self._active_tab_key() == "air":
            return ("air_a",)
        return ("pressure_a", "pressure_b")

    def _remove_touched_fields(self, section: str) -> None:
        for field_key, meta in self.field_meta.items():
            if meta.get("section") == section:
                self.touched_fields.discard(field_key)

    def _reset_decision_card(self) -> None:
        self._update_decision_card(
            DEFAULT_DECISION_TITLE,
            DEFAULT_DECISION_STATUS,
            DEFAULT_DECISION_SUMMARY,
        )

    def _default_k_factor(self) -> str:
        selected = self.k_preset_var.get()
        if "1.02" in selected:
            return f"{WELDED_PIPE_K:.2f}"
        if "1.00" in selected:
            return f"{SEAMLESS_PIPE_K:.2f}"
        return ""

    def _default_steel_alpha(self) -> str:
        selected = self.steel_preset_var.get()
        if "12.0" in selected:
            return "12.0"
        if "12.5" in selected:
            return "12.5"
        if "16.0" in selected:
            return "16.0"
        return ""

    def _format_var_value(self, variable: tk.StringVar) -> str:
        value = variable.get().strip()
        return value if value else "-"

    def _current_geometry_descriptor(self) -> tuple[str, str]:
        size_label = self.geometry_catalog_vars["size_option"].get().strip()
        schedule_label = self.geometry_catalog_vars["schedule_option"].get().strip()
        pipe_size = find_pipe_size(size_label)
        schedule = find_schedule(size_label, schedule_label)
        nps_label = "-"
        schedule_text = "Elle giris"
        if pipe_size is not None:
            nps_label = f"NPS {pipe_size['nps']} / DN {pipe_size['dn']}"
        if schedule is not None:
            schedule_text = schedule["label"]
        return nps_label, schedule_text

    def _on_pipe_size_selected(self, _: tk.Event | None = None) -> None:
        size_label = self.geometry_catalog_vars["size_option"].get().strip()
        schedule_options = get_schedule_options(size_label)
        self.pipe_schedule_combo.configure(values=schedule_options)
        if schedule_options:
            self.geometry_catalog_vars["schedule_option"].set(schedule_options[0])
        else:
            self.geometry_catalog_vars["schedule_option"].set("")

    def _apply_catalog_selection(self) -> None:
        size_label = self.geometry_catalog_vars["size_option"].get().strip()
        schedule_label = self.geometry_catalog_vars["schedule_option"].get().strip()
        pipe_size = find_pipe_size(size_label)
        schedule = find_schedule(size_label, schedule_label)
        if pipe_size is None or schedule is None:
            self._set_banner("Listeden doldurmak icin once NPS ve schedule secin.", "warning")
            return
        self.geometry_vars["outside_diameter_mm"].set(f"{pipe_size['outside_diameter_mm']:.2f}")
        self.geometry_vars["wall_thickness_mm"].set(f"{schedule['wall_thickness_mm']:.2f}")
        self._set_banner("ASME B36.10 listesinden geometri alanlari dolduruldu.", "success")

    def _build_manual_pipe_section(self, section: str) -> PipeSection:
        return PipeSection(
            outside_diameter_mm=self._read_float(
                self.geometry_vars["outside_diameter_mm"], "Dis cap", section, "geometry.outside_diameter_mm"
            ),
            wall_thickness_mm=self._read_float(
                self.geometry_vars["wall_thickness_mm"], "Et kalinligi", section, "geometry.wall_thickness_mm"
            ),
            length_m=self._read_float(
                self.geometry_vars["length_m"], "Hat uzunlugu", section, "geometry.length_m"
            ),
        )

    def _add_geometry_segment(self) -> None:
        self._clear_feedback("geometry")
        try:
            segment = self._build_manual_pipe_section("geometry")
        except ValidationError as exc:
            self._set_banner(str(exc), "error")
            return
        nps_label, schedule_text = self._current_geometry_descriptor()
        self.geometry_segments.append(
            {
                "pipe": segment,
                "nps_label": nps_label,
                "schedule_label": schedule_text,
            }
        )
        self._refresh_segment_tree()
        self._refresh_geometry_summary()
        self._set_banner("Geometri segmenti listeye eklendi.", "success")

    def _remove_selected_segment(self) -> None:
        selected_item = self.segment_tree.selection()
        if not selected_item:
            self._set_banner("Silmek icin once bir segment secin.", "warning")
            return
        index = int(selected_item[0]) - 1
        if 0 <= index < len(self.geometry_segments):
            self.geometry_segments.pop(index)
            self._refresh_segment_tree()
            self._refresh_geometry_summary()
            self._set_banner("Secili segment kaldirildi.", "info")

    def _clear_geometry_segments(self) -> None:
        self.geometry_segments.clear()
        self._refresh_segment_tree()
        self._refresh_geometry_summary()
        self._set_banner("Segment listesi temizlendi. Ustteki geometri alanlari tekrar aktif referans oldu.", "info")

    def _refresh_segment_tree(self) -> None:
        if not hasattr(self, "segment_tree"):
            return
        for item_id in self.segment_tree.get_children():
            self.segment_tree.delete(item_id)
        if not self.geometry_segments:
            self.segment_summary_var.set(
                "Segmentasyon kullanilmazsa ustteki geometri alanlari tek boru kesiti olarak kullanilir."
            )
            return
        total_length = 0.0
        total_volume = 0.0
        for index, segment_info in enumerate(self.geometry_segments, start=1):
            pipe = segment_info["pipe"]
            assert isinstance(pipe, PipeSection)
            total_length += pipe.length_m
            total_volume += pipe.internal_volume_m3
            self.segment_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    index,
                    segment_info["nps_label"],
                    segment_info["schedule_label"],
                    f"{pipe.outside_diameter_mm:.2f}",
                    f"{pipe.wall_thickness_mm:.2f}",
                    f"{pipe.length_m:.2f}",
                ),
            )
        self.segment_summary_var.set(
            f"Segment sayisi = {len(self.geometry_segments)}, toplam uzunluk = {total_length:.2f} m, toplam ic hacim = {total_volume:.6f} m3"
        )

    def _on_tab_changed(self, _: tk.Event | None = None) -> None:
        self._update_workflow_hint()
        self._update_live_notice()

    def _update_workflow_hint(self) -> None:
        active_tab = self._active_tab_key()
        if active_tab == "air":
            a_hint = (
                "A otomatik modda."
                if self._air_a_is_auto()
                else "A manuel modda; tablo/prosedur degeri beklenir."
            )
            self.workflow_hint_var.set(
                "Aktif test: Hava Icerik Testi. Onerilen akis: geometriyi kontrol edin, A'yi hesaplayin, "
                "sartnameye gore P=1.0 bar, K ve Vpa girip 'Aktif Testi Degerlendir' kullanin. "
                + a_hint
                + " Kisayol: Ctrl+Enter."
            )
        else:
            a_mode = (
                "A otomatik modda."
                if self._pressure_a_is_auto()
                else "A manuel modda; tablo/prosedur degeri beklenir."
            )
            b_mode = (
                "B otomatik modda; helper su beta ve celik alpha ile hesaplar."
                if self.use_b_helper_var.get()
                else "B manuel modda; degeri dogrudan ve dogrulanmis kaynaktan girmelisiniz."
            )
            self.workflow_hint_var.set(
                "Aktif test: Basinc Degisim Testi. Onerilen akis: geometriyi kontrol edin, A ve B'yi hazirlayin, "
                "dT = Tilk - Tson ve Pa = Pilk - Pson girip degerlendirin. "
                + a_mode
                + " "
                + b_mode
            )

    def _focus_field(self, field_key: str | None) -> None:
        if not field_key:
            return
        widget = self.entry_widgets.get(field_key)
        if widget is not None:
            widget.focus_set()
            widget.selection_range(0, "end")

    def _run_selected_test(self) -> None:
        if self._active_tab_key() == "air":
            self._run_air_test()
        else:
            self._run_pressure_test()

    def _recalculate_active_coefficients(self) -> None:
        if self._active_tab_key() == "air":
            self._calculate_air_a()
            return
        if self._calculate_pressure_a():
            if self.use_b_helper_var.get():
                self._calculate_b_helper()

    def _clear_active_form(self) -> None:
        if self._active_tab_key() == "air":
            self._clear_air_form()
        else:
            self._clear_pressure_form()

    def _read_float(
        self, variable: tk.StringVar, field_name: str, section: str, field_key: str | None = None
    ) -> float:
        normalized = variable.get().strip().replace(",", ".")
        if not normalized:
            message = f"{field_name} bos birakilamaz."
            self._set_feedback(section, message)
            if field_key is not None:
                self._set_field_message(field_key, "Bu alan zorunlu.", "error")
            self._focus_field(field_key)
            raise ValidationError(message)
        try:
            value = float(normalized)
        except ValueError as exc:
            message = f"{field_name} icin gecerli bir sayi girin."
            self._set_feedback(section, message)
            if field_key is not None:
                self._set_field_message(field_key, "Gecerli bir sayi girin.", "error")
            self._focus_field(field_key)
            raise ValidationError(message) from exc
        if field_key is not None and field_key not in {"air.a_micro_per_bar", "pressure.a_micro_per_bar", "pressure.b_micro_per_c"}:
            self._clear_field_message(field_key)
        return value

    def _air_a_is_auto(self) -> bool:
        return self.air_a_mode_var.get() == AUTO_A_MODE

    def _pressure_a_is_auto(self) -> bool:
        return self.pressure_a_mode_var.get() == AUTO_A_MODE

    def _pressure_b_is_auto(self) -> bool:
        return self.pressure_b_mode_var.get() == AUTO_B_MODE

    def _air_a_is_reference(self) -> bool:
        return self.air_a_mode_var.get() == REFERENCE_A_MODE

    def _pressure_a_is_reference(self) -> bool:
        return self.pressure_a_mode_var.get() == REFERENCE_A_MODE

    def _pressure_b_is_reference(self) -> bool:
        return self.pressure_b_mode_var.get() == REFERENCE_B_MODE

    def _apply_single_coefficient_mode(
        self,
        *,
        key: str,
        field_key: str,
        variable: tk.StringVar,
        mode: str,
        reference_combo: ttk.Combobox | None = None,
        auto_banner: str,
        reference_banner: str,
        manual_banner: str,
    ) -> None:
        entry = self.entry_widgets.get(field_key)
        if entry is not None:
            entry.configure(state="readonly" if mode != MANUAL_A_MODE else "normal")
        if reference_combo is not None:
            reference_combo.configure(state="readonly" if mode == REFERENCE_A_MODE else "disabled")
        if field_key == "air.a_micro_per_bar" and hasattr(self, "air_a_calculate_button"):
            self.air_a_calculate_button.configure(state="normal" if mode == AUTO_A_MODE else "disabled")
        if field_key == "pressure.a_micro_per_bar" and hasattr(self, "pressure_a_calculate_button"):
            self.pressure_a_calculate_button.configure(state="normal" if mode == AUTO_A_MODE else "disabled")
        meta = self.field_meta.get(field_key)
        if meta is not None:
            meta["required"] = mode == MANUAL_A_MODE
            meta["readonly"] = mode != MANUAL_A_MODE
        if mode == AUTO_A_MODE:
            self.coefficient_states[key] = "stale" if variable.get().strip() else "empty"
            self._set_banner(auto_banner, "info")
        elif mode == REFERENCE_A_MODE:
            self.coefficient_states[key] = "reference" if variable.get().strip() else "empty"
            self._set_banner(reference_banner, "info")
        else:
            self.coefficient_states[key] = "manual" if variable.get().strip() else "empty"
            self._set_banner(manual_banner, "warning")
        self._refresh_coefficient_statuses()
        self._update_live_notice()
        self._update_workflow_hint()

    def _on_air_a_mode_changed(self, _: tk.Event | None = None) -> None:
        self._apply_single_coefficient_mode(
            key="air_a",
            field_key="air.a_micro_per_bar",
            variable=self.air_vars["a_micro_per_bar"],
            mode=self.air_a_mode_var.get(),
            reference_combo=self.air_a_reference_combo,
            auto_banner="Hava A secenegi otomatik. A Hesapla butonu veya degerlendirme akisi bu alani doldurur.",
            reference_banner="Hava A secenegi referans modda. Dogrulanmis bir referans nokta secin.",
            manual_banner="Hava A secenegi manuel. Tablo/prosedur degerini dogrudan girebilirsiniz.",
        )

    def _on_pressure_a_mode_changed(self, _: tk.Event | None = None) -> None:
        self._apply_single_coefficient_mode(
            key="pressure_a",
            field_key="pressure.a_micro_per_bar",
            variable=self.pressure_vars["a_micro_per_bar"],
            mode=self.pressure_a_mode_var.get(),
            reference_combo=self.pressure_a_reference_combo,
            auto_banner="Basinc testi A secenegi otomatik. A Hesapla butonu veya degerlendirme akisi bu alani doldurur.",
            reference_banner="Basinc testi A secenegi referans modda. Dogrulanmis bir referans nokta secin.",
            manual_banner="Basinc testi A secenegi manuel. Tablo/prosedur degerini dogrudan girebilirsiniz.",
        )

    def _on_air_a_reference_changed(self, _: tk.Event | None = None) -> None:
        self._apply_air_a_reference(log_result=True)

    def _on_pressure_a_reference_changed(self, _: tk.Event | None = None) -> None:
        self._apply_pressure_a_reference(log_result=True)

    def _on_pressure_b_reference_changed(self, _: tk.Event | None = None) -> None:
        self._apply_pressure_b_reference(log_result=True)

    def _on_pressure_b_mode_changed(self, _: tk.Event | None = None) -> None:
        self._apply_b_helper_mode()

    def _apply_b_helper_mode(self) -> None:
        b_entry = self.entry_widgets.get("pressure.b_micro_per_c")
        steel_entry = self.entry_widgets.get("helper.steel_alpha_micro_per_c")
        water_entry = self.entry_widgets.get("helper.water_beta_micro_per_c")
        if b_entry is None:
            return
        auto_mode = self._pressure_b_is_auto()
        reference_mode = self._pressure_b_is_reference()
        self.use_b_helper_var.set(auto_mode or reference_mode)
        if hasattr(self, "pressure_b_reference_combo"):
            self.pressure_b_reference_combo.configure(state="readonly" if reference_mode else "disabled")
        if auto_mode or reference_mode:
            b_entry.configure(state="readonly")
            if steel_entry is not None:
                steel_entry.configure(state="normal")
            if water_entry is not None:
                water_entry.configure(state="readonly")
            if hasattr(self, "steel_preset_combo"):
                self.steel_preset_combo.configure(state="readonly")
            if hasattr(self, "b_helper_calculate_button"):
                self.b_helper_calculate_button.configure(state="normal" if auto_mode else "disabled")
            self.field_meta["pressure.b_micro_per_c"]["required"] = False
            self.field_meta["pressure.b_micro_per_c"]["readonly"] = True
            self.field_meta["helper.steel_alpha_micro_per_c"]["required"] = True
            self.field_meta["helper.steel_alpha_micro_per_c"]["readonly"] = False
            self.field_meta["helper.water_beta_micro_per_c"]["required"] = False
            self.field_meta["helper.water_beta_micro_per_c"]["readonly"] = True
            if auto_mode:
                self.coefficient_states["pressure_b"] = (
                    "stale" if self.pressure_vars["b_micro_per_c"].get().strip() else "empty"
                )
                self.helper_mode_summary_var.set(
                    "B secenegi otomatik. B alani kilitlidir; helper su beta ve celik alpha ile hesaplar."
                )
                self._set_banner(
                    "B secenegi otomatik. Degerlendirme sirasinda B helper kullanilir ve alan otomatik doldurulur.",
                    "info",
                )
            else:
                self.coefficient_states["pressure_b"] = (
                    "reference" if self.pressure_vars["b_micro_per_c"].get().strip() else "empty"
                )
                self.helper_mode_summary_var.set(
                    "B secenegi referans modda. B icin dogrulanmis bir referans nokta secilir, sonra secili celik alpha kullanilir."
                )
                self._set_banner(
                    "B secenegi referans modda. Bir referans nokta secerek su beta ve B degerini yukleyin.",
                    "info",
                )
        else:
            b_entry.configure(state="normal")
            if steel_entry is not None:
                steel_entry.configure(state="disabled")
            if water_entry is not None:
                water_entry.configure(state="disabled")
            if hasattr(self, "steel_preset_combo"):
                self.steel_preset_combo.configure(state="disabled")
            if hasattr(self, "b_helper_calculate_button"):
                self.b_helper_calculate_button.configure(state="disabled")
            self.field_meta["pressure.b_micro_per_c"]["required"] = True
            self.field_meta["pressure.b_micro_per_c"]["readonly"] = False
            self.field_meta["helper.steel_alpha_micro_per_c"]["required"] = False
            self.field_meta["helper.steel_alpha_micro_per_c"]["readonly"] = True
            self.field_meta["helper.water_beta_micro_per_c"]["required"] = False
            self.field_meta["helper.water_beta_micro_per_c"]["readonly"] = True
            self.b_helper_vars["water_beta_micro_per_c"].set("")
            self.coefficient_states["pressure_b"] = (
                "manual" if self.pressure_vars["b_micro_per_c"].get().strip() else "empty"
            )
            self.helper_mode_summary_var.set(
                "B secenegi manuel. B degerini tabloda veya prosedurde dogrulanan haliyle dogrudan girin."
            )
            self._set_banner(
                "B secenegi manuel. Basinc testi icin B degerini dogrudan girmeniz gerekir.",
                "warning",
            )
        self._refresh_coefficient_statuses()
        self._sync_coefficient_field_messages()
        self._update_live_notice()
        self._update_workflow_hint()

    def _apply_air_a_reference(self, log_result: bool = True) -> bool:
        point = find_reference_point(self.air_a_reference_var.get())
        if point is None:
            self._set_feedback("air", "Hava A icin bir referans nokta secin.")
            self._focus_field("air.a_micro_per_bar")
            return False
        self._set_coefficient_value("air_a", self.air_vars["a_micro_per_bar"], point.a_micro_per_bar, state="reference")
        if log_result:
            self._append_result(
                "Hava Icerik Testi - A referansi",
                (
                    f"A = {point.a_micro_per_bar:.6f} (10^-6 / bar) referans noktadan yuklendi.\n"
                    f"Referans: {point.label}\n"
                    f"Kaynak: {point.source_note}"
                ),
            )
        self._set_banner("Hava icerik testi icin A referans noktadan yuklendi.", "success")
        return True

    def _apply_pressure_a_reference(self, log_result: bool = True) -> bool:
        point = find_reference_point(self.pressure_a_reference_var.get())
        if point is None:
            self._set_feedback("pressure", "Basinc testi A icin bir referans nokta secin.")
            self._focus_field("pressure.a_micro_per_bar")
            return False
        self._set_coefficient_value("pressure_a", self.pressure_vars["a_micro_per_bar"], point.a_micro_per_bar, state="reference")
        if log_result:
            self._append_result(
                "Basinc Degisim Testi - A referansi",
                (
                    f"A = {point.a_micro_per_bar:.6f} (10^-6 / bar) referans noktadan yuklendi.\n"
                    f"Referans: {point.label}\n"
                    f"Kaynak: {point.source_note}"
                ),
            )
        self._set_banner("Basinc testi icin A referans noktadan yuklendi.", "success")
        return True

    def _apply_pressure_b_reference(self, log_result: bool = True) -> bool:
        point = find_reference_point(self.pressure_b_reference_var.get())
        if point is None:
            self._set_feedback("pressure", "Basinc testi B icin bir referans nokta secin.")
            self._focus_field("pressure.b_micro_per_c")
            return False
        try:
            steel_alpha = self._read_float(
                self.b_helper_vars["steel_alpha_micro_per_c"],
                "Celik alpha",
                "pressure",
                "helper.steel_alpha_micro_per_c",
            )
            b_value = calculate_b_coefficient(point.water_beta_micro_per_c, steel_alpha)
        except ValidationError as exc:
            self._set_banner(str(exc), "error")
            self._update_decision_card("Basinc Degisim Testi", "DOGRULANAMADI", str(exc))
            return False
        self.b_helper_vars["water_beta_micro_per_c"].set(f"{point.water_beta_micro_per_c:.6f}")
        self._set_coefficient_value("pressure_b", self.pressure_vars["b_micro_per_c"], b_value, state="reference")
        if log_result:
            self._append_result(
                "Basinc Degisim Testi - B referansi",
                (
                    f"Su beta referansi: {point.water_beta_micro_per_c:.6f} (10^-6 / degC)\n"
                    f"Celik alpha: {steel_alpha:.6f} (10^-6 / degC)\n"
                    f"Hesaplanan B: {b_value:.6f} (10^-6 / degC)\n"
                    f"Referans: {point.label}\n"
                    f"Kaynak: {point.source_note}"
                ),
            )
        self._set_banner("Basinc testi icin B referans noktadan yuklendi.", "success")
        return True

    def _set_coefficient_value(
        self,
        key: str,
        variable: tk.StringVar,
        value: float,
        *,
        state: str = "computed",
    ) -> None:
        self._programmatic_coefficient_updates.add(key)
        try:
            variable.set(f"{value:.6f}")
        finally:
            self._programmatic_coefficient_updates.discard(key)
        self.coefficient_states[key] = state
        self._refresh_coefficient_statuses()

    def _update_decision_card(self, title: str, status: str, summary: str) -> None:
        self.decision_title_var.set(title)
        self.decision_status_var.set(status)
        self.decision_summary_var.set(summary)
        if status == "BASARILI":
            self.decision_status_label.configure(bg="#E6F4EA", fg="#1E6F43")
        elif status == "BASARISIZ":
            self.decision_status_label.configure(bg="#FDE7E9", fg="#A4262C")
        else:
            self.decision_status_label.configure(bg="#EEF2FF", fg="#243B73")

    def _on_k_preset_changed(self, _: tk.Event) -> None:
        self.air_vars["k_factor"].set(self._default_k_factor())

    def _on_steel_preset_changed(self, _: tk.Event) -> None:
        self.b_helper_vars["steel_alpha_micro_per_c"].set(self._default_steel_alpha())

    def _build_pipe_section(self, section: str) -> PipeSection | PipeGeometry:
        try:
            if self.geometry_segments:
                return PipeGeometry(
                    sections=tuple(segment_info["pipe"] for segment_info in self.geometry_segments)  # type: ignore[arg-type]
                )
            return self._build_manual_pipe_section(section)
        except ValidationError as exc:
            self._set_feedback("geometry", str(exc))
            raise

    def _calculate_air_a(self, log_result: bool = True) -> bool:
        self._clear_feedback("air")
        try:
            a_value = calculate_water_compressibility_a(
                temp_c=self._read_float(
                    self.air_vars["temperature_c"], "Su sicakligi", "air", "air.temperature_c"
                ),
                pressure_bar=self._read_float(
                    self.air_vars["pressure_bar"], "Su basinci", "air", "air.pressure_bar"
                ),
            )
        except ValidationError as exc:
            self._set_banner(str(exc), "error")
            self._update_decision_card("Hava Icerik Testi", "DOGRULANAMADI", str(exc))
            return False

        self._set_coefficient_value("air_a", self.air_vars["a_micro_per_bar"], a_value)
        if log_result:
            self._append_result(
                "Hava Icerik Testi - A hesabi",
                f"A = {a_value:.6f} (10^-6 / bar) olarak hesaplandi.",
            )
        self._set_banner("Hava icerik testi icin A katsayisi guncellendi.", "success")
        return True

    def _calculate_pressure_a(self, log_result: bool = True) -> bool:
        self._clear_feedback("pressure")
        try:
            a_value = calculate_water_compressibility_a(
                temp_c=self._read_float(
                    self.pressure_vars["temperature_c"], "Su sicakligi", "pressure", "pressure.temperature_c"
                ),
                pressure_bar=self._read_float(
                    self.pressure_vars["pressure_bar"], "Su basinci", "pressure", "pressure.pressure_bar"
                ),
            )
        except ValidationError as exc:
            self._set_banner(str(exc), "error")
            self._update_decision_card("Basinc Degisim Testi", "DOGRULANAMADI", str(exc))
            return False

        self._set_coefficient_value("pressure_a", self.pressure_vars["a_micro_per_bar"], a_value)
        if log_result:
            self._append_result(
                "Basinc Degisim Testi - A hesabi",
                f"A = {a_value:.6f} (10^-6 / bar) olarak hesaplandi.",
            )
        self._set_banner("Basinc degisim testi icin A katsayisi guncellendi.", "success")
        return True

    def _calculate_b_helper(self, log_result: bool = True) -> bool:
        self._clear_feedback("pressure")
        try:
            water_beta = calculate_water_thermal_expansion_beta(
                temp_c=self._read_float(
                    self.pressure_vars["temperature_c"], "Su sicakligi", "pressure", "pressure.temperature_c"
                ),
                pressure_bar=self._read_float(
                    self.pressure_vars["pressure_bar"], "Su basinci", "pressure", "pressure.pressure_bar"
                ),
            )
            steel_alpha = self._read_float(
                self.b_helper_vars["steel_alpha_micro_per_c"], "Celik alpha", "pressure", "helper.steel_alpha_micro_per_c"
            )
            b_value = calculate_b_coefficient(water_beta, steel_alpha)
        except ValidationError as exc:
            self._set_banner(str(exc), "error")
            self._update_decision_card("Basinc Degisim Testi", "DOGRULANAMADI", str(exc))
            return False

        self.b_helper_vars["water_beta_micro_per_c"].set(f"{water_beta:.6f}")
        self._set_coefficient_value("pressure_b", self.pressure_vars["b_micro_per_c"], b_value)
        if log_result:
            self._append_result(
                "B Yardimcisi",
                (
                    f"Su beta: {water_beta:.6f} (10^-6 / degC)\n"
                    f"Celik alpha: {steel_alpha:.6f} (10^-6 / degC)\n"
                    f"Hesaplanan B: {b_value:.6f} (10^-6 / degC)"
                ),
            )
        self._set_banner("Basinc degisim testi icin B katsayisi helper ile guncellendi.", "success")
        return True

    def coefficient_value_present(self, key: str) -> bool:
        if key == "air_a":
            return bool(self.air_vars["a_micro_per_bar"].get().strip())
        if key == "pressure_a":
            return bool(self.pressure_vars["a_micro_per_bar"].get().strip())
        return bool(self.pressure_vars["b_micro_per_c"].get().strip())

    def _ensure_coefficient_ready(self, key: str) -> bool:
        if self.coefficient_states[key] in {"computed", "reference", "manual"} and self.coefficient_value_present(key):
            return True
        if key == "air_a":
            if self._air_a_is_auto():
                return self._calculate_air_a(log_result=False)
            if self._air_a_is_reference():
                return self._apply_air_a_reference(log_result=False)
            self._set_feedback("air", "A degeri manuel secenekte tablo/prosedurdan girilmelidir.")
            self._focus_field("air.a_micro_per_bar")
            self._set_banner("Hava testi icin A degeri manuel olarak girilmelidir.", "warning")
            self._update_decision_card("Hava Icerik Testi", "DOGRULANAMADI", "Gerekli A katsayisi hazir degil.")
            return False
        if key == "pressure_a":
            if self._pressure_a_is_auto():
                return self._calculate_pressure_a(log_result=False)
            if self._pressure_a_is_reference():
                return self._apply_pressure_a_reference(log_result=False)
            self._set_feedback("pressure", "A degeri manuel secenekte tablo/prosedurdan girilmelidir.")
            self._focus_field("pressure.a_micro_per_bar")
            self._set_banner("Basinc testi icin A degeri manuel olarak girilmelidir.", "warning")
            self._update_decision_card("Basinc Degisim Testi", "DOGRULANAMADI", "Gerekli A katsayisi hazir degil.")
            return False
        if key == "pressure_b" and self.use_b_helper_var.get():
            if self._pressure_b_is_reference():
                return self._apply_pressure_b_reference(log_result=False)
            return self._calculate_b_helper(log_result=False)
        self._set_feedback("pressure", "B degeri manuel girilmeli veya yardimci ile hesaplanmali.")
        self._focus_field("pressure.b_micro_per_c")
        self._set_banner("Basinc testi icin B degeri hazir degil.", "warning")
        self._update_decision_card("Basinc Degisim Testi", "DOGRULANAMADI", "Gerekli katsayi hazir degil.")
        return False

    def _run_air_test(self) -> None:
        self._clear_all_feedback()
        if not self._ensure_coefficient_ready("air_a"):
            return
        try:
            pipe = self._build_pipe_section("air")
            inputs = AirContentInputs(
                pipe=pipe,
                a_micro_per_bar=self._read_float(
                    self.air_vars["a_micro_per_bar"], "A degeri", "air", "air.a_micro_per_bar"
                ),
                pressure_rise_bar=self._read_float(
                    self.air_vars["pressure_rise_bar"], "Basinc artisi P", "air", "air.pressure_rise_bar"
                ),
                k_factor=self._read_float(self.air_vars["k_factor"], "K faktor", "air", "air.k_factor"),
                actual_added_water_m3=self._read_float(
                    self.air_vars["actual_added_water_m3"], "Fiili ilave su Vpa", "air", "air.actual_added_water_m3"
                ),
            )
            result = evaluate_air_content_test(inputs)
        except ValidationError as exc:
            self._set_banner(str(exc), "error")
            self._update_decision_card("Hava Icerik Testi", "DOGRULANAMADI", str(exc))
            return

        status = "BASARILI" if result.passed else "BASARISIZ"
        self._update_decision_card(
            "Hava Icerik Testi",
            status,
            (
                f"Vp = {result.theoretical_added_water_m3:.6f} m3, limit = {result.acceptance_limit_m3:.6f} m3, "
                f"Vpa = {result.actual_added_water_m3:.6f} m3, oran = {result.ratio:.6f}"
            ),
        )
        self._append_result(
            "Hava Icerik Testi",
            (
                f"Durum: {status}\n"
                f"Su sicakligi: {self.air_vars['temperature_c'].get().strip()} degC\n"
                f"Su basinci: {self.air_vars['pressure_bar'].get().strip()} bar\n"
                f"A: {self.air_vars['a_micro_per_bar'].get().strip()} (10^-6 / bar)\n"
                f"Basinc artisi P (sartname): {self.air_vars['pressure_rise_bar'].get().strip()} bar\n"
                f"K faktor: {self.air_vars['k_factor'].get().strip()}\n"
                f"Ic yaricap: {pipe.internal_radius_mm:.3f} mm\n"
                f"Ic hacim Vt: {pipe.internal_volume_m3:.6f} m3\n"
                f"Teorik ilave su Vp: {result.theoretical_added_water_m3:.6f} m3\n"
                f"Kabul limiti (1.06 x Vp): {result.acceptance_limit_m3:.6f} m3\n"
                f"Fiili ilave su Vpa: {result.actual_added_water_m3:.6f} m3\n"
                f"Vpa / Vp: {result.ratio:.6f}"
            ),
        )
        self._set_banner("Hava icerik testi degerlendirmesi tamamlandi.", "success")

    def _run_pressure_test(self) -> None:
        self._clear_all_feedback()
        if not self._ensure_coefficient_ready("pressure_a"):
            return
        if not self._ensure_coefficient_ready("pressure_b"):
            return
        try:
            pipe = self._build_pipe_section("pressure")
            inputs = PressureVariationInputs(
                pipe=pipe,
                a_micro_per_bar=self._read_float(
                    self.pressure_vars["a_micro_per_bar"], "A degeri", "pressure", "pressure.a_micro_per_bar"
                ),
                b_micro_per_c=self._read_float(
                    self.pressure_vars["b_micro_per_c"], "B degeri", "pressure", "pressure.b_micro_per_c"
                ),
                delta_t_c=self._read_float(
                    self.pressure_vars["delta_t_c"], "Su sicaklik degisimi dT", "pressure", "pressure.delta_t_c"
                ),
                actual_pressure_change_bar=self._read_float(
                    self.pressure_vars["actual_pressure_change_bar"],
                    "Fiili basinc degisimi Pa",
                    "pressure",
                    "pressure.actual_pressure_change_bar",
                ),
            )
            result = evaluate_pressure_variation_test(inputs)
        except ValidationError as exc:
            self._set_banner(str(exc), "error")
            self._update_decision_card("Basinc Degisim Testi", "DOGRULANAMADI", str(exc))
            return

        status = "BASARILI" if result.passed else "BASARISIZ"
        self._update_decision_card(
            "Basinc Degisim Testi",
            status,
            (
                f"Pt = {result.theoretical_pressure_change_bar:.6f} bar, ust sinir = "
                f"{result.allowable_upper_pressure_change_bar:.6f} bar, Pa = "
                f"{result.actual_pressure_change_bar:.6f} bar, fark = {result.margin_bar:.6f} bar"
            ),
        )
        self._append_result(
            "Basinc Degisim Testi",
            (
                f"Durum: {status}\n"
                f"Su sicakligi: {self.pressure_vars['temperature_c'].get().strip()} degC\n"
                f"Su basinci: {self.pressure_vars['pressure_bar'].get().strip()} bar\n"
                f"A: {self.pressure_vars['a_micro_per_bar'].get().strip()} (10^-6 / bar)\n"
                f"B: {self.pressure_vars['b_micro_per_c'].get().strip()} (10^-6 / degC)\n"
                f"Su sicaklik degisimi dT = Tilk - Tson: {self.pressure_vars['delta_t_c'].get().strip()} degC\n"
                f"Fiili basinc degisimi Pa = Pilk - Pson: {self.pressure_vars['actual_pressure_change_bar'].get().strip()} bar\n"
                f"B helper modu: {'Acik' if self.use_b_helper_var.get() else 'Kapali'}\n"
                f"Celik alpha: {self.b_helper_vars['steel_alpha_micro_per_c'].get().strip() or '-'} (10^-6 / degC)\n"
                f"Su beta: {self.b_helper_vars['water_beta_micro_per_c'].get().strip() or '-'} (10^-6 / degC)\n"
                f"Ic yaricap: {pipe.internal_radius_mm:.3f} mm\n"
                f"Teorik basinc degisimi Pt: {result.theoretical_pressure_change_bar:.6f} bar\n"
                f"Ust kabul siniri (Pt + 0.3): {result.allowable_upper_pressure_change_bar:.6f} bar\n"
                f"Fiili basinc degisimi Pa: {result.actual_pressure_change_bar:.6f} bar\n"
                f"Fark (Pa - Pt): {result.margin_bar:.6f} bar"
            ),
        )
        self._set_banner("Basinc degisim testi degerlendirmesi tamamlandi.", "success")

    def _append_result(self, title: str, content: str) -> None:
        stamped_entry = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {title}\n{content}"
        )
        self.report_entries.append(stamped_entry)
        self.results_text.configure(state="normal")
        self.results_text.insert("end", f"\n{stamped_entry}\n")
        self.results_text.see("end")
        self.results_text.configure(state="disabled")

    def _clear_air_form(self) -> None:
        for key, variable in self.air_vars.items():
            if key in {"k_factor", "pressure_rise_bar"}:
                continue
            variable.set("")
        self.air_vars["pressure_rise_bar"].set("1.0")
        self.air_vars["k_factor"].set(self._default_k_factor())
        self.coefficient_states["air_a"] = "empty"
        self._remove_touched_fields("air")
        self._clear_feedback("air")
        self._refresh_coefficient_statuses()
        self._reset_decision_card()
        self._set_banner("Hava icerik testi formu temizlendi.", "info")

    def _clear_pressure_form(self) -> None:
        for variable in self.pressure_vars.values():
            variable.set("")
        self.b_helper_vars["water_beta_micro_per_c"].set("")
        self.b_helper_vars["steel_alpha_micro_per_c"].set(self._default_steel_alpha())
        self.coefficient_states["pressure_a"] = "empty"
        self.coefficient_states["pressure_b"] = "empty"
        self._remove_touched_fields("pressure")
        self._clear_feedback("pressure")
        self._refresh_coefficient_statuses()
        self._reset_decision_card()
        self._set_banner("Basinc degisim testi formu temizlendi.", "info")

    def _clear_results(self) -> None:
        self.report_entries.clear()
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert(
            "end",
            "Oturum sonuclari burada zaman damgasi ile listelenecek.\n"
            "Not: Bu panel bir karar ozeti degil, kayit gunlugudur.\n",
        )
        self.results_text.configure(state="disabled")
        self._reset_decision_card()
        self._set_banner(
            "Sonuc gecmisi temizlendi. Yeni degerlendirme icin guncel girdileri kullanin.",
            "info",
        )

    def _build_report_text(self) -> str:
        lines = [
            f"{APP_NAME} Raporu",
            f"Surum: {APP_VERSION}",
            f"Referans sartname: {SPEC_DOCUMENT_CODE} - {SPEC_DOCUMENT_TITLE}",
            f"Olusturma zamani: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Boru Kesiti",
            f"Dis cap (mm): {self._format_var_value(self.geometry_vars['outside_diameter_mm'])}",
            f"Et kalinligi (mm): {self._format_var_value(self.geometry_vars['wall_thickness_mm'])}",
            f"Hat uzunlugu (m): {self._format_var_value(self.geometry_vars['length_m'])}",
            f"Liste secimi: {self.geometry_catalog_vars['size_option'].get().strip() or '-'}",
            f"Schedule secimi: {self.geometry_catalog_vars['schedule_option'].get().strip() or '-'}",
            "",
        ]
        if self.geometry_segments:
            lines.extend(["Segment Listesi"])
            for index, segment_info in enumerate(self.geometry_segments, start=1):
                pipe = segment_info["pipe"]
                assert isinstance(pipe, PipeSection)
                lines.append(
                    f"{index}. {segment_info['nps_label']} | {segment_info['schedule_label']} | OD {pipe.outside_diameter_mm:.2f} mm | Et {pipe.wall_thickness_mm:.2f} mm | L {pipe.length_m:.2f} m"
                )
            lines.append("")
        lines.extend(
            [
                "Hava Icerik Testi Girdileri",
                f"Su sicakligi (degC): {self._format_var_value(self.air_vars['temperature_c'])}",
                f"Su basinci (bar): {self._format_var_value(self.air_vars['pressure_bar'])}",
                f"A secenegi: {self.air_a_mode_var.get().strip()}",
                f"A referans noktasi: {self.air_a_reference_var.get().strip() or '-'}",
                f"A (10^-6 / bar): {self._format_var_value(self.air_vars['a_micro_per_bar'])}",
                f"Basinc artisi P (bar, sartname 1.0): {self._format_var_value(self.air_vars['pressure_rise_bar'])}",
                f"K faktor: {self._format_var_value(self.air_vars['k_factor'])}",
                f"Fiili ilave su Vpa (m3): {self._format_var_value(self.air_vars['actual_added_water_m3'])}",
                "",
                "Basinc Degisim Testi Girdileri",
                f"Su sicakligi (degC): {self._format_var_value(self.pressure_vars['temperature_c'])}",
                f"Su basinci (bar): {self._format_var_value(self.pressure_vars['pressure_bar'])}",
                f"A secenegi: {self.pressure_a_mode_var.get().strip()}",
                f"A referans noktasi: {self.pressure_a_reference_var.get().strip() or '-'}",
                f"A (10^-6 / bar): {self._format_var_value(self.pressure_vars['a_micro_per_bar'])}",
                f"B secenegi: {self.pressure_b_mode_var.get().strip()}",
                f"B referans noktasi: {self.pressure_b_reference_var.get().strip() or '-'}",
                f"B (10^-6 / degC): {self._format_var_value(self.pressure_vars['b_micro_per_c'])}",
                f"Su sicaklik degisimi dT = Tilk - Tson (degC): {self._format_var_value(self.pressure_vars['delta_t_c'])}",
                f"Fiili basinc degisimi Pa = Pilk - Pson (bar): {self._format_var_value(self.pressure_vars['actual_pressure_change_bar'])}",
                f"B helper modu: {'Acik' if self.use_b_helper_var.get() else 'Kapali'}",
                f"Celik alpha (10^-6 / degC): {self._format_var_value(self.b_helper_vars['steel_alpha_micro_per_c'])}",
                f"Su beta (10^-6 / degC): {self._format_var_value(self.b_helper_vars['water_beta_micro_per_c'])}",
                "",
                "Nihai Karar",
                f"Baslik: {self.decision_title_var.get()}",
                f"Durum: {self.decision_status_var.get()}",
                f"Ozet: {self.decision_summary_var.get()}",
                "",
                "Oturum Sonuclari",
            ]
        )
        if self.report_entries:
            lines.extend(self.report_entries)
        else:
            lines.append("Kaydedilecek sonuc yok.")
        lines.extend(
            [
                "",
                "Not",
                "Bu rapor nihai saha karari icin ASME B31.8 ve proje proseduru ile birlikte degerlendirilmelidir.",
                "Bu cikti dT = Tilk - Tson ve Pa = Pilk - Pson isaret tanimi ile hazirlanmistir.",
            ]
        )
        return "\n".join(lines) + "\n"

    def _save_report(self) -> None:
        initial_name = f"hidrostatik_test_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = filedialog.asksaveasfilename(
            title="Hidrostatik Test Raporunu Kaydet",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=initial_name,
        )
        if not file_path:
            return

        try:
            Path(file_path).write_text(self._build_report_text(), encoding="utf-8")
        except OSError as exc:
            self._set_banner(f"Rapor kaydedilemedi: {exc}", "error")
            messagebox.showerror("Hata", f"Rapor kaydedilemedi: {exc}")
            return

        self._set_banner("Rapor basariyla kaydedildi.", "success")
        messagebox.showinfo("Kaydedildi", f"Rapor kaydedildi:\n{file_path}")

    def _show_about_dialog(self) -> None:
        messagebox.showinfo(
            "Hakkinda",
            (
                f"{APP_NAME}\n"
                f"Surum: {APP_VERSION}\n\n"
                f"Referans sartname: {SPEC_DOCUMENT_CODE}\n"
                f"{SPEC_DOCUMENT_TITLE}\n\n"
                "Bu uygulama hidrostatik test degerlendirmesi icin gelistirildi.\n"
                "Geometri manuel girilebilir, ASME B36.10 katalog listesinden secilebilir\n"
                "ve farkli et kalinliklarina sahip segmentler birlikte modellenebilir."
            ),
        )


def main() -> None:
    root = tk.Tk()
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    HydrostaticTestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
