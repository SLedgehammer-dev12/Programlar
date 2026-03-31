import unittest
from natural_gas_g5.models.gas_data import GasComponent, GasMixture
from natural_gas_g5.core.exceptions import ValidationError

class TestGasModels(unittest.TestCase):
    def test_component_validation(self):
        # Valid component
        comp = GasComponent(name="Methane", fraction=90.0)
        self.assertEqual(comp.name, "Methane")
        self.assertEqual(comp.fraction, 90.0)
        
        # Invalid fractions
        with self.assertRaises(ValueError):
            GasComponent(name="Test", fraction=101.0)
        with self.assertRaises(ValueError):
            GasComponent(name="Test", fraction=-1.0)
            
    def test_mixture_validation(self):
        # Valid mixture
        comps = [
            GasComponent(name="Methane", fraction=90.0),
            GasComponent(name="Ethane", fraction=10.0)
        ]
        mixture = GasMixture(components=comps)
        self.assertAlmostEqual(mixture.total_fraction, 100.0)
        mixture.validate_total()
        
        # Invalid total
        comps_bad = [
            GasComponent(name="Methane", fraction=50.0)
        ]
        mixture_bad = GasMixture(components=comps_bad)
        with self.assertRaises(ValidationError):
            mixture_bad.validate_total()
            
    def test_mixture_names(self):
        comps = [
            GasComponent(name="Methane", fraction=50.0),
            GasComponent(name="Ethane", fraction=50.0)
        ]
        mixture = GasMixture(components=comps)
        self.assertEqual(mixture.to_coolprop_string(), "Methane&Ethane")
        
    def test_duplicate_names(self):
        comps = [
            GasComponent(name="Methane", fraction=50.0),
            GasComponent(name="methane", fraction=50.0)
        ]
        with self.assertRaises(ValueError):
            GasMixture(components=comps)

if __name__ == '__main__':
    unittest.main()
