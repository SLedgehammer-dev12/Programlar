from __future__ import annotations

import unittest
from math import isclose

from hydrotest_core import (
    AirContentInputs,
    PipeSection,
    PressureVariationInputs,
    ValidationError,
    calculate_b_coefficient,
    calculate_water_compressibility_a,
    calculate_water_thermal_expansion_beta,
    evaluate_air_content_test,
    evaluate_pressure_variation_test,
    scale_expansion_coefficient_k_to_micro_per_c,
    scale_isothermal_compressibility_pa_to_micro_per_bar,
)


class PipeSectionTests(unittest.TestCase):
    def test_internal_radius_and_volume_use_internal_geometry(self) -> None:
        section = PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000)

        self.assertTrue(isclose(section.internal_radius_mm, 194.46, rel_tol=1e-6))
        self.assertTrue(isclose(section.internal_volume_m3, 118.79835732832362, rel_tol=1e-9))

    def test_invalid_wall_thickness_raises_validation_error(self) -> None:
        with self.assertRaises(ValidationError):
            PipeSection(outside_diameter_mm=100, wall_thickness_mm=60, length_m=10)


class AirContentTests(unittest.TestCase):
    def test_air_content_pass_case(self) -> None:
        inputs = AirContentInputs(
            pipe=PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000),
            a_micro_per_bar=45.0,
            pressure_rise_bar=70.0,
            k_factor=1.02,
            actual_added_water_m3=0.55,
        )

        result = evaluate_air_content_test(inputs)

        self.assertTrue(result.passed)
        self.assertTrue(isclose(result.theoretical_added_water_m3, 0.5485312776361229, rel_tol=1e-9))
        self.assertTrue(isclose(result.acceptance_limit_m3, 0.5814431542942903, rel_tol=1e-9))

    def test_air_content_fail_case(self) -> None:
        inputs = AirContentInputs(
            pipe=PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000),
            a_micro_per_bar=45.0,
            pressure_rise_bar=70.0,
            k_factor=1.02,
            actual_added_water_m3=0.70,
        )

        result = evaluate_air_content_test(inputs)

        self.assertFalse(result.passed)


class PressureVariationTests(unittest.TestCase):
    def test_pressure_variation_pass_case(self) -> None:
        inputs = PressureVariationInputs(
            pipe=PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000),
            a_micro_per_bar=45.0,
            b_micro_per_c=200.0,
            delta_t_c=0.6,
            actual_pressure_change_bar=2.10,
        )

        result = evaluate_pressure_variation_test(inputs)

        self.assertTrue(result.passed)
        self.assertTrue(isclose(result.theoretical_pressure_change_bar, 1.8556176595353482, rel_tol=1e-9))
        self.assertTrue(isclose(result.margin_bar, 0.24438234046465192, rel_tol=1e-9))

    def test_pressure_variation_fail_case(self) -> None:
        inputs = PressureVariationInputs(
            pipe=PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000),
            a_micro_per_bar=45.0,
            b_micro_per_c=200.0,
            delta_t_c=0.6,
            actual_pressure_change_bar=2.30,
        )

        result = evaluate_pressure_variation_test(inputs)

        self.assertFalse(result.passed)


class CompressibilityScaleTests(unittest.TestCase):
    def test_scale_conversion_matches_micro_per_bar_convention(self) -> None:
        scaled = scale_isothermal_compressibility_pa_to_micro_per_bar(4.497199356927445e-10)
        self.assertTrue(isclose(scaled, 44.97199356927445, rel_tol=1e-12))

    def test_thermal_expansion_scale_matches_micro_per_degree_convention(self) -> None:
        scaled = scale_expansion_coefficient_k_to_micro_per_c(2.1829719116700635e-4)
        self.assertTrue(isclose(scaled, 218.29719116700636, rel_tol=1e-12))


class BCoefficientTests(unittest.TestCase):
    def test_b_coefficient_is_water_minus_steel(self) -> None:
        self.assertTrue(isclose(calculate_b_coefficient(218.29719116700636, 12.0), 206.29719116700636))

    def test_water_thermal_expansion_from_coolprop_is_in_expected_range(self) -> None:
        beta = calculate_water_thermal_expansion_beta(temp_c=20.0, pressure_bar=80.0)
        self.assertGreater(beta, 200.0)
        self.assertLess(beta, 230.0)


class WaterPropertyValidationTests(unittest.TestCase):
    def test_zero_pressure_is_rejected_for_a_calculation(self) -> None:
        with self.assertRaises(ValidationError):
            calculate_water_compressibility_a(temp_c=20.0, pressure_bar=0.0)

    def test_zero_pressure_is_rejected_for_beta_calculation(self) -> None:
        with self.assertRaises(ValidationError):
            calculate_water_thermal_expansion_beta(temp_c=20.0, pressure_bar=0.0)


if __name__ == "__main__":
    unittest.main()
