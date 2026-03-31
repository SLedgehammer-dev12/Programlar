import unittest
from natural_gas_g5.core import converters
from natural_gas_g5.core.converters import VolumeUnit, PressureUnit, TemperatureUnit

class TestConverters(unittest.TestCase):
    def test_temperature_conversion(self):
        # Celsius to Kelvin
        self.assertAlmostEqual(
            converters.convert_temperature_to_K(25, "°C"),
            298.15
        )
        # Fahrenheit to Kelvin
        self.assertAlmostEqual(
            converters.convert_temperature_to_K(32, "°F"),
            273.15
        )
        
    def test_pressure_conversion(self):
        # kPa to Pa
        self.assertAlmostEqual(
            converters.convert_pressure_to_Pa(100, "kPa"),
            100000.0
        )
        # bar(a) to Pa
        self.assertAlmostEqual(
            converters.convert_pressure_to_Pa(1, "bar(a)"),
            100000.0
        )
        
    def test_volume_conversion(self):
        # m3 to m3
        self.assertAlmostEqual(
            converters.convert_volume_to_m3(100, "m³"),
            100.0
        )
        # L to m3
        self.assertAlmostEqual(
            converters.convert_volume_to_m3(1000, "L"),
            1.0
        )
        # ft3 to m3
        self.assertAlmostEqual(
            converters.convert_volume_to_m3(1, "ft³"),
            0.0283168,
            places=5
        )

if __name__ == '__main__':
    unittest.main()
