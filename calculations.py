
import math
import numpy as np
import CoolProp.CoolProp as CP
from data import COOLPROP_GASES, PIPE_MATERIALS, PIPE_ROUGHNESS, FITTING_K_FACTORS, ASME_B36_10M_DATA

# R: Evrensel Gaz Sabiti [J/(mol*K)]
R_J_mol_K = 8.314462618
MIN_PRESSURE_PA = 1000.0 # Mutlak minimum basınç (1000 Pa)

class GasFlowCalculator:
    def __init__(self):
        self.log_callback = None

    def set_log_callback(self, callback):
        """Log mesajlarını dışarıya (örn. GUI) iletmek için callback fonksiyonu."""
        self.log_callback = callback

    def log(self, message, level="INFO"):
        if self.log_callback:
            self.log_callback(message, level)

    # --- YARDIMCI FONKSİYONLAR ---
    def validate_inputs(self, inputs):
        """Temel giriş doğrulama."""
        if not inputs.get("gas_composition"): raise ValueError("Gaz bileşimi boş olamaz.")
        if inputs.get("P_in") < 0: raise ValueError("Giriş basıncı negatif olamaz.")
        if inputs.get("T") <= 0: raise ValueError("Sıcaklık pozitif olmalıdır.")
        return True

    def mass_to_mole_fraction(self, mass_fractions):
        total_moles = 0.0; moles = {}
        for gas, mass_frac in mass_fractions.items():
            try: MW = CP.PropsSI('M', gas)
            except Exception as e: raise ValueError(f"{gas} için moleküler ağırlık alınamadı: {str(e)}")
            moles[gas] = mass_frac / MW; total_moles += moles[gas]
        if total_moles == 0: raise ValueError("Toplam mol sıfır!")
        return {gas: mole / total_moles for gas, mole in moles.items()}

    def get_friction_factor(self, Re, relative_roughness):
        if Re < 2000: return 64 / Re
        else:
            # Colebrook-White denklemi iteratif çözüm 
            f_old = 0.02
            for _ in range(20):
                inner = (relative_roughness / 3.7) + (2.51 / (Re * math.sqrt(f_old)))
                f_new = (-2 * math.log10(inner)) ** -2
                if abs(f_new - f_old) < 1e-6: return f_new
                f_old = f_new
            return f_old

    # --- TERMODİNAMİK MODELLER ---
    def get_pure_component_props(self, gas_id):
        try:
            return {
                'Tc': CP.PropsSI('TCRIT', gas_id), 'Pc': CP.PropsSI('PCRIT', gas_id),
                'omega': CP.PropsSI('ACENTRIC', gas_id), 'MW': CP.PropsSI('M', gas_id) * 1000
            }
        except Exception as e:
            # GÜVENLİK DÜZELTMESİ: Varsayılan değer atamak yerine hata fırlatıyoruz.
            raise ValueError(f"CoolProp hatası ({gas_id}): Kritik özellikler alınamadı. {str(e)}")

    def calculate_cubic_eos_props(self, P, T, mole_fractions, EOS_type):
        self.log(f"Hesaplama: {EOS_type} modeli kullanılıyor.", "DEBUG")
        A_c, B_c = (0.45724, 0.07780) if EOS_type == "PR" else (0.42748, 0.08664)
        kappa_coeffs = (0.37464, 1.54226, -0.26992) if EOS_type == "PR" else (0.48, 1.574, -0.176)
        
        b_mix = 0; sqrt_a_mix = 0; MW_mix = 0
        
        for gas, y in mole_fractions.items():
            props = self.get_pure_component_props(gas)
            
            omega = props['omega']
            kappa = kappa_coeffs[0] + kappa_coeffs[1] * omega + kappa_coeffs[2] * omega**2
            
            alpha = (1 + kappa * (1 - math.sqrt(T / props['Tc'])))**2
            a_i = A_c * (R_J_mol_K * props['Tc'])**2 / props['Pc'] * alpha
            b_i = B_c * R_J_mol_K * props['Tc'] / props['Pc']

            b_mix += y * b_i
            sqrt_a_mix += y * math.sqrt(a_i)
            MW_mix += y * props['MW']

        a_mix = sqrt_a_mix**2
        
        A = a_mix * P / (R_J_mol_K * T)**2
        B = b_mix * P / (R_J_mol_K * T)
        
        if EOS_type == "PR":
            coeffs = [1, (B - 1), (A - 3*B**2 - 2*B), (-A*B + B**2 + B**3)]
        else:
            coeffs = [1, -1, (A - B - B**2), -A*B]
        
        roots = np.roots(coeffs)
        real_roots = roots[np.isreal(roots)].real

        if len(real_roots) == 0:
            raise ValueError(f"{EOS_type} modelinde P={P/1e5:.1f} bara, T={T:.1f} K noktasında gerçek kök bulunamadı.")

        Z = max(real_roots)
        
        density = (P * MW_mix * 1e-3) / (Z * R_J_mol_K * T)
        standard_density = (101325 * MW_mix * 1e-3) / (1.0 * R_J_mol_K * 288.15) 
        viscosity = 1.5e-5 * math.sqrt(MW_mix / 16.04) # Basit tahmin

        Cp_mix, k_mix = 0, 0
        for gas, y in mole_fractions.items():
            try:
                Cp_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / 1000 
                k_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / CP.PropsSI('CV0MASS', 'T', T, 'P', 101325, gas)
            except:
                Cp_mix += y * 2.0; k_mix += y * 1.25
        k_avg = k_mix / len(mole_fractions) if len(mole_fractions) > 0 else 1.25
        Cv_mix = Cp_mix / k_avg

        return {
            "MW": MW_mix, "Cp": Cp_mix, "Cv": Cv_mix, "Z": Z, "density": density,
            "viscosity": viscosity, "standard_density": standard_density,
            "EOS_model": EOS_type
        }

    def create_coolprop_state(self, mole_fractions):
        """CoolProp AbstractState nesnesi oluşturur (Performans için)."""
        try:
            backend = "HEOS"
            fluids = list(mole_fractions.keys())
            fractions = list(mole_fractions.values())
            
            # Gaz isimlerini CoolProp formatına uygun hale getir (örn. "Methane (CH4)" -> "Methane")
            # Ancak data.py'da zaten CoolProp isimleri anahtar olarak kullanılıyor (örn. "METHANE" -> "Methane (CH4)")
            # Wait, data.py keys are "METHANE", values are "Methane (CH4)".
            # But inputs['mole_fractions'] keys come from data.py keys?
            # Let's check main.py add_gas_component.
            # It uses gas_id which is the key (e.g. "METHANE").
            # But CoolProp needs "Methane".
            # I need a mapping from ID to CoolProp Name.
            # In data.py: "METHANE": "Methane (CH4)".
            # CoolProp expects "Methane".
            # I should probably clean the names.
            
            clean_fluids = []
            for f in fluids:
                # "Methane (CH4)" -> "Methane"
                # "Nitrogen (N2)" -> "Nitrogen"
                # "Air" -> "Air"
                # Use the value from COOLPROP_GASES but strip the formula
                full_name = COOLPROP_GASES[f]
                clean_name = full_name.split(' (')[0].replace(" ", "")
                clean_fluids.append(clean_name)
                
            state = CP.AbstractState(backend, "&".join(clean_fluids))
            state.set_mole_fractions(fractions)
            return state
        except Exception as e:
            self.log(f"CoolProp State Oluşturma Hatası: {e}", "ERROR")
            return None

    def calculate_coolprop_properties(self, P, T, mixture, state=None):
        # self.log("Hesaplama: CoolProp (Helmholtz EOS) kullanılıyor.", "DEBUG") # Çok log üretir
        standard_P = 101325; standard_T = 288.15
        viscosity_fallback = False
        
        if state:
            try:
                state.update(CP.PT_INPUTS, P, T)
                density = state.rhomass()
                viscosity = state.viscosity()
                MW_mix = state.molar_mass() * 1000
                Cp = state.cpmass() / 1000
                Cv = state.cvmass() / 1000
                Z = state.compressibility_factor()
                
                # Standard Density (Bunu her seferinde hesaplamaya gerek yok aslında ama hızlıdır)
                # State'i değiştirmemek için ayrı hesaplamak lazım veya state'i geri yüklemek lazım.
                # AbstractState tek bir noktayı temsil eder.
                # Standart yoğunluk sabit olduğu için bunu dışarıda bir kere hesaplayıp cache'lemek en iyisi.
                # Şimdilik PropsSI ile devam edelim standart yoğunluk için (sadece 1 kere çağrılırsa sorun değil)
                # Ama döngü içinde çağrılıyorsa sorun.
                # calculate_pressure_drop içinde m_dot hesabı için 1 kere çağrılıyor.
                # Loop içinde calculate_thermo_properties çağrıldığında standart density lazım mı?
                # Return dict'te var.
                # Loop içinde sadece rho ve mu lazım.
                
                # Hızlandırma: Standart yoğunluğu hesaplama (Loop içindeyse)
                standard_density = 0 # Placeholder if optimizing
                
            except Exception as e:
                 # Fallback to PropsSI if AbstractState fails
                 return self.calculate_coolprop_properties(P, T, mixture, state=None)
        else:
            try:
                standard_density = CP.PropsSI('D', 'P', standard_P, 'T', standard_T, mixture)
            except Exception as e:
                raise ValueError(f"CoolProp Standart Yoğunluk Hatası: {str(e)}")
            
            MW_mix = CP.PropsSI('M', 'P', P, 'T', T, mixture) * 1000

            try:
                viscosity = CP.PropsSI('V', 'P', P, 'T', T, mixture)
            except Exception:
                viscosity_fallback = True
                viscosity = 1.5e-5 * math.sqrt(MW_mix / 16.04) # Basit tahmin
            
            Cp = CP.PropsSI('C', 'P', P, 'T', T, mixture) / 1000
            Cv = CP.PropsSI('O', 'P', P, 'T', T, mixture) / 1000
            Z = CP.PropsSI('Z', 'P', P, 'T', T, mixture)
            density = CP.PropsSI('D', 'P', P, 'T', T, mixture)

        props = {
            "MW": MW_mix, "Cp": Cp, "Cv": Cv, "Z": Z,
            "density": density,
            "viscosity": viscosity, "standard_density": standard_density, # Note: standard_density might be 0 if optimized
            "viscosity_fallback": viscosity_fallback
        }
        return props

    def calculate_pseudo_critical_properties(self, P, T, mole_fractions):
        # self.log("Hesaplama: Pseudo-Critical (Kay's Rule) modeli kullanılıyor.", "DEBUG")
        Ppc, Tpc, MW_mix = 0, 0, 0
        for gas, y in mole_fractions.items():
            props = self.get_pure_component_props(gas)
            Ppc += y * props['Pc']; Tpc += y * props['Tc']; MW_mix += y * props['MW']
        
        Pr = P / Ppc; Tr = T / Tpc
        Z = 1.0 + Pr / (14 * Tr) if Pr > 0.1 or Tr < 1.5 else 1.0 
            
        density = (P * MW_mix * 1e-3) / (Z * R_J_mol_K * T)
        standard_density = (101325 * MW_mix * 1e-3) / (1.0 * R_J_mol_K * 288.15) 
        viscosity = 1.5e-5 * math.sqrt(MW_mix / 16.04)

        Cp_mix, k_mix = 0, 0
        for gas, y in mole_fractions.items():
            try:
                Cp_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / 1000
                k_mix += y * CP.PropsSI('CP0MASS', 'T', T, 'P', 101325, gas) / CP.PropsSI('CV0MASS', 'T', T, 'P', 101325, gas)
            except:
                Cp_mix += y * 2.0; k_mix += y * 1.25 
        
        k_avg = k_mix / len(mole_fractions) if len(mole_fractions) > 0 else 1.25
        Cv_mix = Cp_mix / k_avg

        return {
            "MW": MW_mix, "Cp": Cp_mix, "Cv": Cv_mix, "Z": Z, "density": density,
            "viscosity": viscosity, "standard_density": standard_density,
            "Ppc": Ppc, "Tpc": Tpc, "Pr": Pr, "Tr": Tr
        }

    def calculate_thermo_properties(self, P, T, mole_fractions, library_choice, state=None):
        if library_choice == "CoolProp (High Accuracy EOS)":
            mixture = "&".join([f"{k}[{v:.6f}]" for k, v in mole_fractions.items()]) # Fallback string
            return self.calculate_coolprop_properties(P, T, mixture, state)
        elif library_choice == "Peng-Robinson (PR EOS)":
            return self.calculate_cubic_eos_props(P, T, mole_fractions, "PR")
        elif library_choice == "Soave-Redlich-Kwong (SRK EOS)":
            return self.calculate_cubic_eos_props(P, T, mole_fractions, "SRK")
        elif library_choice == "Pseudo-Critical (Kay's Rule)":
            return self.calculate_pseudo_critical_properties(P, T, mole_fractions)
        else:
            raise ValueError(f"Geçersiz termodinamik model seçimi: {library_choice}")

    # --- AKIŞ VE BORU HESAPLARI ---
    def calculate_pressure_drop(self, inputs, num_segments=20):
        """
        Giriş: P_in, T, mole_fractions, library_choice, flow_rate, D_inner, L, roughness, total_k, flow_property
        Çıkış: P_out, delta_p_total, delta_p_pipe, delta_p_fittings, velocity_in, velocity_out, status, profile_data
        """
        P_in = inputs['P_in']; T = inputs['T']; mole_fractions = inputs['mole_fractions']
        library_choice = inputs['library_choice']; flow_val = inputs['flow_rate']; flow_unit = inputs['flow_unit']
        D_inner = inputs['D_inner']; L = inputs['L']; roughness = inputs['roughness']; total_k = inputs['total_k']
        flow_property = inputs['flow_property']

        gas_props_in = self.calculate_thermo_properties(P_in, T, mole_fractions, library_choice)
        rho_in = gas_props_in['density']
        
        # CoolProp State Optimization
        cp_state = None
        if library_choice == "CoolProp (High Accuracy EOS)":
            cp_state = self.create_coolprop_state(mole_fractions)

        # Kütlesel Debi Hesabı
        if flow_unit == "Sm³/h":
            m_dot = (flow_val / 3600) * gas_props_in['standard_density']
        else: # kg/s
            m_dot = flow_val

        # Çapı metreye çevir (Girdi mm)
        D_m = D_inner / 1000.0
        A = math.pi * (D_m ** 2) / 4
        velocity_in = m_dot / (rho_in * A)
        relative_roughness = roughness / D_m

        delta_p_total = 0; delta_p_pipe = 0; delta_p_fittings = 0
        Re_final = 0; f_final = 0; P_out = 0; velocity_out = 0
        
        profile_data = {"distance": [0], "pressure": [P_in], "velocity": [velocity_in]}

        if flow_property == "Sıkıştırılamaz":
            mu = gas_props_in['viscosity']
            Re = (rho_in * velocity_in * D_m) / mu
            f = self.get_friction_factor(Re, relative_roughness)
            
            delta_p_pipe = f * (L / D_m) * (rho_in * velocity_in ** 2) / 2
            delta_p_fittings = total_k * (rho_in * velocity_in ** 2) / 2
            delta_p_total = delta_p_pipe + delta_p_fittings
            P_out = max(MIN_PRESSURE_PA, P_in - delta_p_total)
            
            velocity_out = velocity_in
            Re_final = Re; f_final = f
            gas_props_out = gas_props_in
            
            # Profil (Lineer)
            profile_data["distance"].append(L)
            profile_data["pressure"].append(P_out)
            profile_data["velocity"].append(velocity_out)

        else: # Sıkıştırılabilir (Segmented Integration)
            dL = L / num_segments
            P_current = P_in
            
            total_pipe_loss = 0
            
            for i in range(num_segments):
                # Mevcut şartlarda özellikler
                props = self.calculate_thermo_properties(P_current, T, mole_fractions, library_choice, cp_state)
                rho = props['density']; mu = props['viscosity']
                v = m_dot / (rho * A)
                
                Re = (rho * v * D_m) / mu
                f = self.get_friction_factor(Re, relative_roughness)
                
                # Segment kaybı
                K_seg = total_k / num_segments
                
                dp_friction = f * (dL / D_m) * (rho * v**2) / 2
                dp_fitting = K_seg * (rho * v**2) / 2
                dp_segment = dp_friction + dp_fitting
                
                P_next = max(MIN_PRESSURE_PA, P_current - dp_segment)
                
                total_pipe_loss += dp_friction
                
                P_current = P_next
                
                # Profil verisi
                current_dist = (i + 1) * dL
                profile_data["distance"].append(current_dist)
                profile_data["pressure"].append(P_current)
                
                # Hız tahmini
                if P_next > MIN_PRESSURE_PA:
                     # Bir sonraki adım için yoğunluk tahmini yerine ideal gaz oranı ile hız tahmini (hızlandırma için)
                     # Ama CoolProp kullanıyorsak doğru yoğunluk daha iyi.
                     # Performans için burada thermo çağırmayalım, bir sonraki döngü başında çağrılıyor zaten.
                     # Sadece grafik için v kaydediyoruz.
                     # v_next ~= v * (P_current / P_next)
                     v_next = v * (P_current / P_next)
                else:
                     v_next = v
                
                profile_data["velocity"].append(v_next)
                
                Re_final = Re; f_final = f

            P_out = P_current
            gas_props_out = self.calculate_thermo_properties(P_out, T, mole_fractions, library_choice, cp_state)
            velocity_out = m_dot / (gas_props_out['density'] * A)
            # Profildeki son hızı güncelle
            profile_data["velocity"][-1] = velocity_out
            
            delta_p_total = P_in - P_out
            delta_p_fittings = delta_p_total - total_pipe_loss
            delta_p_pipe = total_pipe_loss

        return {
            "P_out": P_out, "delta_p_total": delta_p_total,
            "delta_p_pipe": delta_p_pipe, "delta_p_fittings": delta_p_fittings,
            "velocity_in": velocity_in, "velocity_out": velocity_out,
            "Re": Re_final, "f": f_final,
            "gas_props_in": gas_props_in, "gas_props_out": gas_props_out,
            "m_dot": m_dot,
            "profile_data": profile_data
        }

    def calculate_max_length(self, inputs):
        """Maksimum uzunluk hesabı (Binary Search)."""
        P_in = inputs['P_in']; P_out_target = inputs['P_out_target']
        
        # Basınç Kontrolü
        if P_out_target > P_in: 
            raise ValueError("Çıkış basıncı giriş basıncından büyük olamaz.")
        if abs(P_in - P_out_target) < 100: # 1 mbar farktan az ise 0 kabul et
             # Temel debi hesabı için yine de özelliklere ihtiyaç var
             gas_props_in = self.calculate_thermo_properties(P_in, inputs['T'], inputs['mole_fractions'], inputs['library_choice'])
             if inputs['flow_unit'] == "Sm³/h":
                m_dot = (inputs['flow_rate'] / 3600) * gas_props_in['standard_density']
             else:
                m_dot = inputs['flow_rate']
                
             return {
                "L_max": 0, 
                "Re": 0, "f": 0, 
                "delta_p_pipe": 0, "delta_p_fittings": 0,
                "m_dot": m_dot,
                "note": "Giriş ve çıkış basıncı eşit."
            }
        
        T = inputs['T']; mole_fractions = inputs['mole_fractions']
        library_choice = inputs['library_choice']; flow_val = inputs['flow_rate']; flow_unit = inputs['flow_unit']
        D_inner = inputs['D_inner']; roughness = inputs['roughness']; total_k = inputs['total_k']
        flow_property = inputs['flow_property']

        # Temel Özellikler
        gas_props_in = self.calculate_thermo_properties(P_in, T, mole_fractions, library_choice)
        rho_in = gas_props_in['density']
        
        # CoolProp State Optimization
        cp_state = None
        if library_choice == "CoolProp (High Accuracy EOS)":
            cp_state = self.create_coolprop_state(mole_fractions)
        
        if flow_unit == "Sm³/h":
            m_dot = (flow_val / 3600) * gas_props_in['standard_density']
        else:
            m_dot = flow_val

        # Çapı metreye çevir
        D_m = D_inner / 1000.0
        A = math.pi * (D_m ** 2) / 4
        velocity_in = m_dot / (rho_in * A)
        relative_roughness = roughness / D_m
        
        delta_p_total_target = P_in - P_out_target
        L_max = 0; Re_final = 0; f_final = 0; delta_p_pipe = 0; delta_p_fittings = 0
        
        if flow_property == "Sıkıştırılamaz":
            mu = gas_props_in['viscosity']
            Re = (rho_in * velocity_in * D_m) / mu
            f = self.get_friction_factor(Re, relative_roughness)
            
            delta_p_fittings = total_k * (rho_in * velocity_in ** 2) / 2
            if delta_p_fittings >= delta_p_total_target:
                return {"L_max": 0, "error": "Boru elemanı kayıpları toplam basınç farkını aşıyor!"}
            
            available_delta_p_pipe = delta_p_total_target - delta_p_fittings
            L_max = (available_delta_p_pipe * 2 * D_m) / (f * rho_in * velocity_in ** 2)
            
            Re_final = Re; f_final = f; delta_p_pipe = available_delta_p_pipe

        else: # Sıkıştırılabilir (Binary Search)
            L_low, L_high = 0.001, 1000000.0 # 1000 km üst limit
            
            for _ in range(50): # Binary Search İterasyonu
                L_mid = (L_low + L_high) / 2
                
                P1 = P_in; P2 = P1 * 0.9
                current_delta_p_total = 0
                
                for _ in range(20):
                    P_avg = (P1 + P2) / 2
                    props = self.calculate_thermo_properties(P_avg, T, mole_fractions, library_choice, cp_state)
                    rho = props['density']; mu = props['viscosity']; v = m_dot / (rho * A)
                    Re = (rho * v * D_m) / mu; f = self.get_friction_factor(Re, relative_roughness)
                    
                    dp_pipe = f * (L_mid / D_m) * (rho * v**2) / 2
                    dp_fit = total_k * (rho * v**2) / 2
                    current_delta_p_total = dp_pipe + dp_fit
                    
                    P2_new = max(MIN_PRESSURE_PA, P1 - current_delta_p_total)
                    if abs(P2_new - P2) < 100: 
                        P2 = P2_new; break
                    P2 = P2_new
                
                if P2 < P_out_target: # Basınç çok düştü, L çok uzun
                    L_high = L_mid
                else: # Basınç hala yüksek, L daha uzun olabilir
                    L_low = L_mid
                
                if abs(L_high - L_low) < 0.1: break
            
            L_max = L_low
            Re_final = Re; f_final = f

        return {
            "L_max": L_max, 
            "Re": Re_final, "f": f_final, 
            "delta_p_pipe": delta_p_pipe, "delta_p_fittings": delta_p_fittings,
            "m_dot": m_dot
        }


    def calculate_min_diameter(self, inputs):
        """Minimum çap hesabı ve ticari boru seçimi (İteratif ve Karşılaştırmalı)."""
        P_in = inputs['P_in']; T = inputs['T']; mole_fractions = inputs['mole_fractions']
        library_choice = inputs['library_choice']; flow_val = inputs['flow_rate']; flow_unit = inputs['flow_unit']
        max_vel = inputs['max_velocity']
        
        # Yeni Girdiler
        L = inputs.get('L', 0)
        flow_property = inputs.get('flow_property', "Sıkıştırılamaz")
        
        # Tasarım Parametreleri
        P_design = inputs['P_design']; material = inputs['material']
        F = inputs['F']; E = inputs['E']; T_factor = inputs['T_factor']

        # 1. Başlangıç Tahmini (Giriş Koşulları)
        gas_props_in = self.calculate_thermo_properties(P_in, T, mole_fractions, library_choice)
        rho_in = gas_props_in['density']
        
        if flow_unit == "Sm³/h":
            m_dot = (flow_val / 3600) * gas_props_in['standard_density']
            flow_rate_actual_in = m_dot / rho_in
        else: # kg/s
            m_dot = flow_val
            flow_rate_actual_in = m_dot / rho_in

        if max_vel <= 0: raise ValueError("Maksimum hız pozitif olmalı.")
        
        # D_min tahmini (Referans için)
        D_min_inner_m = math.sqrt(4 * (flow_rate_actual_in / max_vel) / math.pi)
        D_min_inner_mm = D_min_inner_m * 1000

        # 2. İteratif Seçim ve Karşılaştırma
        # Tüm boruları al (Sıralı değil, gruplanmış lazım)
        all_pipes_flat = self.get_sorted_pipes(P_design, material, F, E, T_factor) 
        # get_sorted_pipes zaten t_required kontrolü yapıyor.
        
        # Gruplama: Nominal Çap -> [Schedule List]
        grouped_pipes = {}
        for p in all_pipes_flat:
            nd = p['nominal']
            if nd not in grouped_pipes: grouped_pipes[nd] = []
            grouped_pipes[nd].append(p)
            
        # Nominal Çapları Sıralama (Küçükten büyüğe)
        def nd_sort_key(nd_str):
            try:
                if ' ' in nd_str:
                    parts = nd_str.split(' ')
                    val = float(parts[0]) + (eval(parts[1].replace(' ', '+')) if len(parts) > 1 else 0)
                elif '/' in nd_str: val = eval(nd_str)
                else: val = float(nd_str.replace('"', ''))
            except: val = 999
            return val
            
        sorted_nds = sorted(grouped_pipes.keys(), key=nd_sort_key)
        
        selected_pipe = None
        final_result = None
        alternatives = {} # "thinner", "thicker"
        
        # En küçük çaptan başlayarak dene
        for nd in sorted_nds:
            schedules = sorted(grouped_pipes[nd], key=lambda x: x['t_mm']) # En inceden kalına
            
            # Bu ND için en ince (ve geçerli) schedule'ı al (zaten get_sorted_pipes geçerlileri döndürdü)
            candidate = schedules[0] 
            
            # Simülasyon
            sim_inputs = inputs.copy()
            sim_inputs = inputs.copy()
            sim_inputs['D_inner'] = candidate['D_inner_mm'] # calculate_pressure_drop içinde metreye çevriliyor
            sim_res = self.calculate_pressure_drop(sim_inputs, num_segments=5) # Hızlı kontrol
            
            if sim_res['velocity_out'] <= max_vel:
                # Bulduk!
                selected_pipe = candidate
                # Hassas hesap
                final_result = self.calculate_pressure_drop(sim_inputs, num_segments=20)
                final_result['velocity_status'] = "Uygun"
                
                # Alternatifleri Bul
                # 1. Thicker (Aynı ND, bir sonraki schedule)
                if len(schedules) > 1:
                    thicker_cand = schedules[1]
                    sim_inputs_thick = inputs.copy()
                    sim_inputs_thick = inputs.copy()
                    sim_inputs_thick['D_inner'] = thicker_cand['D_inner_mm']
                    res_thick = self.calculate_pressure_drop(sim_inputs_thick, num_segments=20)
                    alternatives['thicker'] = {
                        'pipe': thicker_cand, 'result': res_thick, 
                        'note': "Daha Kalın Etli (Aynı Çap)"
                    }
                
                # 2. Thinner (Bir önceki ND'nin en kalını veya bu ND'nin daha incesi - ama t_req sağlamayanlar listede yok)
                # Bir önceki ND'yi kontrol edelim
                current_nd_idx = sorted_nds.index(nd)
                if current_nd_idx > 0:
                    prev_nd = sorted_nds[current_nd_idx - 1]
                    prev_schedules = sorted(grouped_pipes[prev_nd], key=lambda x: x['t_mm'])
                    # Bir önceki çapın en incesi
                    thinner_cand = prev_schedules[0]
                    sim_inputs_thin = inputs.copy()
                    sim_inputs_thin = inputs.copy()
                    sim_inputs_thin['D_inner'] = thinner_cand['D_inner_mm']
                    res_thin = self.calculate_pressure_drop(sim_inputs_thin, num_segments=20)
                    alternatives['thinner'] = {
                        'pipe': thinner_cand, 'result': res_thin,
                        'note': "Bir Alt Çap (Hız Limiti Aşıldı)"
                    }
                
                break
        
        if selected_pipe is None:
             # Hiçbiri uymadı, en büyüğü al
            if sorted_nds:
                last_nd = sorted_nds[-1]
                selected_pipe = grouped_pipes[last_nd][0]
                sim_inputs = inputs.copy(); sim_inputs['D_inner'] = selected_pipe['D_inner_mm']
                final_result = self.calculate_pressure_drop(sim_inputs, num_segments=20)
                final_result['velocity_status'] = "Hız Limiti Aşıldı"
            else:
                return {"error": "Uygun boru standardı bulunamadı."}

        # Sonuçları birleştir
        result = {
            "gas_props_in": gas_props_in,
            "m_dot": m_dot,
            "flow_rate_actual": flow_rate_actual_in, 
            "D_min_inner_mm": D_min_inner_mm, 
            "selected_pipe": selected_pipe,
            "P_design": P_design,
            "max_vel": max_vel,
            "velocity_selected": final_result['velocity_out'],
            "velocity_in": final_result['velocity_in'],
            "velocity_out": final_result['velocity_out'],
            "velocity_status": final_result['velocity_status'],
            "P_out": final_result['P_out'],
            "profile_data": final_result['profile_data'],
            "alternatives": alternatives
        }
        
        return result

    def get_sorted_pipes(self, P_design_pa, material, F, E, T):
        SMYS = PIPE_MATERIALS[material] * 1e6
        all_pipes = []
        for nominal, data in ASME_B36_10M_DATA.items():
            OD = data["OD_mm"]
            t_required = (P_design_pa * (OD / 1000)) / (2 * SMYS * F * E * T) * 1000
            for schedule, t in data["schedules"].items():
                D_inner = OD - 2 * t
                if t >= t_required:
                    all_pipes.append({
                        "nominal": nominal, "OD_mm": OD, "schedule": schedule, "t_mm": t,
                        "D_inner_mm": D_inner, "t_required_mm": t_required
                    })
        
        # Sıralama
        def sort_key(pipe):
            return pipe['D_inner_mm'] # İç çapa göre sırala
        all_pipes.sort(key=sort_key)
        return all_pipes
