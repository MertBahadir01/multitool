@echo off
title MultiTool Studio Builder

echo ===============================
echo Building MultiTool Studio
echo ===============================

python -m pip install --upgrade pip
python -m pip install pyinstaller

echo.
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Running PyInstaller...
pyinstaller build.spec --clean --noconfirm

echo.
echo ===============================
echo Build Complete
echo Executable located in:
echo dist\MultiToolStudio\
echo ===============================

pause