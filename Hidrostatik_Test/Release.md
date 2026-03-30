# Release.md

## Amac

Bu dosya, Windows icin dagitilacak release paketinin nasil uretildigini ve
GitHub release'e hangi artefact'larin yuklenecegini tarif eder.

## Uretilen Artefact'lar

`build_exe.ps1` calistiginda `release/` altinda sunlar uretilir:

- `HidrostatikTest-v<surum>-windows-x64.zip`
- `HidrostatikTest-v<surum>-windows-x64.sha256.txt`
- `HidrostatikTest-v<surum>-windows-x64-RELEASE-NOTES.md`
- `raw-dist-<run-id>-primary\HidrostatikTest\HidrostatikTest.exe`

## Build Komutu

- `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`
- GitHub release tag'i: `hidrostatik-test-v<surum>`

Opsiyonel:

- `-SkipTests`: testleri atlar
- `-SkipArchive`: zip ve checksum uretimini atlar

## GitHub Release Yukleme Sirasi

1. `hidrostatik-test-v<surum>` tag'i ile release tetikle.
2. `release\HidrostatikTest-v<surum>-windows-x64.zip` dosyasini upload et.
3. Ayni release'e `release\HidrostatikTest-v<surum>-windows-x64.sha256.txt` dosyasini ekle.
4. `release\HidrostatikTest-v<surum>-windows-x64-RELEASE-NOTES.md` icerigini release body olarak kullan.

## GitHub Actions

- `D:\Program\Python USB\.github\workflows\hidrostatik-test-release.yml` mevcut `Programlar` reposu icin etkin workflow'dur.
- `Hidrostatik_Test\.github\workflows\windows-release.yml` klasor bagimsiz repo olarak ayrilmak istenirse kullanilabilir.
- Tag ile calistiginda release asset'larini GitHub release sayfasina ekler.
- `workflow_dispatch` ile calistiginda artefact'lari Actions artefact olarak saklar.

## Antivirus Notu

- One-dir paketleme kullanilir.
- `--noupx` ile binary sikistirma kapatilir.
- Version resource ve Windows manifest exe icine gomulur.
- Bu adimlar false-positive riskini azaltir, ama kod imzalama olmadan sifir garanti vermez.
- Kurumsal dagitim veya genis kullanici kitlesi icin Authenticode imzalama onerilir.
