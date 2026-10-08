$ErrorActionPreference = "Stop"
$AppPort = 8000
$RestartExitCode = 42   # the app exits with this after installing an update

function Wait-Exit([int]$code) {
    Read-Host "Press Enter to exit"
    exit $code
}

function Test-PortOpen {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $AppPort)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Test-AppRunning {
    try {
        $res = Invoke-WebRequest -Uri "http://localhost:$AppPort/api/auth-status" -UseBasicParsing -TimeoutSec 2
        return $res.StatusCode -eq 200
    } catch {
        return $false
    }
}

Set-Location (Join-Path $PSScriptRoot "..\backend")
$venvPython = ".\venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "This copy isn't installed properly. Ask Gunpreet for the install command and run it again."
    Wait-Exit 1
}

# Double-clicking the shortcut while the app is already running, or after a
# window was closed without stopping the server, should just open the app.
if (Test-AppRunning) {
    Write-Host "The app is already running - opening it in your browser."
    Start-Process "http://localhost:$AppPort"
    Wait-Exit 0
}

if (Test-PortOpen) {
    Write-Host "Port $AppPort is already being used by something else on this computer."
    Write-Host "Close whatever that is, then run this again."
    Wait-Exit 1
}

$env:LAWCUBATOR_MANAGED = "1"   # tells the app it's an installed copy that may self-update
$firstStart = $true

while ($true) {
    # (Re)install packages only when requirements.txt changed (first run, or after an update).
    $reqHash = (Get-FileHash "requirements.txt" -Algorithm SHA256).Hash
    $marker = ".\venv\.reqhash"
    if (-not (Test-Path $marker) -or ((Get-Content $marker -Raw).Trim() -ne $reqHash)) {
        Write-Host "Installing required packages (this can take a few minutes the first time)..."
        & $venvPython -m pip install -q -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Package install failed. Check your internet connection and run this again."
            Wait-Exit 1
        }
        Set-Content -Path $marker -Value $reqHash
    }

    Write-Host "Starting the app..."
    try {
        $proc = Start-Process -FilePath $venvPython -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$AppPort", "--no-access-log" -NoNewWindow -PassThru
    } catch {
        Write-Host "Couldn't start the app."
        Write-Host $_.Exception.Message
        Wait-Exit 1
    }

    # Open the browser only once the server really answers; skip on update restarts
    # (the open page reloads itself).
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        if ($proc.HasExited) { break }
        if (Test-PortOpen) { $ready = $true; break }
    }
    if ($ready -and $firstStart) { Start-Process "http://localhost:$AppPort" }
    $firstStart = $false

    $proc.WaitForExit()
    if ($proc.ExitCode -ne $RestartExitCode) { break }
    Write-Host "Update installed - restarting..."
}

Wait-Exit $proc.ExitCode
