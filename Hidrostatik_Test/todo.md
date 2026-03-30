# todo.md

## Aktif Plan

- [x] Mevcut prototipi okuyup mimari, dogruluk ve guvenilirlik risklerini cikar.
- [x] Calisma disiplini dokumanlarini ekle.
- [x] Hava icerik testi formulunu kamuya acik prosedurle dogrula.
- [x] Basinc testi formulunu ve kabul kriterini kamuya acik prosedurle dogrula.
- [x] Tum giris alanlarinin birim sozlesmesini netlestir.
- [x] Eksik UI alanlarini ve buton akislarini tamamla.
- [x] Hesap mantigini UI kodundan ayir.
- [x] Sinir durum ve hata validasyonlarini ekle.
- [x] Referans veri seti ile otomatik testler yaz.
- [x] Operator icin sonuc ekrani olustur.
- [x] B katsayisi icin yardimci secim ve hesap ekranini ekle.
- [x] UI icin durum tabanli geri bildirim, karar karti ve otomatik katsayi yenileme akisini ekle.
- [x] Windows icin standalone `.exe` build al.
- [x] GitHub release'e uygun paketleme akisini kur.
- [x] Acilista ve manuel tetiklenen guncelleme kontrol akisini ekle.
- [ ] ASME B31.8 tam madde veya sirket proseduru ile nihai dogrulama yap.
- [ ] 24 saatlik kayit, log ve rapor uretim akisini tasarla.
- [ ] Authenticode kod imzalama ve kurumsal dagitim hazirligi yap.

## Uygulananlar - 2026-03-30

- Karar karti ve aktif form temizleme davranisi duzeltildi.
- `K` ve celik preset temizleme davranislari varsayilanlara gore tutarli hale getirildi.
- Canli validasyon yalnizca aktif sekmeye ilgili alanlar uzerinden calisacak sekilde duzeltildi.
- Legacy ve artik kullanilmayan UI kod bloklari temizlendi.
- Rapor metni uygulama surumu ve giris ozeti ile genisletildi.
- Su ozellik hesaplarinda `0 bar` girisine cekirdek seviyede acik validasyon eklendi.
- GitHub Releases tabanli updater modulu eklendi.
- Acilista otomatik guncelleme kontrolu ve manuel kontrol butonlari eklendi.
- Windows `.exe` icin indir-uygula-yeniden baslat akisi eklendi.
- Repo-ozel `hidrostatik-test-v*` tag duzeni ve monorepo release workflow dosyasi eklendi.
- UI ve cekirdek testleri 27 teste cikarildi.
- `app_metadata.py`, manifest, requirements ve release dokumanlari eklendi.
- `build_exe.ps1` benzersiz build klasorleri ve retry'li zip arsivleme ile guclendirildi.
- Windows release artefact'lari yerel olarak uretildi.
- GitHub Actions icin Windows release workflow dosyasi eklendi.

## Dogrulama Kaydi

- `python -m unittest discover -s "d:\Program\Python USB\Hidrostatik_Test" -p "test_*.py"` -> 27 test gecti.
- `python -c "import sys; sys.path.insert(0, r'd:\Program\Python USB\Hidrostatik_Test'); import Hidrostatik_Test_Chat; import hydrotest_core; import updater; import app_metadata; print('import-ok')"` -> basarili.
- `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1` -> basarili.
- `release\HidrostatikTest-v1.2.0-windows-x64.zip` -> build sonrasi beklenen artefact.
- `release\HidrostatikTest-v1.2.0-windows-x64.sha256.txt` -> build sonrasi beklenen artefact.
- `release\HidrostatikTest-v1.2.0-windows-x64-RELEASE-NOTES.md` -> build sonrasi beklenen artefact.

## Definition of Done

- Her hesap kaynagi ve birimiyle belgelenmis olacak.
- UI alanlari ile hesap parametreleri birebir eslesecek.
- Her test tipi icin acik "basarili / basarisiz / dogrulanamadi" sonucu olacak.
- En az bir kabul ve bir red senaryosu otomatik testle dogrulanacak.
- Windows release paketi checksum ve release note ile birlikte uretilecek.
- Nihai saha kullanimi oncesi ASME B31.8 veya sirket proseduru ile tekrar dogrulama yapilacak.
