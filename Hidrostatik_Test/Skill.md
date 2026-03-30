# Skill.md

## Amaç

Bu proje, ASME B31.8 kapsamındaki doğal gaz boru hattı hidrostatik test verilerini
değerlendiren, işletmeye alma öncesi bütünlük kontrolünü destekleyen, güvenilir bir
Python uygulamasına dönüşmelidir. Proje güvenlik-kritik kabul edilir; bu nedenle
gösterim amaçlı çalışan kod ile sahada güvenilecek kod aynı şey değildir.

## Çalışma Kuralları

### 1. Planla, sonra uygula

- Uygulama, mimari veya formül etkisi olan her iş önce [todo.md](./todo.md) içinde
  kontrol listesi olarak planlanır.
- En az 3 adımlı işler "önce plan" kuralına tabidir.
- Yol değişirse plan hemen güncellenir; eski plan sessizce sürdürülmez.

### 2. Kaynak ve standard disiplini

- Mühendislik formülü, katsayı veya kabul kriteri kaynağı belirtilmeden koda
  eklenmez.
- Resmi ASME B31.8 maddesi erişilemiyorsa ilgili hesap "prosedur tabanli, madde
  dogrulamasi bekliyor" diye etiketlenir.
- "0.884", "1.06", "0.3 bar" gibi sabitler mutlaka bir prosedur, tablo veya maddeye
  bağlanır.
- Her değişken için birim zorunludur.

### 3. Katmanları ayır

- Tkinter sadece arayüz ve kullanıcı etkileşimi için kullanılır.
- Hesaplar saf Python fonksiyonları veya veri sınıfları içinde tutulur.
- Birim dönüşümleri tek yerde toplanır.
- Sonuç üretimi ile doğrulama mantığı UI callback içine gömülmez.

### 4. Doğrulamadan tamam sayma

- Her hesap için en az bir kabul ve bir red örneğiyle test yazılır.
- Sıfır, negatif, eksik, fiziksel olarak anlamsız ve sınır değerler test edilir.
- Sonuçlar mümkünse el hesabı veya referans tablo ile karşılaştırılır.
- "Çalışıyor" demeden önce çıktı birimleri ve kabul kriterleri tekrar kontrol edilir.

### 5. Zarif ama ölçülü çözüm

- Basit problem basit çözümle çözülür; gereksiz soyutlama yapılmaz.
- Geçici yama yerine kök neden hedeflenir.
- Refactor yapılacaksa önce mevcut davranış ve eksikler netleştirilir.

### 6. Otonom hata giderme

- Hata raporu verildiğinde önce tekrar üret, sonra kök nedeni bul, ardından çöz.
- Kullanıcıdan gereksiz yönlendirme beklenmez.
- Düzeltme sonrası ilgili test veya kontrol adımı eklenir.

### 7. Sürekli öğrenme

- Kullanıcı düzeltmesi geldiğinde [tasks/lessons.md](./tasks/lessons.md) dosyasına
  tarih, hata deseni ve önleyici kural eklenir.
- Yeni dersler sonraki oturum başında gözden geçirilir.

## Teknik Standartlar

### Birim sistemi

- Çap ve et kalınlığı: `mm`
- Hat uzunluğu: `m`
- Sıcaklık girişi: `degC`
- Basınç girişi: `bar`
- Hacim: `m3`
- Sıkıştırılabilirlik: açıkça ölçekli biçimde belirtilmeli
- Isıl genleşme farkı: açıkça ölçekli biçimde belirtilmeli

### Kod standardı

- Magic number bırakma; sabitleri isimlendir.
- Hesap fonksiyonlarının imzaları giriş/çıkış birimlerini belli etsin.
- Hata mesajları operatör için anlaşılır, mühendis için izlenebilir olsun.
- UI alanları ile hesap parametreleri birebir eşlenmeli.

## Beklenen Hedef Mimari

- `domain/`: formüller, veri modelleri, kabul kriterleri
- `services/`: doğrulama, raporlama, dönüştürme
- `ui/`: Tkinter ekranları
- `tests/`: referans senaryolar ve regresyon testleri

Bu klasör yapısı hemen kurulmasa bile tüm yeni geliştirmeler bu hedefe göre
düşünülmelidir.
