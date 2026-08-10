@echo off
cd /d "%~dp0.."

:: Version aus version.py lesen
for /f "tokens=*" %%l in ('findstr "APP_VERSION" core\version.py') do set VLINE=%%l
for /f "tokens=2 delims=^" %%v in ("%VLINE:APP_VERSION = =%") do set VERSION=%%~v
set VERSION=%VERSION:"=%

echo ============================================
echo  Release wird erstellt fuer v%VERSION%
echo ============================================
echo.

:: Build
echo [1/4] PyInstaller Build...
call .venv\Scripts\activate.bat
pyinstaller "Aion2 TM.spec" --clean --noconfirm
if errorlevel 1 (
    echo FEHLER: Build fehlgeschlagen!
    pause & exit /b 1
)

:: ZIP erstellen
set ZIP_NAME=Aion2_TM_v%VERSION%.zip
echo [2/4] ZIP erstellen: %ZIP_NAME%...
if exist "%ZIP_NAME%" del "%ZIP_NAME%"
powershell -Command "Compress-Archive -Path 'dist\Aion2 TM' -DestinationPath '%ZIP_NAME%' -Force"
if errorlevel 1 (
    echo FEHLER: ZIP-Erstellung fehlgeschlagen!
    pause & exit /b 1
)

:: GitHub Release erstellen und ZIP hochladen
echo [3/4] GitHub Release erstellen...
gh release create "v%VERSION%" "%ZIP_NAME%" --title "v%VERSION%" --notes-file ..\CHANGELOG.md
if errorlevel 1 (
    echo FEHLER: GitHub Release fehlgeschlagen! Bitte manuell hochladen: %ZIP_NAME%
    pause & exit /b 1
)

:: Aufraeumen
echo [4/4] Temporaere Dateien loeschen...
del "%ZIP_NAME%"

echo.
echo ============================================
echo  Release v%VERSION% erfolgreich veroeffentlicht!
echo ============================================
pause
