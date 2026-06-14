<#
.SYNOPSIS
    Builds a complete, self-contained release package for GenshinLyrePlayer.

.DESCRIPTION
    Produces three executables with no external runtime dependencies:
      GenshinLyrePlayer.exe  --  self-contained WPF app (.NET runtime bundled)
      genshin-parse.exe          --  video -> token-sheet converter (Python + OpenCV)
      genshin-play.exe           --  token-sheet -> keystrokes player (Python)

    Output:
      release\                                    folder ready to upload as-is
      GenshinLyrePlayer-v<ver>-win-x64.zip    ready for GitHub Releases

.REQUIREMENTS
    - Python 3.10+ on PATH   (pip install pyinstaller is handled automatically)
    - .NET SDK 6+            on PATH

.EXAMPLE
    .\build_release.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

# Version -- keep in sync with csproj + pyproject.toml
$Version = "1.0.0"

# Paths
$OutDir   = Join-Path $Root "release"
$BuildDir = Join-Path $Root "build\pyinstaller"
$ZipPath  = Join-Path $Root "GenshinLyrePlayer-v$Version-win-x64.zip"
$CsProj   = "GenshinLyrePlayer\GenshinLyrePlayer.WPF\GenshinLyrePlayer.WPF.csproj"

function Step([string]$msg) {
    Write-Host ""
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host ("  " + ("-" * $msg.Length)) -ForegroundColor DarkGray
}

# --- 0. Preflight -----------------------------------------------------------
Step "Preflight"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python not found on PATH" }
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw "dotnet not found on PATH"  }

python -m pip show pyinstaller 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }
}

Write-Host "  Python     : $(python --version)"
Write-Host "  PyInstaller: $(python -m PyInstaller --version)"
Write-Host "  dotnet     : $(dotnet --version)"

# --- 1. Clean ---------------------------------------------------------------
Step "Clean"

foreach ($p in @($OutDir, $BuildDir)) {
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

New-Item $OutDir   -ItemType Directory | Out-Null
New-Item $BuildDir -ItemType Directory | Out-Null

# --- 2. genshin-parse.exe ---------------------------------------------------
Step "genshin-parse.exe  (PyInstaller + OpenCV, ~60 MB)"

# Source paths must be absolute so PyInstaller resolves them from the project
# root, not from --workpath.
python -m PyInstaller `
    --onefile `
    --name genshin-parse `
    --collect-all cv2 `
    "--add-data=$Root\config\roi_profiles;config\roi_profiles" `
    --distpath $OutDir `
    --workpath "$BuildDir\genshin-parse" `
    --noconfirm `
    vision_parser\parser_pipeline.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for genshin-parse" }

# --- 3. genshin-play.exe ----------------------------------------------------
Step "genshin-play.exe  (PyInstaller, ~8 MB)"

python -m PyInstaller `
    --onefile `
    --name genshin-play `
    "--add-data=$Root\config\key_mappings;config\key_mappings" `
    --distpath $OutDir `
    --workpath "$BuildDir\genshin-play" `
    --noconfirm `
    player_engine\player_pipeline.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for genshin-play" }

# --- 4. GenshinLyrePlayer.exe -------------------------------------------
Step "GenshinLyrePlayer.exe  (dotnet publish, self-contained, ~230 MB)"

dotnet publish $CsProj `
    --configuration Release `
    --runtime win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:PublishReadyToRun=true `
    -p:DebugType=none `
    -p:DebugSymbols=false `
    --output $OutDir `
    --nologo

if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed" }

# --- 5. Strip non-exe publish artefacts -------------------------------------
Step "Strip"

Get-ChildItem $OutDir -File | Where-Object Extension -ne ".exe" | ForEach-Object {
    Write-Host "  Removing $($_.Name)"
    Remove-Item $_.FullName -Force
}

# Remove generated .spec files from repo root (build artefacts)
Get-ChildItem $Root -Filter "*.spec" -File | Remove-Item -Force

# --- 6. Zip -----------------------------------------------------------------
Step "Zip"

Compress-Archive -Path "$OutDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal
Write-Host "  Created: $ZipPath"

# --- 7. Summary -------------------------------------------------------------
Write-Host ""
Write-Host "  Release v$Version ready!" -ForegroundColor Green
Write-Host ""
Write-Host "  $OutDir" -ForegroundColor DarkGray
Get-ChildItem $OutDir -File | Sort-Object Name | ForEach-Object {
    $size = if ($_.Length -ge 1MB) { "{0:N0} MB" -f ($_.Length / 1MB) }
            else                    { "{0:N0} KB" -f ($_.Length / 1KB) }
    Write-Host ("    {0,-40} {1,8}" -f $_.Name, $size)
}
$zipMb = "{0:N0} MB" -f ((Get-Item $ZipPath).Length / 1MB)
Write-Host ""
Write-Host ("  {0,-44} {1,8}  <- upload to GitHub Releases" -f (Split-Path $ZipPath -Leaf), $zipMb)
Write-Host ""
