from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoefficientReferencePoint:
    key: str
    label: str
    temp_c: float
    pressure_bar: float
    a_micro_per_bar: float
    water_beta_micro_per_c: float
    source_note: str


REFERENCE_POINTS: tuple[CoefficientReferencePoint, ...] = (
    CoefficientReferencePoint(
        key="iapws95_t10_p50",
        label="IAPWS95 | T=10 degC | P=50 bar",
        temp_c=10.0,
        pressure_bar=50.0,
        a_micro_per_bar=47.193088967078,
        water_beta_micro_per_c=99.621630836736,
        source_note="IAPWS-95 capraz kontrol noktasi",
    ),
    CoefficientReferencePoint(
        key="iapws95_t15_p80",
        label="IAPWS95 | T=15 degC | P=80 bar",
        temp_c=15.0,
        pressure_bar=80.0,
        a_micro_per_bar=45.786845210898,
        water_beta_micro_per_c=165.612819003945,
        source_note="IAPWS-95 capraz kontrol noktasi",
    ),
    CoefficientReferencePoint(
        key="iapws95_t20_p100",
        label="IAPWS95 | T=20 degC | P=100 bar",
        temp_c=20.0,
        pressure_bar=100.0,
        a_micro_per_bar=44.744088115012,
        water_beta_micro_per_c=221.153338084596,
        source_note="IAPWS-95 capraz kontrol noktasi",
    ),
)


def get_reference_option_labels() -> tuple[str, ...]:
    return tuple(point.label for point in REFERENCE_POINTS)


def find_reference_point(label: str) -> CoefficientReferencePoint | None:
    normalized = label.strip()
    for point in REFERENCE_POINTS:
        if point.label == normalized:
            return point
    return None
