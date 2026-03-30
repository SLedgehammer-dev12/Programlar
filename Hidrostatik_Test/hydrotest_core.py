from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Final

from CoolProp.CoolProp import PropsSI

AIR_CONTENT_ACCEPTANCE_FACTOR: Final[float] = 1.06
PRESSURE_VARIATION_ACCEPTANCE_BAR: Final[float] = 0.3
SEAMLESS_PIPE_K: Final[float] = 1.00
WELDED_PIPE_K: Final[float] = 1.02
MICRO_BAR_INVERSE_PER_PA_INVERSE: Final[float] = 1e11
MICRO_PER_C_INVERSE_PER_K_INVERSE: Final[float] = 1e6
ABSOLUTE_ZERO_C: Final[float] = -273.15
FLOAT_TOLERANCE: Final[float] = 1e-9


class ValidationError(ValueError):
    """Raised when user data is incomplete or physically inconsistent."""


@dataclass(frozen=True)
class PipeSection:
    outside_diameter_mm: float
    wall_thickness_mm: float
    length_m: float

    def __post_init__(self) -> None:
        if self.outside_diameter_mm <= 0:
            raise ValidationError("Dış çap sıfırdan büyük olmalıdır.")
        if self.wall_thickness_mm <= 0:
            raise ValidationError("Et kalınlığı sıfırdan büyük olmalıdır.")
        if self.length_m <= 0:
            raise ValidationError("Hat uzunluğu sıfırdan büyük olmalıdır.")
        if self.wall_thickness_mm * 2 >= self.outside_diameter_mm:
            raise ValidationError("Et kalınlığı borunun iç çapını sıfıra düşürecek kadar büyük olamaz.")

    @property
    def internal_radius_mm(self) -> float:
        return (self.outside_diameter_mm / 2) - self.wall_thickness_mm

    @property
    def internal_volume_m3(self) -> float:
        radius_m = self.internal_radius_mm / 1000
        return pi * (radius_m**2) * self.length_m

    @property
    def elasticity_term(self) -> float:
        return 0.884 * self.internal_radius_mm / self.wall_thickness_mm


def scale_isothermal_compressibility_pa_to_micro_per_bar(value_pa_inverse: float) -> float:
    if value_pa_inverse <= 0:
        raise ValidationError("İzotermal sıkıştırılabilirlik pozitif olmalıdır.")
    return value_pa_inverse * MICRO_BAR_INVERSE_PER_PA_INVERSE


def scale_expansion_coefficient_k_to_micro_per_c(value_k_inverse: float) -> float:
    if value_k_inverse <= 0:
        raise ValidationError("Genlesme katsayisi pozitif olmalidir.")
    return value_k_inverse * MICRO_PER_C_INVERSE_PER_K_INVERSE


def calculate_water_compressibility_a(temp_c: float, pressure_bar: float) -> float:
    if temp_c <= ABSOLUTE_ZERO_C:
        raise ValidationError("Sıcaklık mutlak sıfırın altında olamaz.")
    if pressure_bar <= 0:
        raise ValidationError("Basınç sıfırdan büyük olmalıdır.")

    kelvin = temp_c + 273.15
    pascal = pressure_bar * 1e5

    try:
        compressibility_pa_inverse = PropsSI(
            "ISOTHERMAL_COMPRESSIBILITY",
            "T",
            kelvin,
            "P",
            pascal,
            "Water",
        )
    except ValueError as exc:
        raise ValidationError(f"A hesaplanamadı: {exc}") from exc

    return scale_isothermal_compressibility_pa_to_micro_per_bar(compressibility_pa_inverse)


def calculate_water_thermal_expansion_beta(temp_c: float, pressure_bar: float) -> float:
    if temp_c <= ABSOLUTE_ZERO_C:
        raise ValidationError("Sicaklik mutlak sifirin altinda olamaz.")
    if pressure_bar <= 0:
        raise ValidationError("Basinc sifirdan buyuk olmalidir.")

    kelvin = temp_c + 273.15
    pascal = pressure_bar * 1e5

    try:
        expansion_k_inverse = PropsSI(
            "ISOBARIC_EXPANSION_COEFFICIENT",
            "T",
            kelvin,
            "P",
            pascal,
            "Water",
        )
    except ValueError as exc:
        raise ValidationError(f"Su genlesme katsayisi hesaplanamadi: {exc}") from exc

    return scale_expansion_coefficient_k_to_micro_per_c(expansion_k_inverse)


def calculate_b_coefficient(
    water_beta_micro_per_c: float, steel_alpha_micro_per_c: float
) -> float:
    if water_beta_micro_per_c <= 0:
        raise ValidationError("Su genlesme katsayisi pozitif olmalidir.")
    if steel_alpha_micro_per_c < 0:
        raise ValidationError("Celik genlesme katsayisi negatif olamaz.")

    b_micro_per_c = water_beta_micro_per_c - steel_alpha_micro_per_c
    if b_micro_per_c <= 0:
        raise ValidationError("Hesaplanan B katsayisi pozitif cikmadi.")
    return b_micro_per_c


@dataclass(frozen=True)
class AirContentInputs:
    pipe: PipeSection
    a_micro_per_bar: float
    pressure_rise_bar: float
    k_factor: float
    actual_added_water_m3: float

    def __post_init__(self) -> None:
        if self.a_micro_per_bar <= 0:
            raise ValidationError("A değeri sıfırdan büyük olmalıdır.")
        if self.pressure_rise_bar <= 0:
            raise ValidationError("Basınç artışı P sıfırdan büyük olmalıdır.")
        if self.k_factor <= 0:
            raise ValidationError("K faktörü sıfırdan büyük olmalıdır.")
        if self.actual_added_water_m3 < 0:
            raise ValidationError("Fiili ilave su hacmi negatif olamaz.")


@dataclass(frozen=True)
class AirContentResult:
    theoretical_added_water_m3: float
    acceptance_limit_m3: float
    actual_added_water_m3: float
    ratio: float
    passed: bool


def evaluate_air_content_test(inputs: AirContentInputs) -> AirContentResult:
    deformation_term = inputs.pipe.elasticity_term + inputs.a_micro_per_bar
    if deformation_term <= 0:
        raise ValidationError("Hava içerik hesabı için payda/çarpan pozitif olmalıdır.")

    theoretical_added_water_m3 = (
        deformation_term
        * 1e-6
        * inputs.pipe.internal_volume_m3
        * inputs.pressure_rise_bar
        * inputs.k_factor
    )
    if theoretical_added_water_m3 <= FLOAT_TOLERANCE:
        raise ValidationError("Teorik su ilavesi hesaplanamadı.")

    acceptance_limit_m3 = theoretical_added_water_m3 * AIR_CONTENT_ACCEPTANCE_FACTOR
    ratio = inputs.actual_added_water_m3 / theoretical_added_water_m3
    passed = inputs.actual_added_water_m3 <= acceptance_limit_m3 + FLOAT_TOLERANCE

    return AirContentResult(
        theoretical_added_water_m3=theoretical_added_water_m3,
        acceptance_limit_m3=acceptance_limit_m3,
        actual_added_water_m3=inputs.actual_added_water_m3,
        ratio=ratio,
        passed=passed,
    )


@dataclass(frozen=True)
class PressureVariationInputs:
    pipe: PipeSection
    a_micro_per_bar: float
    b_micro_per_c: float
    delta_t_c: float
    actual_pressure_change_bar: float

    def __post_init__(self) -> None:
        if self.a_micro_per_bar <= 0:
            raise ValidationError("A değeri sıfırdan büyük olmalıdır.")
        if self.b_micro_per_c <= 0:
            raise ValidationError("B değeri sıfırdan büyük olmalıdır.")


@dataclass(frozen=True)
class PressureVariationResult:
    theoretical_pressure_change_bar: float
    allowable_upper_pressure_change_bar: float
    actual_pressure_change_bar: float
    margin_bar: float
    passed: bool


def evaluate_pressure_variation_test(inputs: PressureVariationInputs) -> PressureVariationResult:
    deformation_term = inputs.pipe.elasticity_term + inputs.a_micro_per_bar
    if deformation_term <= 0:
        raise ValidationError("Basınç değişim hesabı için payda pozitif olmalıdır.")

    theoretical_pressure_change_bar = (inputs.b_micro_per_c * inputs.delta_t_c) / deformation_term
    allowable_upper_pressure_change_bar = (
        theoretical_pressure_change_bar + PRESSURE_VARIATION_ACCEPTANCE_BAR
    )
    margin_bar = inputs.actual_pressure_change_bar - theoretical_pressure_change_bar
    passed = margin_bar <= PRESSURE_VARIATION_ACCEPTANCE_BAR + FLOAT_TOLERANCE

    return PressureVariationResult(
        theoretical_pressure_change_bar=theoretical_pressure_change_bar,
        allowable_upper_pressure_change_bar=allowable_upper_pressure_change_bar,
        actual_pressure_change_bar=inputs.actual_pressure_change_bar,
        margin_bar=margin_bar,
        passed=passed,
    )
