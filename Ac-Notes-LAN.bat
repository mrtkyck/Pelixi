@echo off
setlocal

cd /d "%~dp0"

set "MYNOTES_HOST=0.0.0.0"
set "MYNOTES_PORT=8000"
set "MYNOTES_LOCAL_URL=http://127.0.0.1:8000/"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; " ^
  "if ($pids) { $pids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }; " ^
  "$env:MYNOTES_HOST='0.0.0.0'; $env:MYNOTES_PORT='8000'; " ^
  "Start-Process python -ArgumentList 'run.py' -WorkingDirectory '%cd%' -WindowStyle Hidden; " ^
  "Start-Sleep -Seconds 4; " ^
  "& 'C:\Program Files\Google\Chrome\Application\chrome.exe' '%MYNOTES_LOCAL_URL%'"

echo.
echo MyNotes yerel ag modunda baslatildi.
echo Bu bilgisayarda acilacak adres: http://127.0.0.1:8000/
echo Diger bilgisayarlar icin adres: http://192.168.1.194:8000/
echo.
pause

endlocal
