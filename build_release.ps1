Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $projectRoot "dist"
$buildDir = Join-Path $projectRoot "build"
$specPath = Join-Path $projectRoot "Natural Gas Prop.spec"
$finalExe = Join-Path $projectRoot "Natural Gas Prop.exe"

if (Test-Path -LiteralPath $finalExe) {
    Remove-Item -LiteralPath $finalExe -Force
}

pyinstaller --noconfirm --clean $specPath

$builtExe = Join-Path $distDir "Natural Gas Prop.exe"
if (-not (Test-Path -LiteralPath $builtExe)) {
    throw "PyInstaller çıktısı bulunamadı: $builtExe"
}

Copy-Item -LiteralPath $builtExe -Destination $finalExe -Force
Write-Output "Build hazır: $finalExe"
