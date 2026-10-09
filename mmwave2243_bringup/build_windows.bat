@echo off
setlocal enabledelayedexpansion
REM ============================================================================
REM build_windows.bat - one-step setup on Windows, counterpart of build_ubuntu.sh
REM
REM   Does: install MSVC Build Tools if missing, install the Python build
REM   dependencies, build and install fpga_udp, run a self-check. The final
REM   message explains the SOP jumpers, the NIC settings and how to start.
REM
REM   Usage:  build_windows.bat [full path to python.exe]
REM           Without an argument it lists the Python and conda environments
REM           found on this machine and asks which one to install into.
REM           Installing the compiler shows a UAC prompt, first time only,
REM           about 2 GB and 10-20 minutes.
REM
REM   Unlike on Ubuntu no FTDI library has to be installed: the Windows .lib
REM   ships in fpga_udp/src/FTDI_D2XX/Windows/ and setup.py picks it by
REM   platform. The FTDI driver is already present on any machine that has
REM   run mmWave Studio.
REM
REM   Keep this file plain ASCII. cmd misparses batch files that contain
REM   non-ASCII text saved as UTF-8.
REM ============================================================================

set "PYTHON=%~1"
if defined PYTHON goto havepy
REM No argument: scan for Python installations, conda environments and PATH, then let the user choose.
echo.
echo ==== Scanning for Python environments ====
set "PYLIST=%TEMP%\awr2243_pylist.txt"
powershell -NoProfile -Command "$c=@(); if($env:CONDA_PREFIX){$c+=Join-Path $env:CONDA_PREFIX 'python.exe'}; $roots=@((Join-Path $env:USERPROFILE 'anaconda3'),(Join-Path $env:USERPROFILE 'miniconda3'),'C:\ProgramData\Anaconda3','C:\ProgramData\Miniconda3'); foreach($r in $roots){ if(Test-Path $r){ $c+=Join-Path $r 'python.exe'; $c+=(Get-ChildItem (Join-Path $r 'envs') -Directory -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName 'python.exe' }) } }; $t=Join-Path $env:USERPROFILE '.conda\environments.txt'; if(Test-Path $t){Get-Content $t | ForEach-Object {$c+=Join-Path $_.Trim() 'python.exe'}}; $c+=(Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object Source); $c=$c | Where-Object {$_ -and $_ -notmatch 'WindowsApps' -and (Test-Path $_)} | Select-Object -Unique; $o=@(); foreach($x in $c){$v=(& $x -V 2>&1) -join ''; $o+=($x+'|'+$v)}; $o | Set-Content -Encoding Default (Join-Path $env:TEMP 'awr2243_pylist.txt')"
set n=0
set "DEF=1"
if exist "%PYLIST%" for /f "usebackq tokens=1,2 delims=|" %%A in ("%PYLIST%") do (
    set /a n+=1
    set "PYOPT_!n!=%%A"
    if /i "%%A"=="%CONDA_PREFIX%\python.exe" set "DEF=!n!"
    echo   [!n!] %%B    %%A
)
if "!n!"=="0" (
    echo [FATAL] No Python found. Activate your conda environment first and retry,
    echo         or pass it explicitly: build_windows.bat C:\path\to\python.exe
    exit /b 1
)
set "choice=!DEF!"
set /p "choice=Install into which environment? Enter a number, or press Enter for !DEF! which is the active environment: "
for %%C in (!choice!) do set "PYTHON=!PYOPT_%%C!"
if not defined PYTHON (
    echo [FATAL] Invalid choice: !choice!
    exit /b 1
)
:havepy
set "HERE=%~dp0"

if not exist "%PYTHON%" (
    echo [FATAL] python not found: %PYTHON%
    echo         Usage: build_windows.bat [full path to python.exe]
    exit /b 1
)
echo ============================================================
echo   AWR2243 one-step setup ^(Windows^)   python = %PYTHON%
echo ============================================================

REM ---- 1. MSVC Build Tools, the compiler for the pybind11 extension ----
echo.
echo ==== [1/4] Checking MSVC Build Tools ====
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "HAVE_MSVC="
if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -latest -property installationPath 2^>nul`) do set "HAVE_MSVC=%%i"
)
if defined HAVE_MSVC (
    echo Found: !HAVE_MSVC!
    goto pydeps
)

echo Not found. Installing now, about 2 GB and 10-20 minutes, a UAC prompt will appear...
where winget >nul 2>nul
if %errorlevel%==0 (
    winget install --id Microsoft.VisualStudio.2022.BuildTools -e ^
        --override "--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" ^
        --accept-package-agreements --accept-source-agreements
) else (
    REM No winget on older Windows 10: download the official bootstrapper
    echo winget is not available, using the official installer...
    curl -L -o "%TEMP%\vs_BuildTools.exe" https://aka.ms/vs/17/release/vs_BuildTools.exe || goto fail
    "%TEMP%\vs_BuildTools.exe" --passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended
)
REM Check again: the exit codes of winget and the installer are unreliable, trust vswhere
set "HAVE_MSVC="
if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -latest -property installationPath 2^>nul`) do set "HAVE_MSVC=%%i"
)
if not defined HAVE_MSVC (
    echo [FATAL] Build Tools installation failed or was cancelled.
    echo         Install manually: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo         Select "Desktop development with C++", then run this script again.
    exit /b 1
)
echo Installed: !HAVE_MSVC!

REM ---- 1.5 VC runtime shipped inside the conda environment ----
REM Symptom: pip builds fine, but importing the extension crashes with an access
REM violation and no error message.
REM Cause: the conda environment carries its own vcruntime140 and msvcp140, for example
REM 14.29 from the VS2019 era, and Python loads those first. An extension built with
REM VS2022 crashes against the old runtime. Fix: overwrite them with the system version.
echo.
echo ==== [1.5/4] Checking the VC runtime of the conda environment ====
for %%D in ("%PYTHON%") do set "ENVDIR=%%~dpD"
powershell -NoProfile -Command "$e='%ENVDIR%'.TrimEnd('\'); $sys=(Get-Item 'C:\Windows\System32\vcruntime140.dll').VersionInfo.FileVersionRaw; $fixed=$false; foreach($d in @($e,(Join-Path $e 'Library\bin'))){ foreach($n in 'vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll'){ $f=Join-Path $d $n; if(Test-Path $f){ if((Get-Item $f).VersionInfo.FileVersionRaw -lt $sys){ Copy-Item $f ($f+'.bak') -Force; Copy-Item (Join-Path 'C:\Windows\System32' $n) $f -Force; $fixed=$true } } } }; if($fixed){'  Old VC runtime DLLs in the environment were replaced with the system version (originals saved as .bak)'}else{'  VC runtime version OK'}"

:pydeps
REM ---- 2. Python build dependencies ----
echo.
echo ==== [2/4] Python dependencies (pybind11 / numpy) ====
"%PYTHON%" -m pip install --upgrade pip pybind11 numpy || goto fail

REM ---- 3. Build and install fpga_udp ----
echo.
echo ==== [3/4] Building and installing fpga_udp (1-3 minutes the first time) ====
"%PYTHON%" -m pip install "%HERE%fpga_udp" || goto fail

REM ---- 4. Self-check, the same three checks as build_ubuntu.sh, no radar needed ----
echo.
echo ==== [4/4] Self-check ====
pushd "%HERE%"
"%PYTHON%" -c "import fpga_udp; assert fpga_udp.add(1,2)==3; assert hasattr(fpga_udp,'AWR2243_init'), 'fpga_udp has no AWR2243_init'; print('  fpga_udp.add(1,2) =', fpga_udp.add(1,2), ' (3 means the extension works)'); print('  AWR2243_init available: True'); from mmwave.dataloader import DCA1000; print('  DCA1000 import: OK')" || (popd & goto fail)
popd

echo.
echo ============================================================
echo   [OK] Installation complete. After connecting the hardware:
echo.
echo   ** Step 0 (most important: hardware jumpers) **
echo      Set the SOP jumpers on the AWR2243BOOST to functional mode, SOP4 = binary 001:
echo         P3(SOP2)=open   P2(SOP1)=open (remove the middle jumper)   P4(SOP0)=closed
echo      Otherwise the radar does not answer on SPI and init returns -8.
echo      (mmWave Studio uses the Dev mode, which does not work with this code;
echo       set the jumpers back if you return to Studio)
echo.
echo   1) Network: give the NIC connected to the DCA1000 the static IP 192.168.33.30, mask 255.255.255.0
echo      (Settings / Network / Ethernet / Edit IP, or in an administrator PowerShell:
echo       New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.33.30 -PrefixLength 24)
echo      Do not test the link with ping, the DCA1000 does not answer ICMP. In PowerShell use:
echo       Get-NetNeighbor -IPAddress 192.168.33.180   a MAC address means the link is OK
echo.
echo   2) Start the radar (continuous transmission, no administrator rights needed):
echo         %PYTHON% start_awr2243.py
echo.
echo   3) In another terminal run capture.py or capture_plot.py.
echo      Data captured through this launcher needs CAPTURE_SOURCE = 'launcher' in config.py;
echo      with 'studio' the frames decode into mirror images or noise.
echo ============================================================
exit /b 0

:fail
echo.
echo [FATAL] The previous step failed, see the output above.
exit /b 1
