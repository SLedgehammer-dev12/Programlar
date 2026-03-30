from __future__ import annotations

import tkinter as tk
import unittest

from Hidrostatik_Test_Chat import HydrostaticTestApp
from app_metadata import APP_VERSION


class UiWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk kullanilamiyor: {exc}")
        self.root.withdraw()
        self.app = HydrostaticTestApp(self.root)

    def tearDown(self) -> None:
        self.root.destroy()

    def _fill_geometry(self) -> None:
        self.app.geometry_vars["outside_diameter_mm"].set("406.4")
        self.app.geometry_vars["wall_thickness_mm"].set("8.74")
        self.app.geometry_vars["length_m"].set("1000")

    def test_temperature_change_marks_computed_air_a_stale(self) -> None:
        self.app.air_vars["temperature_c"].set("20")
        self.app.air_vars["pressure_bar"].set("80")

        self.assertTrue(self.app._calculate_air_a(log_result=False))
        self.assertEqual(self.app.coefficient_states["air_a"], "computed")

        self.app.air_vars["temperature_c"].set("21")

        self.assertEqual(self.app.coefficient_states["air_a"], "stale")

    def test_pressure_evaluation_auto_calculates_a_and_b(self) -> None:
        self._fill_geometry()
        self.app.pressure_vars["temperature_c"].set("20")
        self.app.pressure_vars["pressure_bar"].set("80")
        self.app.pressure_vars["delta_t_c"].set("0.6")
        self.app.pressure_vars["actual_pressure_change_bar"].set("2.1")
        self.app.b_helper_vars["steel_alpha_micro_per_c"].set("12.0")
        self.app.use_b_helper_var.set(True)

        self.app._run_pressure_test()

        self.assertEqual(self.app.decision_status_var.get(), "BASARILI")
        self.assertNotEqual(self.app.pressure_vars["a_micro_per_bar"].get(), "")
        self.assertNotEqual(self.app.pressure_vars["b_micro_per_c"].get(), "")
        self.assertEqual(self.app.coefficient_states["pressure_a"], "computed")
        self.assertEqual(self.app.coefficient_states["pressure_b"], "computed")

    def test_empty_required_field_sets_feedback(self) -> None:
        self.app._run_air_test()

        self.assertIn("bos birakilamaz", self.app.section_feedback_vars["air"].get())
        self.assertEqual(self.app.decision_status_var.get(), "DOGRULANAMADI")

    def test_geometry_summary_updates_from_inputs(self) -> None:
        self._fill_geometry()

        self.assertIn("Ic cap", self.app.geometry_summary_var.get())
        self.assertIn("ic hacim Vt", self.app.geometry_summary_var.get())

    def test_catalog_selection_populates_geometry_fields(self) -> None:
        size_label = next(option for option in self.app.pipe_size_combo.cget("values") if option.startswith("NPS 16 "))
        self.app.geometry_catalog_vars["size_option"].set(size_label)
        self.app._on_pipe_size_selected()
        schedule_label = next(
            option for option in self.app.pipe_schedule_combo.cget("values") if "40 / XS" in option
        )
        self.app.geometry_catalog_vars["schedule_option"].set(schedule_label)

        self.app._apply_catalog_selection()

        self.assertEqual(self.app.geometry_vars["outside_diameter_mm"].get(), "406.40")
        self.assertEqual(self.app.geometry_vars["wall_thickness_mm"].get(), "12.70")

    def test_segment_addition_switches_geometry_to_segment_mode(self) -> None:
        self.app.geometry_vars["outside_diameter_mm"].set("406.4")
        self.app.geometry_vars["wall_thickness_mm"].set("8.74")
        self.app.geometry_vars["length_m"].set("500")
        self.app._add_geometry_segment()
        self.app.geometry_vars["wall_thickness_mm"].set("12.70")
        self.app._add_geometry_segment()

        geometry = self.app._build_pipe_section("air")

        self.assertIn("Segmentli geometri aktif", self.app.geometry_summary_var.get())
        self.assertEqual(len(self.app.segment_tree.get_children()), 2)
        self.assertGreater(geometry.internal_volume_m3, 0.0)

    def test_menu_bar_contains_expected_sections(self) -> None:
        menu = self.root.nametowidget(self.root["menu"])

        labels = [
            menu.entrycget(index, "label")
            for index in range(menu.index("end") + 1)
            if menu.type(index) == "cascade"
        ]

        self.assertEqual(labels, ["Dosya", "Rapor", "Guncelleme", "Hakkinda"])

    def test_clear_active_form_resets_pressure_inputs(self) -> None:
        self.app.notebook.select(1)
        self.app.pressure_vars["temperature_c"].set("20")
        self.app.pressure_vars["pressure_bar"].set("80")
        self.app.pressure_vars["delta_t_c"].set("0.5")
        self.app.pressure_vars["actual_pressure_change_bar"].set("1.9")
        self.app.pressure_vars["b_micro_per_c"].set("180")

        self.app._clear_active_form()

        self.assertEqual(self.app.pressure_vars["temperature_c"].get(), "")
        self.assertEqual(self.app.pressure_vars["pressure_bar"].get(), "")
        self.assertEqual(self.app.pressure_vars["delta_t_c"].get(), "")
        self.assertEqual(self.app.coefficient_states["pressure_a"], "empty")
        self.assertEqual(self.app.coefficient_states["pressure_b"], "empty")

    def test_clear_active_air_form_resets_custom_k_and_decision(self) -> None:
        self.app.notebook.select(0)
        self.app.air_vars["temperature_c"].set("20")
        self.app.air_vars["pressure_bar"].set("80")
        self.app.k_preset_var.set("Ozel")
        self.app.air_vars["k_factor"].set("1.15")
        self.app._update_decision_card("Hava Icerik Testi", "BASARILI", "Eski karar")

        self.app._clear_active_form()

        self.assertEqual(self.app.air_vars["temperature_c"].get(), "")
        self.assertEqual(self.app.air_vars["pressure_bar"].get(), "")
        self.assertEqual(self.app.air_vars["k_factor"].get(), "")
        self.assertEqual(self.app.decision_status_var.get(), "BEKLIYOR")
        self.assertIn("aktif gorunen", self.app.live_notice_var.get())

    def test_clear_pressure_form_uses_selected_steel_preset(self) -> None:
        self.app.notebook.select(1)
        self.app.steel_preset_var.set("Dusuk alasimli celik - 12.5")
        self.app.b_helper_vars["steel_alpha_micro_per_c"].set("99")

        self.app._clear_pressure_form()

        self.assertEqual(self.app.b_helper_vars["steel_alpha_micro_per_c"].get(), "12.5")
        self.app.steel_preset_var.set("Ozel")
        self.app.b_helper_vars["steel_alpha_micro_per_c"].set("88")

        self.app._clear_pressure_form()

        self.assertEqual(self.app.b_helper_vars["steel_alpha_micro_per_c"].get(), "")

    def test_tab_switch_limits_live_notice_to_relevant_fields(self) -> None:
        self.app.notebook.select(0)
        self.app.air_vars["temperature_c"].set("20")
        self.app.air_vars["pressure_bar"].set("80")
        self.app._clear_air_form()
        self.assertIn("aktif gorunen", self.app.live_notice_var.get())

        self.app.notebook.select(1)
        self.app._on_tab_changed()

        self.assertIn("aktif gorunen", self.app.live_notice_var.get())

    def test_invalid_live_input_sets_field_message(self) -> None:
        self.app.air_vars["temperature_c"].set("abc")

        self.assertIn("Gecerli bir sayi", self.app.field_message_vars["air.temperature_c"].get())
        self.assertIn("gecersiz", self.app.live_notice_var.get())

    def test_stale_coefficient_sets_live_warning_message(self) -> None:
        self.app.air_vars["temperature_c"].set("20")
        self.app.air_vars["pressure_bar"].set("80")
        self.assertTrue(self.app._calculate_air_a(log_result=False))

        self.app.air_vars["pressure_bar"].set("81")

        self.assertEqual(self.app.coefficient_states["air_a"], "stale")
        self.assertIn("yeniden hesaplayin", self.app.field_message_vars["air.a_micro_per_bar"].get())
        self.assertIn("guncellenmeli", self.app.live_notice_var.get())

    def test_report_text_contains_version_and_input_snapshot(self) -> None:
        self._fill_geometry()
        self.app.air_vars["temperature_c"].set("20")
        self.app.air_vars["pressure_bar"].set("80")
        self.app.air_vars["k_factor"].set("1.02")
        self.app.pressure_vars["delta_t_c"].set("0.6")
        self.app.b_helper_vars["steel_alpha_micro_per_c"].set("12.0")

        report = self.app._build_report_text()

        self.assertIn(f"Surum: {APP_VERSION}", report)
        self.assertIn("Hava Icerik Testi Girdileri", report)
        self.assertIn("Basinc Degisim Testi Girdileri", report)
        self.assertIn("Dis cap (mm): 406.4", report)
        self.assertIn("Su basinci (bar): 80", report)


if __name__ == "__main__":
    unittest.main()
