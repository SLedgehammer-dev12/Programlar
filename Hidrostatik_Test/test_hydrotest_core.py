from __future__ import annotations

import unittest
from math import isclose

from hydrotest_core import (
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

    def test_segmented_geometry_aggregates_length_volume_and_elasticity(self) -> None:
        geometry = PipeGeometry(
            sections=(
                PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=500),
                PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=12.7, length_m=500),
            )
        )

        self.assertTrue(isclose(geometry.total_length_m, 1000.0, rel_tol=1e-12))
        self.assertGreater(geometry.internal_volume_m3, 0.0)
        self.assertGreater(geometry.elasticity_term, 0.0)
        self.assertLess(
            geometry.elasticity_term,
            PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000).elasticity_term,
        )


class AirContentTests(unittest.TestCase):
    def test_air_content_pass_case(self) -> None:
        inputs = AirContentInputs(
            pipe=PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000),
            a_micro_per_bar=45.0,
            pressure_rise_bar=1.0,
            k_factor=1.02,
            actual_added_water_m3=0.0079,
        )

        result = evaluate_air_content_test(inputs)

        self.assertTrue(result.passed)
        self.assertTrue(isclose(result.theoretical_added_water_m3, 0.00783616110908747, rel_tol=1e-9))
        self.assertTrue(isclose(result.acceptance_limit_m3, 0.008306330775632718, rel_tol=1e-9))

    def test_air_content_fail_case(self) -> None:
        inputs = AirContentInputs(
            pipe=PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000),
            a_micro_per_bar=45.0,
            pressure_rise_bar=1.0,
            k_factor=1.02,
            actual_added_water_m3=0.0085,
        )

        result = evaluate_air_content_test(inputs)

        self.assertFalse(result.passed)

    def test_air_content_requires_one_bar_pressure_rise(self) -> None:
        with self.assertRaises(ValidationError):
            AirContentInputs(
                pipe=PipeSection(outside_diameter_mm=406.4, wall_thickness_mm=8.74, length_m=1000),
                a_micro_per_bar=45.0,
                pressure_rise_bar=0.8,
                k_factor=1.02,
                actual_added_water_m3=0.0079,
            )


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

    def test_water_property_reference_points_match_iapws95_cross_check(self) -> None:
        # Reference values were cross-checked against an independent IAPWS-95 implementation.
        reference_points = (
            (10.0, 50.0, 47.193088967078, 99.621630836736, 87.621630836736),
            (15.0, 80.0, 45.786845210898, 165.612819003945, 153.612819003945),
            (20.0, 100.0, 44.744088115012, 221.153338084596, 209.153338084596),
        )

        for temp_c, pressure_bar, expected_a, expected_beta, expected_b in reference_points:
            with self.subTest(temp_c=temp_c, pressure_bar=pressure_bar):
                a_value = calculate_water_compressibility_a(temp_c=temp_c, pressure_bar=pressure_bar)
                beta_value = calculate_water_thermal_expansion_beta(temp_c=temp_c, pressure_bar=pressure_bar)
                b_value = calculate_b_coefficient(beta_value, 12.0)

                self.assertTrue(isclose(a_value, expected_a, rel_tol=1e-9))
                self.assertTrue(isclose(beta_value, expected_beta, rel_tol=1e-9))
                self.assertTrue(isclose(b_value, expected_b, rel_tol=1e-9))


class WaterPropertyValidationTests(unittest.TestCase):
    def test_zero_pressure_is_rejected_for_a_calculation(self) -> None:
        with self.assertRaises(ValidationError):
            calculate_water_compressibility_a(temp_c=20.0, pressure_bar=0.0)

    def test_zero_pressure_is_rejected_for_beta_calculation(self) -> None:
        with self.assertRaises(ValidationError):
            calculate_water_thermal_expansion_beta(temp_c=20.0, pressure_bar=0.0)


if __name__ == "__main__":
    unittest.main()
