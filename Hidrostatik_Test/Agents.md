# Agents.md

## Amaç

Bu dosya, proje üzerinde paralel ve odaklı çalışmayı kolaylaştıracak görev
ayrışımını tarif eder. Buradaki "agent" kavramı ister insan, ister yapay zeka,
ister ayrı çalışma oturumu olsun; her biri tek bir sorumluluk alanı taşır.

## Temel Kurallar

- Bir agent bir anda tek bir iş alsın.
- Agent çıktısı mutlaka izlenebilir olsun: karar, kaynak, dosya, risk.
- Aynı formülü iki farklı agent sessizce değiştirmesin.
- Kritik yol üzerindeki blokaj işleri ana akışta tutulur; yan işler ayrıştırılır.

## Önerilen Agent Rolleri

### 1. Standard ve Prosedur Analisti

Sorumluluk:
- ASME B31.8, şirket prosedürü veya hidrotest spesifikasyonundaki formülleri,
  kabul kriterlerini ve sabitleri teyit etmek.

Çıktı:
- Madde veya prosedur referansı
- Formülün birim analizi
- Varsayım ve belirsizlik listesi

### 2. Hesaplama Dogrulama Agent'i

Sorumluluk:
- Python'daki her formülün elle hesap, referans örnek veya test verisiyle
  karşılaştırılması.

Çıktı:
- Beklenen sonuç tablosu
- Kabul/red örnekleri
- Sayısal tolerans önerisi

### 3. Mimari ve Refactor Agent'i

Sorumluluk:
- Tek dosyalı prototipi katmanlı yapıya dönüştürme planını hazırlamak.

Çıktı:
- Modül sınırları
- Veri akış şeması
- Minimum etkili refactor sırası

### 4. UI ve Operator Guvenligi Agent'i

Sorumluluk:
- Eksik alanlar, yanlış birim girişi, belirsiz sonuç ekranı ve kullanıcı hatası
  risklerini incelemek.

Çıktı:
- Form alan listesi
- Zorunlu doğrulamalar
- Hata mesajı ve sonuç ekranı önerileri

### 5. Test ve Regresyon Agent'i

Sorumluluk:
- Otomatik testler, smoke testler ve manuel doğrulama senaryolarını kurmak.

Çıktı:
- Test matrisi
- Çalıştırma komutları
- Başarısızlık durumunda inceleme adımları

## Ne Zaman Ayrıştırılır

- İş 3 adımı geçiyorsa
- Formül doğrulama ve UI işi aynı anda ilerleyebiliyorsa
- Araştırma ve uygulama aynı bağlamı kirletiyorsa
- Mühendislik kaynağı arama işi kod yazmayı blokeliyorsa

## Oturum Sonu Beklentisi

Her agent çıktısında şu dört başlık bulunmalıdır:

- Ne incelendi
- Ne bulundu
- Hangi riskler açık kaldı
- Sonraki net adım ne
