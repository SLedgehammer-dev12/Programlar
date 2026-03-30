# Hidrostatik Test Degerlendirme

## Proje Ozeti

Bu uygulama, dogal gaz boru hatti hidrostatik test verilerini masaustu arayuz
uzerinden degerlendirmek icin gelistirilmis bir Windows uygulamasidir.
Tkinter tabanli arayuz ile hesap motoru birbirinden ayrilmistir.

## Mevcut Durum

- Hava icerik testi ve basinc degisim testi calisiyor.
- Hesap cekirdegi `hydrotest_core.py` icinde tutuluyor.
- UI durum yonetimi ve raporlama `Hidrostatik_Test_Chat.py` icinde.
- Acilista otomatik guncelleme kontrolu ve manuel guncelleme kontrolu eklendi.
- Uygun release bulundugunda Windows `.exe` paketi kendini guncelleyebiliyor.
- Otomatik test paketi 27 test ile calisiyor.
- Windows one-dir release paketi `build_exe.ps1` ile uretiliyor.
- GitHub release icin `.zip`, `.sha256.txt` ve release note dosyalari uretiliyor.

## Calistirma

- Uygulama: `python Hidrostatik_Test_Chat.py`
- Testler: `python -m unittest discover -s . -p "test_*.py"`
- Release build: `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`

## Release Artefact'lari

`build_exe.ps1` tamamlandiginda `release/` altinda sunlar uretilir:

- `HidrostatikTest-v<surum>-windows-x64.zip`
- `HidrostatikTest-v<surum>-windows-x64.sha256.txt`
- `HidrostatikTest-v<surum>-windows-x64-RELEASE-NOTES.md`
- `raw-dist-<run-id>-primary\HidrostatikTest\HidrostatikTest.exe`

## Dosya Yapisi

- `Hidrostatik_Test_Chat.py`: Tkinter arayuzu
- `hydrotest_core.py`: hesap motoru ve validasyonlar
- `app_metadata.py`: uygulama adi, surum ve yayin metadata'si
- `build_exe.ps1`: Windows release build scripti
- `windows_manifest.xml`: Windows manifest tanimi
- `requirements.txt`: runtime bagimliliklari
- `requirements-dev.txt`: build ve gelistirme bagimliliklari
- `Tests.md`: test ve dogrulama protokolu
- `Release.md`: GitHub release akis dokumani
- `todo.md`: teknik durum ve acik maddeler

## GitHub Release Hazirligi

- Release asset isimleri surum numarasina gore uretilir.
- Release tag formati `hidrostatik-test-v<surum>` olarak kullanilir.
- SHA256 checksum dosyasi eklenir.
- Release body olarak kullanilabilecek markdown notu otomatik yazilir.
- `D:\Program\Python USB\.github\workflows\hidrostatik-test-release.yml` mevcut `Programlar` reposu icinde bu uygulama icin release olusturur.
- `Hidrostatik_Test\.github\workflows\windows-release.yml` ise klasor bagimsiz repo kokune tasinmak istenirse hazir bir workflow sablonudur.

## Guvenlik ve Dagitim Notu

Bu proje Windows ortaminda standalone calisacak sekilde paketlenmistir.
`--noupx`, one-dir paketleme, manifest ve version resource kullanimi
false-positive riskini azaltir. Yine de antivirus veya antimalware engelini
sifira indirmek ancak kod imzalama, yayinci itibari ve kurumsal allow-list
ile mumkundur.

## Acik Muhendislik Notu

Uygulama, resmi standart maddeleri veya sirket proseduru ile nihai kez
dogrulanmadan dogrudan saha karari icin kullanilmamalidir.
