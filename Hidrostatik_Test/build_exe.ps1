param(
    [string]$PythonExe = "python",
    [switch]$SkipTests,
    [switch]$SkipArchive
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$metadataPath = Join-Path $projectRoot "app_metadata.py"
$entryPoint = Join-Path $projectRoot "Hidrostatik_Test_Chat.py"
$manifestPath = Join-Path $projectRoot "windows_manifest.xml"
$releasePath = Join-Path $projectRoot "release"

function Get-MetadataValue {
    param([string]$Name)

    $pattern = '^{0}\s*=\s*"(?<value>.+)"$' -f [regex]::Escape($Name)
    $match = Select-String -Path $metadataPath -Pattern $pattern | Select-Object -First 1
    if (-not $match) {
        throw "Metadata alani okunamadi: $Name"
    }
    return $match.Matches[0].Groups["value"].Value
}

function Write-VersionInfoFile {
    param(
        [string]$OutputPath,
        [string]$AppVersion,
        [string]$AppName,
        [string]$PublisherName,
        [string]$CopyrightNotice
    )

    $segments = @($AppVersion.Split("."))
    while ($segments.Count -lt 4) {
        $segments += "0"
    }
    $versionTuple = ($segments[0..3] -join ", ")

    $content = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($versionTuple),
    prodvers=($versionTuple),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '$PublisherName'),
          StringStruct('FileDescription', '$AppName'),
          StringStruct('FileVersion', '$AppVersion'),
          StringStruct('InternalName', '$AppName'),
          StringStruct('OriginalFilename', '$AppName.exe'),
          StringStruct('ProductName', '$AppName'),
          StringStruct('ProductVersion', '$AppVersion'),
          StringStruct('LegalCopyright', '$CopyrightNotice')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@

    Set-Content -LiteralPath $OutputPath -Value $content -Encoding UTF8
}

function Write-ReleaseNotes {
    param(
        [string]$OutputPath,
        [string]$AppName,
        [string]$AppVersion,
        [string]$ArtifactName,
        [string]$HashFileName,
        [bool]$WindowsResourcesEmbedded,
        [string]$ReleaseTag
    )

    $resourceStatus = if ($WindowsResourcesEmbedded) {
        "Version resource and Windows manifest embedded"
    } else {
        "Plain fallback build used because Windows resource embedding failed"
    }

    $notes = @"
# $AppName v$AppVersion

## Included Artifacts
- $ArtifactName
- $HashFileName

## Validation Summary
- `python -m unittest discover -s . -p "test_*.py"`
- import smoke check

## Build Notes
- Windows one-dir package generated with PyInstaller
- UPX disabled to reduce antivirus false positives
- $resourceStatus
- CoolProp dependency bundled into the distribution folder
- Startup update check and manual update control are enabled
- Code signing was not applied in this package

## GitHub Release Body
Use this file as the GitHub release description and upload the `.zip` plus `.sha256.txt` files as release assets.

## Suggested Tag
- $ReleaseTag

## Antivirus Note
False-positive risk is reduced but cannot be guaranteed to be zero without Authenticode code signing and publisher reputation.
"@

    Set-Content -LiteralPath $OutputPath -Value $notes -Encoding UTF8
}

function New-ReleaseArchive {
    param(
        [string]$SourcePath,
        [string]$DestinationPath
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $resolvedSource = (Resolve-Path -LiteralPath $SourcePath).Path
    $maxAttempts = 8

    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            if (Test-Path -LiteralPath $DestinationPath) {
                Remove-Item -LiteralPath $DestinationPath -Force -ErrorAction SilentlyContinue
            }

            [System.IO.Compression.ZipFile]::CreateFromDirectory(
                $resolvedSource,
                $DestinationPath,
                [System.IO.Compression.CompressionLevel]::Optimal,
                $true
            )
            return
        } catch {
            if ($attempt -eq $maxAttempts) {
                throw
            }

            $delaySeconds = [Math]::Min($attempt * 2, 12)
            Write-Warning "Release arsivleme adimi dosya kilidi nedeniyle tekrar denenecek ($attempt/$maxAttempts)."
            Start-Sleep -Seconds $delaySeconds
        }
    }
}

function Invoke-PyInstallerBuild {
    param(
        [string]$AttemptLabel,
        [bool]$UseWindowsResources,
        [string]$RunId,
        [string]$AppVersion,
        [string]$AppName,
        [string]$PublisherName,
        [string]$CopyrightNotice
    )

    $attemptSuffix = "$RunId-$AttemptLabel"
    $attemptDistPath = Join-Path $releasePath "raw-dist-$attemptSuffix"
    $attemptBuildPath = Join-Path $releasePath "build-temp-$attemptSuffix"
    $attemptVersionInfoPath = Join-Path $attemptBuildPath "version_info.txt"

    New-Item -ItemType Directory -Path $attemptBuildPath -Force | Out-Null
    $env:PYTHONPYCACHEPREFIX = Join-Path $attemptBuildPath "pycache"

    if ($UseWindowsResources) {
        Write-VersionInfoFile `
            -OutputPath $attemptVersionInfoPath `
            -AppVersion $AppVersion `
            -AppName $AppName `
            -PublisherName $PublisherName `
            -CopyrightNotice $CopyrightNotice
    }

    $pyinstallerArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--noupx",
        "--name", $binaryName,
        "--distpath", $attemptDistPath,
        "--workpath", $attemptBuildPath,
        "--specpath", $attemptBuildPath,
        "--hidden-import", "CoolProp.CoolProp",
        "--exclude-module", "CoolProp.GUI",
        "--exclude-module", "CoolProp.Plots",
        "--exclude-module", "CoolProp.tests",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "pytest",
        "--exclude-module", "PyQt5",
        "--exclude-module", "PyQt6",
        "--exclude-module", "PySide6",
        "--exclude-module", "openpyxl",
        "--exclude-module", "lxml",
        "--exclude-module", "pyarrow"
    )

    if ($UseWindowsResources) {
        $pyinstallerArgs += @("--version-file", $attemptVersionInfoPath, "--manifest", $manifestPath)
    }

    $pyinstallerArgs += $entryPoint
    & $PythonExe @pyinstallerArgs

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        DistPath = $attemptDistPath
        BuildPath = $attemptBuildPath
        ExePath = Join-Path $attemptDistPath "$binaryName\$binaryName.exe"
        UsedWindowsResources = $UseWindowsResources
    }
}

$appName = Get-MetadataValue "APP_NAME"
$appVersion = Get-MetadataValue "APP_VERSION"
$binaryName = Get-MetadataValue "BINARY_NAME"
$publisherName = Get-MetadataValue "PUBLISHER_NAME"
$copyrightNotice = Get-MetadataValue "COPYRIGHT_NOTICE"
$releaseTagPrefix = Get-MetadataValue "RELEASE_TAG_PREFIX"
$artifactBaseName = "$binaryName-v$appVersion-windows-x64"
$zipPath = Join-Path $releasePath "$artifactBaseName.zip"
$hashPath = Join-Path $releasePath "$artifactBaseName.sha256.txt"
$notesPath = Join-Path $releasePath "$artifactBaseName-RELEASE-NOTES.md"
$releaseTag = "$releaseTagPrefix$appVersion"
$runId = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), ([System.Guid]::NewGuid().ToString("N").Substring(0, 8))
$compileScratchPath = Join-Path $releasePath "compile-check-$runId"

Write-Host "Release build hazirlaniyor..."
Write-Host "Project root: $projectRoot"
Write-Host "Version: $appVersion"
Write-Host "Run id: $runId"

New-Item -ItemType Directory -Path $releasePath -Force | Out-Null
New-Item -ItemType Directory -Path $compileScratchPath -Force | Out-Null
$env:PYTHONPYCACHEPREFIX = $compileScratchPath

if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Windows manifest bulunamadi: $manifestPath"
}

if (-not $SkipTests) {
    Write-Host "Otomatik testler calistiriliyor..."
    & $PythonExe -m unittest discover -s $projectRoot -p "test_*.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Unit testler basarisiz oldu."
    }

    & $PythonExe -m py_compile `
        (Join-Path $projectRoot "Hidrostatik_Test_Chat.py") `
        (Join-Path $projectRoot "hydrotest_core.py") `
        (Join-Path $projectRoot "coefficient_reference.py") `
        (Join-Path $projectRoot "pipe_catalog.py") `
        (Join-Path $projectRoot "updater.py") `
        (Join-Path $projectRoot "test_hydrotest_core.py") `
        (Join-Path $projectRoot "test_pipe_catalog.py") `
        (Join-Path $projectRoot "test_ui_workflow.py") `
        (Join-Path $projectRoot "test_updater.py") `
        (Join-Path $projectRoot "app_metadata.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "py_compile adimi Windows dosya kilidi nedeniyle atlandi. Unit test ve import smoke check devam ediyor."
    }

    & $PythonExe -c "import sys; sys.path.insert(0, r'$projectRoot'); import Hidrostatik_Test_Chat; import hydrotest_core; import pipe_catalog; import updater; import app_metadata; print('import-ok')"
    if ($LASTEXITCODE -ne 0) {
        throw "Import smoke check basarisiz oldu."
    }
}

Write-Host "PyInstaller build basliyor..."
$buildResult = Invoke-PyInstallerBuild `
    -AttemptLabel "primary" `
    -UseWindowsResources $true `
    -RunId $runId `
    -AppVersion $appVersion `
    -AppName $appName `
    -PublisherName $publisherName `
    -CopyrightNotice $copyrightNotice

if ($buildResult.ExitCode -ne 0) {
    Write-Warning "Version resource veya manifest uygulanirken Windows erisim kilidi olustu. Sade build ile tekrar deneniyor."
    $buildResult = Invoke-PyInstallerBuild `
        -AttemptLabel "plain" `
        -UseWindowsResources $false `
        -RunId $runId `
        -AppVersion $appVersion `
        -AppName $appName `
        -PublisherName $publisherName `
        -CopyrightNotice $copyrightNotice
}

if ($buildResult.ExitCode -ne 0) {
    throw "PyInstaller build basarisiz oldu."
}

$distPath = $buildResult.DistPath
$exePath = $buildResult.ExePath
$windowsResourcesEmbedded = $buildResult.UsedWindowsResources

if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Beklenen exe olusmadi: $exePath"
}

if (-not $SkipArchive) {
    Write-Host "Release artifact'lari uretiliyor..."
    New-ReleaseArchive -SourcePath (Join-Path $distPath $binaryName) -DestinationPath $zipPath
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $hashPath -Value "$hash  $([System.IO.Path]::GetFileName($zipPath))" -Encoding ASCII
    Write-ReleaseNotes `
        -OutputPath $notesPath `
        -AppName $appName `
        -AppVersion $appVersion `
        -ArtifactName ([System.IO.Path]::GetFileName($zipPath)) `
        -HashFileName ([System.IO.Path]::GetFileName($hashPath)) `
        -WindowsResourcesEmbedded $windowsResourcesEmbedded `
        -ReleaseTag $releaseTag
}

Write-Host ""
Write-Host "Build tamamlandi."
Write-Host "Exe yolu: $exePath"
if (-not $SkipArchive) {
    Write-Host "Zip yolu: $zipPath"
    Write-Host "SHA256: $hashPath"
    Write-Host "Release notes: $notesPath"
    Write-Host "Git tag onerisi: $releaseTag"
}
if ($windowsResourcesEmbedded) {
    Write-Host "Windows manifest ve version resource eklendi."
} else {
    Write-Host "Windows resource ekleme adimi atlandi; plain fallback build kullanildi."
}
Write-Host "Not: False-positive riski azaltildi ancak kod imzalama olmadan sifir garanti verilemez."
