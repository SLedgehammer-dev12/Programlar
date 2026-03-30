# Tests.md

## Amac

Bu dosya, hidrostatik test uygulamasinda degisiklik sonrasi calistirilacak
dogrulama adimlarini standardize eder.

## Otomatik Testler

Her anlamli degisiklikten sonra asagidaki komutlar calistirilir:

- `python -m unittest discover -s "d:\Program\Python USB\Hidrostatik_Test" -p "test_*.py"`
- `python -m py_compile "d:\Program\Python USB\Hidrostatik_Test\Hidrostatik_Test_Chat.py" "d:\Program\Python USB\Hidrostatik_Test\hydrotest_core.py" "d:\Program\Python USB\Hidrostatik_Test\pipe_catalog.py" "d:\Program\Python USB\Hidrostatik_Test\updater.py" "d:\Program\Python USB\Hidrostatik_Test\test_hydrotest_core.py" "d:\Program\Python USB\Hidrostatik_Test\test_pipe_catalog.py" "d:\Program\Python USB\Hidrostatik_Test\test_ui_workflow.py" "d:\Program\Python USB\Hidrostatik_Test\test_updater.py" "d:\Program\Python USB\Hidrostatik_Test\app_metadata.py"`
- `python -c "import sys; sys.path.insert(0, r'd:\Program\Python USB\Hidrostatik_Test'); import Hidrostatik_Test_Chat; import hydrotest_core; import pipe_catalog; import updater; import app_metadata; print('import-ok')"`

## Build ve Release Kontrolu

- `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`
- GitHub release tag'i `hidrostatik-test-v<surum>` ile uyumlu olmali.
- `release\HidrostatikTest-v<surum>-windows-x64.zip` olusmali.
- `release\HidrostatikTest-v<surum>-windows-x64.sha256.txt` olusmali.
- `release\HidrostatikTest-v<surum>-windows-x64-RELEASE-NOTES.md` olusmali.
- `release\raw-dist-<run-id>-primary\HidrostatikTest\HidrostatikTest.exe` olusmali.

## Manuel Smoke Test

UI veya release degisikliginden sonra asagidaki akislar en az bir kez denenir:

1. Hava icerik testi icin gecerli veri gir, `A` hesapla ve testi degerlendir.
2. Basinc degisim testi icin helper ile `B` uret ve testi degerlendir.
3. Aktif formu temizle ve karar kartinin `BEKLIYOR` durumuna dondugunu kontrol et.
4. Preset secimi `Ozel` iken temizleme davranisinin beklenen varsayilana dondugunu kontrol et.
5. Rapor kaydet ve dosyanin olustugunu kontrol et.
6. Uretilen `.exe` temiz klasorde aciliyor mu kontrol et.
7. Acilista guncelleme kontrolu banner ve durum bilgisini guncelliyor mu kontrol et.
8. `Guncelleme Kontrol Et` butonu yeni surum veya guncel surum mesajini dogru gosteriyor mu kontrol et.
9. ASME B36.10 secimi `Dis cap` ve `Et kalinligi` alanlarini dogru dolduruyor mu kontrol et.
10. Segment ekleme ve silme akisi toplam geometri ozetini dogru guncelliyor mu kontrol et.
11. Ust menu altindaki `Dosya`, `Rapor`, `Guncelleme`, `Hakkinda` komutlari beklenen islemleri aciyor mu kontrol et.

## Notlar

- `py_compile` adimi bazi Windows ortamlarinda gecici dosya kilidi nedeniyle hata verebilir.
- Bu durumda unit testler, import smoke check ve PyInstaller build sonucu esas kabul kriteridir.
- Antivirus veya antimalware uyumlulugu tamamen garanti edilemez.
- Riski azaltmak icin one-dir paketleme, `--noupx`, temiz metadata ve kod imzalama onerilir.
