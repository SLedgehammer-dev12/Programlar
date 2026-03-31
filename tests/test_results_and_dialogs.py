import unittest
from unittest.mock import patch

from natural_gas_g5.models.calculation_result import (
    ActualConditionResults,
    CalculationResult,
    StandardConditionResults,
)

try:
    from natural_gas_g5.ui import dialogs
except ModuleNotFoundError:
    dialogs = None


class TestResultDisplay(unittest.TestCase):
    def test_standard_conditions_are_rendered_dynamically(self):
        result = CalculationResult(
            backend_used="HEOS",
            actual=ActualConditionResults(
                temperature=300.0,
                pressure=101325.0,
                density=0.8,
                molar_mass=0.018,
                compressibility_factor=0.99,
                internal_energy=10.0,
                enthalpy=12.0,
                entropy=0.5,
                cp=2.0,
                cv=1.5,
                isentropic_exponent=1.33,
                speed_of_sound=350.0,
            ),
            standard=StandardConditionResults(
                density_std=0.7,
                specific_gravity=0.6,
                reference_temperature=293.15,
                reference_pressure=100000.0,
                standard_name="SATP",
            ),
        )

        display_rows = result.to_display_list()

        self.assertIn(
            ("- STANDART ÇEVRİM BİLGİLERİ (SATP - SCM @ 20.00°C, 100.000 kPa) -", "", ""),
            display_rows,
        )
        self.assertIn(
            ("Standart Koşullar", "293.15 K, 100.000 kPa", "-"),
            display_rows,
        )


class TestDialogs(unittest.TestCase):
    @unittest.skipIf(dialogs is None, "customtkinter is not installed in the test environment")
    @patch("natural_gas_g5.ui.dialogs.messagebox.showwarning")
    def test_component_based_heating_warning_is_shown_for_coolprop_suffix(self, mock_warning):
        dialogs.show_heating_value_method_warning("Bileşen bazlı (CoolProp)")
        mock_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
