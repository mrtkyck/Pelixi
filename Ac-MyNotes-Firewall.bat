@echo off
setlocal

netsh advfirewall firewall add rule name="MyNotes 8000" dir=in action=allow protocol=TCP localport=8000

echo.
echo MyNotes icin 8000 portu guvenlik duvarinda izinli hale getirildi.
echo.
pause

endlocal
