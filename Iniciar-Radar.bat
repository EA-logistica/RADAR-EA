@echo off
title Radar de Importaciones
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-tailscale.ps1"
if errorlevel 1 pause
