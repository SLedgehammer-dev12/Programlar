
import sys
import os

# Add the current directory to sys.path so we can import our modules
sys.path.append(os.getcwd())

from calculations import GasFlowCalculator
from data import COOLPROP_GASES

def test_calculation():
    print("Testing GasFlowCalculator V5...")
    calc = GasFlowCalculator()
    
    # Callback for logging
    def log_callback(msg, level):
        print(f"[{level}] {msg}")
    
    calc.set_log_callback(log_callback)

    # Sample Inputs
    inputs = {
        "P_in": 5000000, # 50 Bar
        "T": 293.15, # 20 C
        "mole_fractions": {"METHANE": 0.9, "ETHANE": 0.1},
        "library_choice": "CoolProp (High Accuracy EOS)",
        "flow_rate": 10000, # Sm3/h
        "flow_unit": "Sm³/h",
        "D_inner": 0.1, # 100 mm
        "L": 1000, # 1 km
        "roughness": 0.0000457,
        "total_k": 2.5,
        "flow_property": "Sıkıştırılamaz"
    }

    try:
        print("\n--- Running Pressure Drop Calculation ---")
        result = calc.calculate_pressure_drop(inputs)
        print("Result:", result)
        print("Pressure Drop Calculation: SUCCESS")
    except Exception as e:
        print(f"Pressure Drop Calculation FAILED: {e}")
        import traceback
        traceback.print_exc()

    try:
        print("\n--- Running Max Length Calculation ---")
        inputs["P_out_target"] = 4000000 # 40 Bar
        inputs["flow_property"] = "Sıkıştırılabilir"
        result_len = calc.calculate_max_length(inputs)
        print("Result:", result_len)
        print("Max Length Calculation: SUCCESS")
    except Exception as e:
        print(f"Max Length Calculation FAILED: {e}")
        import traceback
        traceback.print_exc()

    try:
        print("\n--- Running Min Diameter Calculation ---")
        inputs_min_d = inputs.copy()
        inputs_min_d["target"] = "Minimum Çap"
        inputs_min_d["max_velocity"] = 20.0
        inputs_min_d["P_design"] = 5000000 # 50 Bar Gauge
        inputs_min_d["material"] = "API 5L Grade B"
        inputs_min_d["F"] = 0.72
        inputs_min_d["E"] = 1.0
        inputs_min_d["T_factor"] = 1.0
        
        result_min_d = calc.calculate_min_diameter(inputs_min_d)
        print("Result:", result_min_d)
        print("Min Diameter Calculation: SUCCESS")
    except Exception as e:
        print(f"Min Diameter Calculation FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_calculation()
