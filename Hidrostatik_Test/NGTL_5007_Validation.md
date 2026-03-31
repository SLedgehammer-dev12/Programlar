# NGTL 5007 Validation Notes

Bu not, uygulamanin `4-NGTL 0-GN-P-002-5007 R4 Hidrostatik Test ve Icten Denetleme Sartnamesi`
ile hizalanmasi ve `A` / `B` katsayilarinin dogrulanmasi icin tutulmustur.

## Sartname Eslesmesi

- Madde 5.5: `A` ve `B` degerlerinin 1 bar ve 1 degC artislara gore tablo halinde hazirlanmasi istenir.
- Madde 13: hava icerik testi `1 bar` basinc artisi icin yapilir ve teorik hacim
  `Vp = ((0.884 x ri / s) + A) x 10^-6 x Vt x K` formulu ile hesaplanir.
- Madde 15.2: basinc testi `dP = (B x dT) / ((0.884 x ri / S) + A)` formulu ile hesaplanir.
- Madde 15.2 isaret tanimi:
  - `dT = Tilk - Tson`
  - `Pa = Pilk - Pson`
  - kabul kosulu: `(Pa - dP) <= 0.3 bar`

## Program Kararlari

- Hava icerik testinde `pressure_rise_bar` artik sartnameye gore `1.0 bar` olarak dogrulanir.
- Arayuz ve rapor metni `dT = Tilk - Tson` ve `Pa = Pilk - Pson` tanimlarini acikca gosterir.
- `A`, CoolProp `Water` ozelliginden `ISOTHERMAL_COMPRESSIBILITY` ile alinip `10^-6 / bar` birimine cevrilir.
- `B`, suyun hacimsel termal genlesmesi (`beta`) ile celigin lineer termal genlesme katsayisinin (`alpha`) farki olarak hesaplanir:
  - `B = beta_water - alpha_steel`

## Katsayi Dogrulamasi

`A` ve `beta` degerleri, IAPWS-95 tabanli ikinci bir uygulama ile ayni noktalarda capraz kontrol edildi.
Asagidaki referans noktalar otomatik testlere sabitlendi:

| T (degC) | P (bar) | A (10^-6 / bar) | beta_water (10^-6 / K) | B @ alpha_steel=12 (10^-6 / K) |
| --- | ---: | ---: | ---: | ---: |
| 10 | 50 | 47.193088967078 | 99.621630836736 | 87.621630836736 |
| 15 | 80 | 45.786845210898 | 165.612819003945 | 153.612819003945 |
| 20 | 100 | 44.744088115012 | 221.153338084596 | 209.153338084596 |

## Guncelleme Kontrolu Ariza Analizi

- Yerel arizada Python `urllib` GitHub API cagrisinda `SSLCertVerificationError: Missing Authority Key Identifier`
  hatasi uretti.
- Problem release secim mantigi degil, TLS zincirinin Python tarafinda dogrulanamamasiydi.
- Cozum olarak updater modulu:
  - once standart Python HTTPS yolunu dener,
  - bu yol TLS nedeniyle duserse Windows PowerShell `Invoke-RestMethod` / `Invoke-WebRequest`
    fallback'ine gecer.

Bu not, `test_hydrotest_core.py` ve `test_updater.py` ile birlikte korunur.
