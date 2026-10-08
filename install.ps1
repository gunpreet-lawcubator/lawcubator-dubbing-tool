param(
    [string]$OpenRouterKey,
    [string]$ElevenLabsKey,
    [string]$PasswordHash
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Repo = "gunpreet-lawcubator/lawcubator-dubbing-tool"
$InstallDir = Join-Path $env:USERPROFILE "LawcubatorDubbing"

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Find-Python {
    foreach ($candidate in @(@("python"), @("py", "-3"))) {
        try {
            $exe = $candidate[0]
            $extra = @($candidate | Select-Object -Skip 1)
            $out = & $exe @extra --version 2>&1 | Out-String
            if ($out -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 10) { return ,$candidate }
        } catch { }
    }
    return $null
}

function Install-WithWinget([string]$id, [string]$label) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$label is missing and 'winget' isn't available to install it. Install $label manually, then run this command again."
    }
    Write-Host "Installing $label..."
    winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Refresh-Path
}

try {
    if (-not $OpenRouterKey -or -not $ElevenLabsKey -or -not $PasswordHash) {
        throw "This install command is incomplete. Ask Gunpreet for your personal install command."
    }

    $py = Find-Python
    if (-not $py) { Install-WithWinget "Python.Python.3.12" "Python"; $py = Find-Python }
    if (-not $py) { throw "Python was installed but isn't visible yet. Close this window, open a new one, and run the same command again." }

    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Install-WithWinget "Gyan.FFmpeg" "ffmpeg"
        if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            throw "ffmpeg was installed but isn't visible yet. Close this window, open a new one, and run the same command again."
        }
    }

    if (Test-Path (Join-Path $InstallDir "VERSION")) {
        Write-Host "Already installed at $InstallDir - starting it."
    } else {
        Write-Host "Downloading the latest version..."
        $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ "User-Agent" = "lawcubator-installer" }
        $asset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
        if (-not $asset) { throw "No release found yet. Tell Gunpreet." }
        $zip = Join-Path $env:TEMP "lawcubator-install.zip"
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
        New-Item -ItemType Directory -Force $InstallDir | Out-Null
        Expand-Archive $zip -DestinationPath $InstallDir -Force
        Remove-Item $zip

        # No BOM: python-dotenv would glue a BOM onto the first key name.
        $envText = "OPENROUTER_API_KEY=$OpenRouterKey`nELEVENLABS_API_KEY=$ElevenLabsKey`nAPP_PASSWORD_HASH=$PasswordHash`n"
        [IO.File]::WriteAllText((Join-Path $InstallDir "backend\.env"), $envText, (New-Object Text.UTF8Encoding $false))

        Write-Host "Setting up..."
        Push-Location (Join-Path $InstallDir "backend")
        $exe = $py[0]; $extra = @($py | Select-Object -Skip 1)
        & $exe @extra -m venv venv
        if ($LASTEXITCODE -ne 0) { throw "Couldn't create the Python environment." }
        Pop-Location
    }

    $shortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Lawcubator Dubbing.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $InstallDir "run.bat"
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Save()

    Write-Host ""
    Write-Host "Done. A 'Lawcubator Dubbing' icon is now on your desktop."
    Write-Host "Opening the app now - the first start installs a few packages and takes a few minutes."
    Start-Process -FilePath (Join-Path $InstallDir "run.bat") -WorkingDirectory $InstallDir
} catch {
    Write-Host ""
    Write-Host "Something went wrong: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
