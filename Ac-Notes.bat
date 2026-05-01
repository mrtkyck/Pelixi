@echo off
setlocal

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$listenPids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($listenPids) { $listenPids | ForEach-Object { Stop-Process -Id $_ -Force } }; $pythonPids = Get-Process python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id; if ($pythonPids) { $pythonPids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }; Start-Process powershell -ArgumentList '-NoExit','-Command','Set-Location ''%cd%''; python run.py' -WorkingDirectory '%cd%'"
timeout /t 3 /nobreak >nul
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
  start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" "http://127.0.0.1:8000/login"
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
  start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" "http://127.0.0.1:8000/login"
) else (
  start "" "http://127.0.0.1:8000/login"
)

endlocal
