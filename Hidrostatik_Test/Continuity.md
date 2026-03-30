# Continuity.md

## Proje Durumu

Tarih: 2026-03-24

Mevcut durum:
- Proje artık ayrık bir hesap çekirdeği ve bir Tkinter arayüzünden oluşuyor.
- Ana dosyalar: `hydrotest_core.py`, `Hidrostatik_Test_Chat.py`, `test_hydrotest_core.py`, `test_ui_workflow.py`
- Temel otomatik testler mevcut ve geçiyor.
- Hava içerik testi ile basınç değişim testi için kullanıcıya doğrudan sonuç verilebiliyor.
- Windows için standalone build üretildi: `dist\\HidrostatikTest\\HidrostatikTest.exe`

## Teknik Gercekler

- Hesap çekirdeği saf Python veri sınıfları ve fonksiyonları ile çalışıyor.
- GUI import edildiğinde otomatik açılmıyor; `main()` koruması var.
- Çap artık dış çap olarak yorumlanıyor ve iç hacim buna göre hesaplanıyor.
- `A` değeri otomatik hesaplanıyor, `B` değeri manuel doğrulanmış giriş olarak bekleniyor.
- `B` için ayrıca su beta ve celik alpha tabanli bir yardımcı hesap akışı var.
- Sonuç ekranı teorik değerleri, kabul sınırını ve karar durumunu yazıyor.
- UI'de katsayı durumları `Bekleniyor / Hazir / Guncellenmeli / Manuel giris` olarak izleniyor.
- Nihai karar ayrı kartta gösteriliyor; oturum logu ayrı panelde tutuluyor.
- Sonuçlar `.txt` rapor olarak kaydedilebiliyor.

## Temel Varsayımlar

- Kullanıcı birimleri `mm`, `m`, `bar`, `degC` cinsinden giriyor.
- `B` katsayısı kullanıcı tarafından onaylı tablo veya prosedürden alınıyor.
- Kamuya açık prosedür ile kurulan formüller, resmi standart maddesiyle daha sonra tekrar teyit edilecek.

## Açık Riskler

- ASME B31.8 tam madde doğrulaması hâlâ yapılmadı.
- 24 saatlik zaman serisi ve log akışı henüz modellenmedi.
- Basınç değişim testindeki işaret konvansiyonu şirket prosedürüne göre ayrıca doğrulanmalı.
- Üretilen `.exe` için AV false-positive riski azaltıldı ama sıfır garanti yok; kod imzalama hâlâ açık iş.

## Sonraki Oturum Baslangic Kontrolu

- [ ] Önce [todo.md](./todo.md) dosyasını oku.
- [ ] Ardından [tasks/lessons.md](./tasks/lessons.md) dosyasını gözden geçir.
- [ ] ASME / şirket prosedürü için erişilen yeni kaynak var mı kontrol et.
- [ ] `B` katsayısı tablosu ve işaret konvansiyonu net mi doğrula.
- [ ] Yeni özellik eklemeden önce test paketini çalıştır.

## Karar Kaydi

- Görev takibi için kök dizindeki `todo.md` kullanılacak.
- Kullanıcı düzeltmeleri için `tasks/lessons.md` ayrıldı.
- Mühendislik sabitleri, kaynak gösterilmeden kalıcılaştırılmayacak.
- `B` değeri otomatik türetilmeyecek; doğrulanmış veri olarak girilecek.
- Yardımcı `B` hesabı sadece operatöre destek verir; son değer yine prosedürle teyit edilmelidir.
- Standalone dağıtım için `one-dir`, `no UPX` PyInstaller stratejisi benimsendi.
