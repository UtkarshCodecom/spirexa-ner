@echo off
echo Stopping SPIREXA...
taskkill /F /FI "WINDOWTITLE eq spirexa_server*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq spirexa_bridge*" >nul 2>&1
echo Done.
