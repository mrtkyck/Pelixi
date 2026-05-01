@echo off
setlocal

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "URL=http://127.0.0.1:8000/login"
set "DATA_ROOT=%LOCALAPPDATA%\MyNotes"

if exist "C:\Program Files\Python313\python.exe" (
  set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
) else (
  set "PYTHON_EXE=python"
)

cd /d "%APP_ROOT%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = '%URL%';" ^
  "$appRoot = '%APP_ROOT%';" ^
  "$env:MYNOTES_APP_DIR = '%DATA_ROOT%';" ^
  "try { $running = (Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2).StatusCode -ge 200 } catch { $running = $false };" ^
  "if (-not $running) { Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList 'run.py' -WorkingDirectory $appRoot -WindowStyle Minimized; Start-Sleep -Seconds 3 };" ^
  "if (Test-Path 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe') { Start-Process -FilePath 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' -ArgumentList $url }" ^
  "elseif (Test-Path 'C:\Program Files\Microsoft\Edge\Application\msedge.exe') { Start-Process -FilePath 'C:\Program Files\Microsoft\Edge\Application\msedge.exe' -ArgumentList $url }" ^
  "else { Start-Process -FilePath $url }"

endlocal
