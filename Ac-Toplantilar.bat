@echo off
setlocal

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$pids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { $pids | ForEach-Object { Stop-Process -Id $_ -Force } }; Start-Process python -ArgumentList 'run.py' -WorkingDirectory '%cd%' -WindowStyle Hidden; Start-Sleep -Seconds 4; & 'C:\Program Files\Google\Chrome\Application\chrome.exe' 'http://127.0.0.1:8000/meetings'"

endlocal
