@echo off
REM Builds a standalone Windows .exe from dna_injector.pyw using PyInstaller.
REM Requires Python 3 with pip. Run this file by double-clicking it.

echo Installing/updating PyInstaller...
py -m pip install --upgrade pyinstaller || (echo pip/PyInstaller failed & pause & exit /b 1)

echo Building EXE...
py -m PyInstaller --onefile --windowed --name "DNA Injector" dna_injector.pyw || (echo Build failed & pause & exit /b 1)

echo.
echo Done. Your EXE is at:  dist\DNA Injector.exe
pause
