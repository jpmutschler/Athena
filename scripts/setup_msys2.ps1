#Requires -Version 5.1
<#
.SYNOPSIS
    Install MSYS2 and MinGW64 toolchain for building the Switchtec C library.

.DESCRIPTION
    Downloads and installs MSYS2 (if not present), then installs the MinGW64
    GCC toolchain and build tools. Idempotent -- skips steps already completed.

.PARAMETER InstallDir
    MSYS2 installation directory. Defaults to C:\msys64.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\msys64"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "[setup_msys2] $msg" -ForegroundColor Cyan }

# --- Check if MSYS2 is already installed ---

$msys2Bash = Join-Path $InstallDir "usr\bin\bash.exe"
$mingwGcc = Join-Path $InstallDir "mingw64\bin\gcc.exe"

if (Test-Path $msys2Bash) {
    Write-Step "MSYS2 already installed at $InstallDir"
} else {
    Write-Step "Downloading MSYS2 installer..."
    $installerUrl = "https://github.com/msys2/msys2-installer/releases/download/2024-01-13/msys2-x86_64-20240113.exe"
    $installerPath = Join-Path $env:TEMP "msys2-installer.exe"

    if (-not (Test-Path $installerPath)) {
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    }

    Write-Step "Installing MSYS2 to $InstallDir (silent)..."
    $args = @("install", "--root", $InstallDir, "--confirm-command")
    Start-Process -FilePath $installerPath -ArgumentList $args -Wait -NoNewWindow

    if (-not (Test-Path $msys2Bash)) {
        throw "MSYS2 installation failed -- $msys2Bash not found."
    }
    Write-Step "MSYS2 installed successfully."
}

# --- Install MinGW64 toolchain ---

if (Test-Path $mingwGcc) {
    Write-Step "MinGW64 GCC already installed."
} else {
    Write-Step "Installing MinGW64 toolchain..."
    & $msys2Bash -lc "pacman -Syu --noconfirm"
    & $msys2Bash -lc "pacman -S --noconfirm --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-make autotools make"

    if (-not (Test-Path $mingwGcc)) {
        throw "MinGW64 GCC installation failed."
    }
    Write-Step "MinGW64 toolchain installed."
}

# --- Add to session PATH ---

$mingwBin = Join-Path $InstallDir "mingw64\bin"
if ($env:PATH -notlike "*$mingwBin*") {
    $env:PATH = "$mingwBin;$env:PATH"
    Write-Step "Added $mingwBin to session PATH."
} else {
    Write-Step "$mingwBin already in PATH."
}

Write-Step "MSYS2 setup complete. MinGW GCC:"
& $mingwGcc --version | Select-Object -First 1
