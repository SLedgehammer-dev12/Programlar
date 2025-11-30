import unittest
from calculations import GasFlowCalculator

class TestGasFlowCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = GasFlowCalculator()

    def test_pressure_drop_incompressible(self):
        inputs = {
            'mole_fractions': {'Methane': 1.0},
            'P_in': 5000000, # 50 bar
            'T': 293.15,  # 20 C
            'flow_rate': 10000,
            'flow_unit': 'Sm³/h',
            'L': 1000,
            'D_inner': 200, 
            'roughness': 0.046e-3,
            'total_k': 0,
            'flow_property': 'Sıkıştırılamaz',
            'library_choice': 'CoolProp (High Accuracy EOS)'
        }
        result = self.calc.calculate_pressure_drop(inputs)
        self.assertIn('P_out', result)
        self.assertLess(result['P_out'], inputs['P_in'])

    def test_pressure_drop_compressible(self):
        inputs = {
            'mole_fractions': {'Methane': 1.0},
            'P_in': 5000000,
            'T': 293.15,
            'flow_rate': 10000,
            'flow_unit': 'Sm³/h',
            'L': 1000,
            'D_inner': 200,
            'roughness': 0.046e-3,
            'total_k': 0,
            'flow_property': 'Sıkıştırılabilir',
            'library_choice': 'CoolProp (High Accuracy EOS)'
        }
        result = self.calc.calculate_pressure_drop(inputs)
        self.assertIn('P_out', result)
        self.assertLess(result['P_out'], inputs['P_in'])
        self.assertIn('profile_data', result)

    def test_min_diameter_calculation(self):
        inputs = {
            'mole_fractions': {'Methane': 1.0},
            'P_in': 5000000,
            'T': 293.15,
            'flow_rate': 10000,
            'flow_unit': 'Sm³/h',
            'L': 1000,
            'max_velocity': 20,
            'roughness': 0.046e-3,
            'total_k': 0,
            'flow_property': 'Sıkıştırılabilir',
            'material': 'API 5L Grade B',
            'F': 0.72, 'E': 1.0, 'T_factor': 1.0,
            'P_design': 5000000,
            'library_choice': 'CoolProp (High Accuracy EOS)'
        }
        result = self.calc.calculate_min_diameter(inputs)
        self.assertIn('selected_pipe', result)
        self.assertIn('alternatives', result)
        # Velocity should be reasonable (e.g. > 0.1 m/s and <= 20 m/s)
        self.assertGreater(result['velocity_selected'], 0.1)
        self.assertLessEqual(result['velocity_selected'], 20)

    def test_calculate_max_length(self):
        inputs = {
            'P_in': 5000000, # 50 bar
            'P_out_target': 4000000, # 40 bar
            'T': 288.15,
            'mole_fractions': {'Methane': 1.0},
            'library_choice': 'CoolProp (High Accuracy EOS)',
            'flow_rate': 10000, # Sm3/h
            'flow_unit': 'Sm³/h',
            'D_inner': 202.7, # mm
            'roughness': 0.046e-3,
            'total_k': 0,
            'flow_property': 'Sıkıştırılabilir'
        }
        result = self.calc.calculate_max_length(inputs)
        self.assertIn('L_max', result)
        # Expecting a positive length, likely in kilometers
        self.assertGreater(result['L_max'], 1000) 
        # With 10 bar drop, it should be quite long.


if __name__ == '__main__':
    unittest.main()
