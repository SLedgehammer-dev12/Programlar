from turtle import st
import numpy as np
import CoolProp.CoolProp as CP
from CoolProp.CoolProp import AbstractState
from pint import UnitRegistry
import warnings
import streamlit as st
import pandas as pd
from datetime import datetime
import sys

# --- 1. SABİTLER ve ÇEVRE YAPILANDIRMASI ---

# Pint Birim Yönetimi ve Sabitler
ureg = UnitRegistry()

# Endüstriyel birimlerin tamamı Pint'e tanımlandı
ureg.define('Sm3 = meter**3')
ureg.define('Am3 = meter**3')
ureg.define('scf = foot**3')
ureg.define('MMscf = 1e6 * scf')
ureg.define('MMscfd = MMscf / day')
ureg.define('MMscmd = 1e6 * meter**3 / day')

Q_ = ureg.Quantity

# Standart koşullar (STP) - 15 °C ve 1 atm
T_STANDART_K = Q_(15, 'degC').to('K').m   # 288.15 K
P_STANDART_PA = Q_(1.01325, 'bar').to('pascal').m # 101325 Pa
P_ATM_PA = P_STANDART_PA

# CoolProp tarafından desteklenen doğal gaz bileşenleri
COOLPROP_BILEŞENLER = {
    'METHANE': 'Metan (C1)', 'ETHANE': 'Etan (C2)', 'PROPANE': 'Propan (C3)',
    'N-BUTANE': 'n-Bütan (nC4)', 'I-BUTANE': 'i-Bütan (iC4)', 'N-PENTANE': 'n-Pentan (nC5)',
    'I-PENTANE': 'i-Pentan (iC5)', 'CYCLOPENTANE': 'Siklopentan', 'HEXANE': 'Hekzan (C6)',
    'HEPTANE': 'Heptan (C7)', 'OCTANE': 'Oktan (C8)', 'NITROGEN': 'Azot (N2)',
    'CARBONDIOXIDE': 'Karbondioksit (CO2)', 'WATER': 'Su (H2O)', 'HYDROGEN': 'Hidrojen (H2)',
    'OXYGEN': 'Oksijen (O2)', 'ARGON': 'Argon (Ar)'
}

# EOS Seçenekleri - HEOS öne çıkarıldı
EOS_SEÇENEKLER = {
    "🏆 Yüksek Doğruluk (HEOS) - Tüm Akışkanlar": "HEOS",
    "⚡ Hızlı Hesaplama (Peng-Robinson)": "PR",
    "⚡ Hızlı Hesaplama (Soave-Redlich-Kwong)": "SRK",
    "🔬 Doğalgaz Standart (GERG-2008) - Çok Bileşenli": "GERG-2008"
}

# Birim Seçenekleri
BIRIMLER = {
    'Basınç': ['bar(a)', 'bar(g)', 'psi(a)', 'psi(g)', 'kPa', 'MPa', 'atm'],
    'Sıcaklık': ['°C', 'K', '°F'],
    'Akış Miktarı': ['Sm3/h', 'kg/s', 'kg/h', 'MMscmd', 'MMscfd', 'Am3/h']
}

# --- 2. LOGLAMA ve YARDIMCI FONKSİYONLAR ---

if 'log_records' not in st.session_state:
    st.session_state.log_records = []

def log_message(level: str, message: str, exception=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level.upper()}] {message}"
    if exception:
        log_entry += f" -> Hata Detayı: {str(exception)}"
    st.session_state.log_records.append(log_entry)

def log_info(message):
    log_message("INFO", message)
def log_warning(message):
    log_message("WARNING", message)
def log_error(message, exception=None):
    log_message("ERROR", message, exception)
def log_debug(message):
    log_message("DEBUG", message)

def _get_pressure_type(unit_str):
    if '(g)' in unit_str.lower():
        return 'gauge'
    if '(a)' in unit_str.lower() or unit_str.lower() in ['kpa', 'mpa', 'atm', 'bar', 'psi']: 
        return 'absolute'
    return 'absolute'

# --- 3. ANA SINIF: AirFinnedGasCooler ---
class AirFinnedGasCooler:
    
    def __init__(self, akiskan_kompozisyon, eos_secimi, raw_p_unit):
        log_info(f"Cooler Sınıfı Başlatılıyor. Seçilen EOS: {eos_secimi}")
        self.eos_secimi = eos_secimi
        self.raw_p_unit = raw_p_unit
        self.Q_gercek = None
        self.Q_ideal = None
        
        self.kompozisyon_raw = akiskan_kompozisyon
        self.mol_kompozisyon_coolprop = self._kütlesel_mol_cevir(self.kompozisyon_raw)
        
        self._mol_yuzdesi_kontrol()
        self.karisim_str_full = self._coolprop_karisim_str_olustur(with_concentrations=True)
        self.karisim_str_names_only = self._coolprop_karisim_str_olustur(with_concentrations=False)
        self._molar_kutle_karisim = None

    def _mol_yuzdesi_kontrol(self):
        toplam_kesir = sum(self.mol_kompozisyon_coolprop.values())
        if abs(toplam_kesir - 1.0) > 0.0001:
            log_warning(f"Mol kesirleri toplamı 1.0 değil ({toplam_kesir:.4f}). Bu durum çevrim hatasından veya eksik/fazla yüzdeden kaynaklanabilir.")

    def _kütlesel_mol_cevir(self, kompozisyon):
        if not kompozisyon:
            return {}
        
        girdi_tipi = list(kompozisyon.values())[0]['tip']
        
        if girdi_tipi == 'Molar':
            toplam_yuzde = sum(v['yuzde'] for v in kompozisyon.values())
            return {k: v['yuzde'] / toplam_yuzde for k, v in kompozisyon.items()}
        
        log_info("Kütlesel yüzde girdisi algılandı. Mol kesrine çevrim yapılıyor.")
        toplam_mol = 0
        mol_komp = {}

        for bilesen, val in kompozisyon.items():
            try:
                M = CP.PropsSI('M', bilesen)
                kütle_oran = val['yuzde'] / 100.0
                mol_i = kütle_oran / M
                mol_komp[bilesen] = mol_i
                toplam_mol += mol_i
            except Exception as e:
                log_error(f"CoolProp {bilesen} için Molekül Ağırlığı (M) bulamadı. Bu bileşen CoolProp tarafından desteklenmiyor olabilir.", e)
                raise ValueError(f"HATA: {bilesen} için Mol çevrimi yapılamadı. Bileşen desteklenmiyor.")

        mol_kesirleri = {bilesen: n_i / toplam_mol for bileşen, n_i in mol_komp.items()}
        log_debug(f"Kütlesel kompozisyonun Mol Kesirleri: {mol_kesirleri}")
        return mol_kesirleri

    def _coolprop_karisim_str_olustur(self, with_concentrations=True):
        """CoolProp'un ihtiyaç duyduğu bileşen stringini oluşturur."""
        num_components = len(self.mol_kompozisyon_coolprop)
        
        # TEK BİLEŞEN → SAF İSİM (KONSANTRASYON YOK!)
        if num_components == 1:
            return list(self.mol_kompozisyon_coolprop.keys())[0]
        
        if with_concentrations:
            karisim_listesi = [f"{bileşen}[{kesir:.6f}]" 
                               for bileşen, kesir in self.mol_kompozisyon_coolprop.items() 
                               if bileşen in COOLPROP_BILEŞENLER.keys()]
            return "&".join(karisim_listesi)
        else:
            karisim_listesi = [bileşen 
                               for bileşen in self.mol_kompozisyon_coolprop.keys() 
                               if bileşen in COOLPROP_BILEŞENLER.keys()]
            return "&".join(karisim_listesi)

    def _get_molar_kutle_karisim(self):
        if self._molar_kutle_karisim is None:
            self._molar_kutle_karisim = sum(
                CP.PropsSI('M', bileşen) * kesir 
                for bileşen, kesir in self.mol_kompozisyon_coolprop.items()
            )
        return self._molar_kutle_karisim

    def _coolprop_state_objesi_olustur(self):
        if not self.mol_kompozisyon_coolprop:
            raise ValueError("HATA: Geçerli akışkan kompozisyonu tanımlanmadı.")
            
        backend = self.eos_secimi
        num_components = len(self.mol_kompozisyon_coolprop)
        
        try:
            # 🎯 HEOS - Tüm durumlar için birincil çözüm
            if backend == "HEOS":
                if num_components == 1:
                    saf_akışkan_adı = list(self.mol_kompozisyon_coolprop.keys())[0]
                    AS = AbstractState("HEOS", saf_akışkan_adı) 
                    log_info(f"HEOS ile tek bileşen ({saf_akışkan_adı}) modeli kullanılıyor.")
                else:
                    AS = AbstractState("HEOS", self.karisim_str_full)
                    AS.set_mole_fractions(list(self.mol_kompozisyon_coolprop.values()))
                    log_info(f"HEOS ile çok bileşenli karışım modeli kullanılıyor.")
            
            # 🎯 GERG-2008 - Özel durum için
            elif backend == "GERG-2008":
                if num_components == 1:
                    log_warning("GERG-2008 tek bileşen desteklemiyor. HEOS'a yönlendiriliyor.")
                    saf_akışkan_adı = list(self.mol_kompozisyon_coolprop.keys())[0]
                    AS = AbstractState("HEOS", saf_akışkan_adı)
                else:
                    # GERG-2008 HEOS içinde çalışır
                    AS = AbstractState("HEOS", self.karisim_str_full)
                    AS.set_mole_fractions(list(self.mol_kompozisyon_coolprop.values()))
                    log_info(f"GERG-2008 (HEOS backend) ile çok bileşenli karışım modeli kullanılıyor.")
            
            # 🎯 PR ve SRK - Hızlı hesaplama için
            elif backend in ["PR", "SRK"]:
                AS = AbstractState(backend, self.karisim_str_names_only)
                AS.set_mole_fractions(list(self.mol_kompozisyon_coolprop.values()))
                log_info(f"{backend} ile çok bileşenli karışım modeli kullanılıyor.")
                
            else:
                # Fallback: HEOS
                log_warning(f"Bilinmeyen backend {backend}. HEOS kullanılıyor.")
                if num_components == 1:
                    AS = AbstractState("HEOS", self.karisim_str_names_only)
                else:
                    AS = AbstractState("HEOS", self.karisim_str_full)
                    AS.set_mole_fractions(list(self.mol_kompozisyon_coolprop.values()))
                    
            return AS
            
        except Exception as e:
            log_error(f"CoolProp AbstractState oluşturulamadı ({backend}).", e)
            
            # 🔥 SON ÇARE: HEOS fallback - TEK BİLEŞEN İÇİN KONSANTRASYONSUZ
            try:
                log_info("Birincil yöntem başarısız. HEOS fallback deneniyor...")
                if num_components == 1:
                    saf_akışkan_adı = list(self.mol_kompozisyon_coolprop.keys())[0]
                    AS = AbstractState("HEOS", saf_akışkan_adı)
                    log_info(f"HEOS fallback ile tek bileşen ({saf_akışkan_adı}) modeli kullanılıyor.")
                else:
                    # Çok bileşenli için alternatif yaklaşım
                    AS = AbstractState("HEOS", self.karisim_str_names_only)
                    AS.set_mole_fractions(list(self.mol_kompozisyon_coolprop.values()))
                    log_info(f"HEOS fallback ile çok bileşenli karışım modeli kullanılıyor.")
                return AS
            except Exception as e2:
                log_error("HEOS fallback de başarısız oldu.", e2)
                raise ValueError(f"HATA: CoolProp başlatılamadı. Lütfen kompozisyon ve EOS seçimini kontrol edin. Hata: {str(e2)}")

    def _birim_cevir_P_T(self, P_girdi, T_girdi):
        try:
            P_absolute_SI = P_girdi.to('pascal').m
        except Exception as e:
            log_error(f"Basınç birimi çevrimi başarısız oldu. Girdi: {P_girdi}", e)
            raise ValueError(f"Basınç birimi çevrimi başarısız. Lütfen birim listesini kontrol edin. Hata: {str(e)}")

        p_tipi = _get_pressure_type(self.raw_p_unit) 
        if p_tipi == 'gauge':
            P_absolute_SI += P_ATM_PA
            log_warning("Basınç gösterge (gauge) olarak algılandı. Atmosfer basıncı mutlak basınca çevrim için eklendi.")
        
        T_SI = T_girdi.to('kelvin').m
        log_debug(f"Basınç Final: {P_absolute_SI:.2f} Pa. Sıcaklık Final: {T_SI:.2f} K")
        return P_absolute_SI, T_SI

    def _birim_cevir_m_dot(self, m_dot_val, m_dot_unit, P_giris_SI, T_giris_SI, AS):
        unit = m_dot_unit.lower()
        m_dot_SI = None
        log_info(f"Akış Miktarı çevrimi başlatıldı. Girdi: {m_dot_val} {m_dot_unit}")
        
        if 'kg/s' in unit:
            m_dot_SI = Q_(m_dot_val, 'kg/s').to('kg/second').m
        elif 'kg/h' in unit:
            m_dot_SI = Q_(m_dot_val, 'kg/h').to('kg/second').m
        elif 'sm3/h' in unit or 'mmscmd' in unit or 'mmscfd' in unit or 'am3/h' in unit:
            Vol_m3_s = 0
            D_kg_m3 = 0
            M_karisim_kg_mol = self._get_molar_kutle_karisim()
            R_gaz = 8.314462618

            if 'sm3/h' in unit or 'mmscmd' in unit or 'mmscfd' in unit:
                D_kg_m3 = P_STANDART_PA * M_karisim_kg_mol / (R_gaz * T_STANDART_K)
                log_debug(f"Standart Koşul Yoğunluğu (IdealGas Kanunu): {D_kg_m3:.3f} kg/m3")
            
                if 'sm3/h' in unit:
                    Vol_m3_s = Q_(m_dot_val, 'Sm3/h').to('m**3/s').m
                elif 'mmscfd' in unit:
                    Vol_m3_s = Q_(m_dot_val, 'MMscfd').to('m**3/s').m
                    log_warning("MMscfd birimi Pint ile çevrildi.")
                elif 'mmscmd' in unit:
                    Vol_m3_s = Q_(m_dot_val, 'MMscmd').to('m**3/s').m
                    log_warning("MMscmd birimi Pint ile çevrildi.")
            
            elif 'am3/h' in unit:
                AS.update(CP.PT_INPUTS, P_giris_SI, T_giris_SI)
                D_kg_m3 = AS.rhomass()
                Vol_m3_s = Q_(m_dot_val, 'Am3/h').to('m**3/s').m
                log_debug(f"Gerçek Koşul Yoğunluğu ({self.eos_secimi}): {D_kg_m3:.3f} kg/m3")
            
            m_dot_SI = Vol_m3_s * D_kg_m3

        if m_dot_SI is None:
            log_error(f"Akış miktarı birimi '{m_dot_unit}' desteklenmiyor veya çevrim hatası oluştu.", ValueError("Birim desteklenmiyor"))
            raise ValueError(f"Akış miktarı birimi '{m_dot_unit}' desteklenmiyor.")
            
        log_info(f"Akış miktarı çevrimi başarılı: {m_dot_SI:.3f} kg/s.")
        return m_dot_SI

    def hesapla_isi_yuku(self, m_dot_val, m_dot_unit, P_giris_girdi, T_giris_girdi, T_cikis_girdi):
        log_info("--- TERMAL YÜK HESAPLAMASI BAŞLADI ---")
        P_giris_SI, T_giris_SI = self._birim_cevir_P_T(P_giris_girdi, T_giris_girdi)
        T_cikis_SI = T_cikis_girdi.to('kelvin').m
        AS = self._coolprop_state_objesi_olustur()
        m_dot_SI = self._birim_cevir_m_dot(m_dot_val, m_dot_unit, P_giris_SI, T_giris_SI, AS)
        
        try:
            log_info(f"Gerçek Gaz Entalpi (H) Hesaplaması ({self.eos_secimi})...")
            AS.update(CP.PT_INPUTS, P_giris_SI, T_giris_SI)
            H_giris_J_kg = AS.hmass()
            faz_giris = AS.phase()
            AS.update(CP.PT_INPUTS, P_giris_SI, T_cikis_SI)
            H_cikis_J_kg = AS.hmass()
            faz_cikis = AS.phase()
            
            if faz_cikis != faz_giris and faz_cikis != CP.iphase_gas and faz_giris == CP.iphase_gas:
                 log_warning(f"ÖNEMLİ UYARI: Akışkan yoğuşma bölgesine girmiş olabilir (Giriş: Gaz, Çıkış: {CP.get_phase_string(faz_cikis)}). Hesaplama gizli ısıyı içerir.")

            Delta_H_J_kg = H_giris_J_kg - H_cikis_J_kg
            Q_gercek_W = m_dot_SI * Delta_H_J_kg
            self.Q_gercek = Q_(Q_gercek_W, 'watt')
            log_info(f"Gerçek Gaz Q hesaplaması başarılı: {self.Q_gercek.to('MW'):.3f}")
            
        except Exception as e:
            log_error("Gerçek gaz hesaplaması başarısız oldu.", e)
            self.Q_gercek = None

        try:
            T_ort_SI = (T_giris_SI + T_cikis_SI) / 2
            # İdeal gaz hesaplaması için daha güvenli yaklaşım
            if len(self.mol_kompozisyon_coolprop) == 1:
                saf_akışkan_adı = list(self.mol_kompozisyon_coolprop.keys())[0]
                AS_ideal = AbstractState("IdealGas", saf_akışkan_adı)
            else:
                AS_ideal = AbstractState("IdealGas", self.karisim_str_names_only)
                AS_ideal.set_mole_fractions(list(self.mol_kompozisyon_coolprop.values()))
                
            AS_ideal.update(CP.PT_INPUTS, 101325, T_ort_SI) 
            Cp_karisim_ort_J_kgK = AS_ideal.cpmass()
            Q_ideal_W = m_dot_SI * Cp_karisim_ort_J_kgK * (T_giris_SI - T_cikis_SI)
            self.Q_ideal = Q_(Q_ideal_W, 'watt')
            log_info(f"İdeal Gaz Q hesaplaması başarılı: {self.Q_ideal.to('MW'):.3f}")
        except Exception as e:
            log_warning(f"İdeal Gaz hesaplaması başarısız oldu: {str(e)}")
            self.Q_ideal = None
            
        log_info("--- TERMAL YÜK HESAPLAMASI TAMAMLANDI ---")
        return self.Q_gercek, self.Q_ideal

# --- 4. STREAMLIT ARAYÜZ MANTIĞI ve ÇİZİMİ ---

if 'kompozisyon' not in st.session_state:
    st.session_state.kompozisyon = {}
if 'sonuc_goster' not in st.session_state:
    st.session_state.sonuc_goster = False

def add_component_callback():
    bilesen_adi = st.session_state.yeni_bilesen
    yuzde = st.session_state.yuzde_input
    tip = st.session_state.tip_input
    
    if yuzde > 0:
        if bilesen_adi in st.session_state.kompozisyon:
            st.error("Bu bileşen zaten ekli. Lütfen mevcut listeden düzenleyin.")
            return

        if st.session_state.kompozisyon and list(st.session_state.kompozisyon.values())[0]['tip'] != tip:
             st.error("Karışık (Molar/Kütlesel) girdi yapılamaz. Lütfen aynı tipte kalın.")
             return

        st.session_state.kompozisyon[bilesen_adi] = {'yuzde': yuzde, 'tip': tip}
        st.session_state.sonuc_goster = False
        log_info(f"{COOLPROP_BILEŞENLER[bilesen_adi]} bileşeni (%{yuzde} {tip}) listeye eklendi.")
    else:
        st.error("Yüzde sıfırdan büyük olmalıdır.")

def delete_component_callback(bilesen_adi):
    log_info(f"{COOLPROP_BILEŞENLER[bilesen_adi]} listeden silindi.")
    if bilesen_adi in st.session_state.kompozisyon:
        del st.session_state.kompozisyon[bilesen_adi]
        st.session_state.sonuc_goster = False

def draw_sidebar():
    st.sidebar.title("🛠️ Program Ayarları")
    
    st.sidebar.header("ℹ️ Hakkında (Referanslar)")
    with st.sidebar.expander("Teknik Bilgiler ve Referanslar"):
        st.markdown(f"""
        Bu program, doğalgaz soğutucusu için gerekli ısı yükünü ($\\dot{{Q}}$) hesaplamak üzere tasarlanmıştır.

        **Hesaplama Prensibi:**
        $$\\dot{{Q}} = \\dot{{m}} \\cdot (H_{{giriş}} - H_{{çıkış}})$$

        **Temel Yazılım Bileşenleri:**
        * **Termodinamik Motor:** CoolProp (Yüksek doğruluklu HEOS ve GERG-2008 modellerini destekler)
        * **Birim Yönetimi:** Pint (Tüm mutlak/gösterge basınç ve diğer birim çevrimlerini yönetir)
        * **Referans Standartlar:** API Standard 661, ASME BPVC Sec. VIII Div. 1, BS EN 13445-3
        """)
        
    st.sidebar.header("❓ Yardım (Kullanım Kılavuzu)")
    with st.sidebar.expander("Kullanıcı Kılavuzu ve Hata Çözümleri"):
        st.markdown("""
        **🎯 EOS Seçim Kılavuzu:**
        
        - **🏆 HEOS**: **ÖNERİLEN** - Hem tek hem çok bileşenli tüm akışkanlar için yüksek doğruluk
        - **⚡ PR/SRK**: Hızlı hesaplama için, özellikle yüksek sıcaklık/basınç
        - **🔬 GERG-2008**: Sadece doğalgaz karışımları (çok bileşenli), HEOS otomatik yedek
        
        **📋 Akışkan Kompozisyonu:** Lütfen bileşen yüzdelerini sadece **Molar** veya sadece **Kütlesel** olarak girin.
        
        **🔧 Birimler:** **bar(g) / psi(g)** (gösterge) seçerseniz atmosfer basıncı ($1.01325 \\text{{ bar}}$) otomatik olarak eklenir.
        """)

def draw_main_app():
    st.title("🌡️ Finli Hava Soğutucusu Termal Yük Hesaplayıcı")
    st.markdown("Doğalgaz Kompresör Çıkışı için Soğutma Yükü Hesaplaması (CoolProp Destekli)")

    tab1, tab2, tab3 = st.tabs(["⚙️ Girdiler ve Hesaplama", "✅ Sonuç Raporu", "📜 Log Kayıtları"])

    with tab1:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.header("1. Akışkan Kompozisyonu")
            
            comp_col1, comp_col2, comp_col3 = st.columns([2, 1, 1])
            with comp_col1:
                st.selectbox("Bileşen Seç", list(COOLPROP_BILEŞENLER.keys()), format_func=lambda x: COOLPROP_BILEŞENLER[x], key='yeni_bilesen')
            with comp_col2:
                st.number_input("Yüzde (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key='yuzde_input')
            with comp_col3:
                st.radio("Tip", ['Molar', 'Kütlesel'], key='tip_input')
            
            st.button("➕ Bileşen Ekle", on_click=add_component_callback)

            st.subheader("Mevcut Kompozisyon")
            if st.session_state.kompozisyon:
                girdi_tipi = list(st.session_state.kompozisyon.values())[0]['tip']
                toplam = sum(v['yuzde'] for v in st.session_state.kompozisyon.values() if v['tip'] == girdi_tipi)
                
                df_data = []
                for key, val in st.session_state.kompozisyon.items():
                    df_data.append({
                        "Bileşen": COOLPROP_BILEŞENLER[key],
                        "Yüzde (%)": val['yuzde'],
                        "Tip": val['tip']
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.info(f"Girilen **{girdi_tipi} Yüzdeler Toplamı**: **{toplam:.2f}%**")
                
                if len(st.session_state.kompozisyon) > 0:
                    st.markdown("**Bileşen Silme:**")
                    silme_col = st.columns(min(4, len(st.session_state.kompozisyon)))
                    for i, (key, _) in enumerate(st.session_state.kompozisyon.copy().items()):
                        col_idx = i % len(silme_col)
                        with silme_col[col_idx]:
                            if st.button(f"Sil {COOLPROP_BILEŞENLER[key]}", key=f"del_{key}", on_click=delete_component_callback, args=(key,)):
                                st.rerun() 
            else:
                st.info("Lütfen yukarıdan bileşen ekleyin.")

        with col2:
            st.header("2. Proses Girdileri ve EOS Seçimi")
            
            flow_col1, flow_col2 = st.columns(2)
            with flow_col1:
                st.number_input("Akış Miktarı Değeri", min_value=0.01, value=15.0, step=0.1, key='m_dot_val')
            with flow_col2:
                st.selectbox("Akış Miktarı Birimi", BIRIMLER['Akış Miktarı'], key='m_dot_unit')

            p_col1, p_col2 = st.columns(2)
            with p_col1:
                st.number_input("Giriş Basıncı Değeri", min_value=0.1, value=60.0, step=0.1, key='p_in_val')
            with p_col2:
                st.selectbox("Giriş Basıncı Birimi", BIRIMLER['Basınç'], key='p_in_unit')
                
            T_col1, T_col2 = st.columns(2)
            with T_col1:
                st.number_input("Giriş Sıcaklığı Değeri", value=107.0, step=0.1, key='t_in_val')
                st.number_input("Hedef Çıkış Sıcaklığı Değeri", value=37.0, step=0.1, key='t_out_val')
            with T_col2:
                st.selectbox("Sıcaklık Birimi", BIRIMLER['Sıcaklık'], key='t_unit')

            # EOS seçimi - HEOS varsayılan
            st.selectbox("Hal Denklemi (EOS) Seçimi", 
                        list(EOS_SEÇENEKLER.keys()), 
                        index=0,  # HEOS varsayılan
                        key='eos_secimi_str')
            
            # EOS bilgilendirmesi
            num_components = len(st.session_state.kompozisyon)
            if num_components == 1 and st.session_state.eos_secimi_str == "🔬 Doğalgaz Standart (GERG-2008) - Çok Bileşenli":
                st.warning("⚠️ GERG-2008 tek bileşenle çalışmaz. HEOS otomatik kullanılacak.")
            elif num_components > 1:
                st.success(f"✓ {num_components} bileşenli karışım - Tüm EOS'lar kullanılabilir")
            
            st.markdown("---")
            
            if st.button("🚀 Termal Yükü Hesapla", key='calculate_btn', use_container_width=True):
                st.session_state.log_records = [] 
                log_info("Yeni Hesaplama İsteği Alındı.")
                
                if not st.session_state.kompozisyon:
                    st.error("HATA: Lütfen Akışkan Kompozisyonu ekleyin.")
                elif st.session_state.t_in_val <= st.session_state.t_out_val:
                    st.error("HATA: Giriş sıcaklığı, çıkış sıcaklığından yüksek olmalıdır.")
                else:
                    with st.spinner("Termal yük hesaplanıyor... Log Kayıtları sekmesinden ilerlemeyi takip edin."):
                        
                        try:
                            m_dot_val = st.session_state.m_dot_val
                            m_dot_unit = st.session_state.m_dot_unit
                            
                            p_in_unit_raw = st.session_state.p_in_unit.strip()
                            p_in_unit_cleaned = p_in_unit_raw.replace('(a)', '').replace('(g)', '').strip()
                            t_unit_cleaned = st.session_state.t_unit.strip()

                            P_giris_girdi = Q_(st.session_state.p_in_val, p_in_unit_cleaned)
                            T_giris_girdi = Q_(st.session_state.t_in_val, t_unit_cleaned)
                            T_cikis_girdi = Q_(st.session_state.t_out_val, t_unit_cleaned)
                            
                            eos_val = EOS_SEÇENEKLER[st.session_state.eos_secimi_str]
                            
                            cooler = AirFinnedGasCooler(st.session_state.kompozisyon, eos_val, raw_p_unit=p_in_unit_raw)
                            
                            with warnings.catch_warnings(record=True) as w:
                                warnings.simplefilter("always")
                                Q_gercek, Q_ideal = cooler.hesapla_isi_yuku(m_dot_val, m_dot_unit, P_giris_girdi, T_giris_girdi, T_cikis_girdi)

                                st.session_state.uyarilar = w
                                st.session_state.sonuc_gercek = Q_gercek
                                st.session_state.sonuc_ideal = Q_ideal
                                st.session_state.sonuc_goster = True

                        except Exception as e:
                            log_error("KRİTİK HATA: Hesaplamada bir sorun oluştu.", e)
                            st.error(f"KRİTİK HATA: Hesaplamada bir sorun oluştu. Detaylı bilgi için Log Kayıtları sekmesini kontrol edin.")
                            st.session_state.sonuc_goster = False

    with tab2:
        if 'sonuc_goster' in st.session_state and st.session_state.sonuc_goster and st.session_state.sonuc_gercek:
            st.header("✅ Termal Yük Hesaplama Sonuç Raporu")
            
            if 'uyarilar' in st.session_state and st.session_state.uyarilar:
                st.subheader("❗ Uyarılar ve Kontroller")
                for warning in st.session_state.uyarilar:
                    if "ÖNEMLİ UYARI" in str(warning.message):
                        st.error(f"Kritik Uyarı: {warning.message}")
                    else:
                        st.warning(f"Uyarı: {warning.message}")

            st.subheader("Isı Yükü Hesaplaması ($\dot{Q}$)")
            
            Q_gercek = st.session_state.sonuc_gercek
            Q_ideal = st.session_state.sonuc_ideal

            col_res1, col_res2, col_res3 = st.columns(3)
            
            Q_mw = Q_gercek.to('megawatt')
            col_res1.metric("Gerçek Gaz Isı Yükü ($\dot{Q}_{Gerçek}$)", f"**{Q_mw.m:.6f} MW**", delta_color="off")
            col_res1.caption(f"Kullanılan EOS: {st.session_state.eos_secimi_str}")
                
            if Q_ideal:
                Q_ideal_mw = Q_ideal.to('megawatt')
                col_res2.metric("İdeal Gaz Yaklaşımı ($\dot{Q}_{İdeal}$)", f"{Q_ideal_mw.m:.6f} MW", delta_color="off")
                
                fark = abs(Q_gercek.m - Q_ideal.m) / Q_gercek.m * 100
                col_res3.metric("Fark Yüzdesi (Sapma)", f"%{fark:.2f}", delta_color="off")
                st.caption("Yüksek basınçlarda, farkın büyük olması normaldir. Gerçek Gaz sonucunu kullanınız.")

            st.markdown("---")
            st.subheader("Yazdırılabilir Rapor Detayları")
            
            st.markdown("##### 📝 Hesaplama Girdileri")
            rapor_girdileri = {
                "Akış Miktarı": f"{st.session_state.m_dot_val} {st.session_state.m_dot_unit}",
                "Giriş Basıncı": f"{st.session_state.p_in_val} {st.session_state.p_in_unit}",
                "Sıcaklık (Giriş/Çıkış)": f"{st.session_state.t_in_val} / {st.session_state.t_out_val} {st.session_state.t_unit}",
                "Seçilen EOS": st.session_state.eos_secimi_str,
                "Bileşen Sayısı": f"{len(st.session_state.kompozisyon)} adet"
            }
            st.json(rapor_girdileri)

            st.markdown("##### ⛽ Akışkan Kompozisyonu")
            
            comp_data = []
            for key, val in st.session_state.kompozisyon.items():
                comp_data.append({
                    "Bileşen": COOLPROP_BILEŞENLER[key],
                    "Yüzde (%)": val['yuzde'],
                    "Tip": val['tip']
                })
            comp_df = pd.DataFrame(comp_data)
            st.dataframe(comp_df, use_container_width=True, hide_index=True)

        else:
            st.info("Hesaplama sonuçları bu sekmede gösterilecektir. Lütfen Girdiler sekmesinden hesaplamayı başlatın.")

    with tab3:
        st.header("📜 Program Çalışma ve Debug Kayıtları")
        
        if st.session_state.log_records:
            log_output = "\n".join(st.session_state.log_records)
            st.code(log_output, language='log')
            
            st.download_button(
                label="Logları İndir (TXT)",
                data=log_output,
                file_name=f"air_cooler_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
        else:
            st.info("Hesaplama başlatıldıktan sonra kayıtlar burada görünecektir.")

# Uygulamayı Çalıştırma
if __name__ == '__main__':
    st.set_page_config(
        page_title="Air Finned Gas Cooler Termal Yük",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    draw_sidebar()
    draw_main_app()