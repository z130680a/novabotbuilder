@echo off
setlocal EnableExtensions

title Nova Bot Builder
cd /d "%~dp0"

set "URL=http://127.0.0.1:8000"

echo.
echo ==========================================
echo           Nova Bot Builder
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found.
    echo.
    pause
    exit /b 1
)

if not exist "app\web.py" (
    echo [ERROR] app\web.py not found.
    echo.
    pause
    exit /b 1
)

REM =================================================
REM Check server
REM =================================================

echo Checking server...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$x = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($x) { exit 0 } else { exit 1 }"

if not errorlevel 1 (
    echo Server is already running.
    goto CHOOSE_BROWSER
)

REM =================================================
REM Start FastAPI
REM =================================================

echo.
echo Starting Nova server...
echo.

start "Nova Bot Builder Server" cmd /k ^
"cd /d ""%~dp0"" && .venv\Scripts\python.exe -m uvicorn app.web:app --host 127.0.0.1 --port 8000"

REM =================================================
REM Wait only for TCP port
REM =================================================

echo Waiting for server...

set /a COUNT=0

:WAIT_SERVER

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$x = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($x) { exit 0 } else { exit 1 }"

if not errorlevel 1 (
    goto SERVER_READY
)

set /a COUNT+=1

if %COUNT% GEQ 30 (
    echo.
    echo [ERROR] Server did not start.
    echo.
    echo Check the Nova Server window.
    echo.
    pause
    exit /b 1
)

timeout /t 1 /nobreak >nul
goto WAIT_SERVER


:SERVER_READY

echo.
echo ==========================================
echo Server is running successfully.
echo ==========================================
echo.

REM =================================================
REM Browser Selection
REM =================================================

:CHOOSE_BROWSER

echo.
echo ==========================================
echo         Select your browser
echo ==========================================
echo.
echo 1. Google Chrome
echo 2. Microsoft Edge
echo 3. Mozilla Firefox
echo 4. Brave
echo 5. Opera
echo 6. Vivaldi
echo 7. Windows Default Browser
echo 8. Cancel
echo.
echo ------------------------------------------
echo.

choice /C 12345678 /N /M "Choose [1-8]: "

if errorlevel 8 goto EXIT_BROWSER
if errorlevel 7 goto OPEN_DEFAULT
if errorlevel 6 goto OPEN_VIVALDI
if errorlevel 5 goto OPEN_OPERA
if errorlevel 4 goto OPEN_BRAVE
if errorlevel 3 goto OPEN_FIREFOX
if errorlevel 2 goto OPEN_EDGE
if errorlevel 1 goto OPEN_CHROME

goto CHOOSE_BROWSER


REM =================================================
REM Chrome
REM =================================================

:OPEN_CHROME

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    start "" "%LocalAppData%\Google\Chrome\Application\chrome.exe" "%URL%"
    goto BROWSER_DONE
)

echo.
echo Chrome is not installed.
echo.
pause
goto CHOOSE_BROWSER


REM =================================================
REM Edge
REM =================================================

:OPEN_EDGE

if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%LocalAppData%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%LocalAppData%\Microsoft\Edge\Application\msedge.exe" "%URL%"
    goto BROWSER_DONE
)

echo.
echo Edge is not installed.
echo.
pause
goto CHOOSE_BROWSER


REM =================================================
REM Firefox
REM =================================================

:OPEN_FIREFOX

if exist "%ProgramFiles%\Mozilla Firefox\firefox.exe" (
    start "" "%ProgramFiles%\Mozilla Firefox\firefox.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe" (
    start "" "%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%LocalAppData%\Mozilla Firefox\firefox.exe" (
    start "" "%LocalAppData%\Mozilla Firefox\firefox.exe" "%URL%"
    goto BROWSER_DONE
)

echo.
echo Firefox is not installed.
echo.
pause
goto CHOOSE_BROWSER


REM =================================================
REM Brave
REM =================================================

:OPEN_BRAVE

if exist "%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe" (
    start "" "%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe" (
    start "" "%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe" (
    start "" "%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe" "%URL%"
    goto BROWSER_DONE
)

echo.
echo Brave is not installed.
echo.
pause
goto CHOOSE_BROWSER


REM =================================================
REM Opera
REM =================================================

:OPEN_OPERA

if exist "%ProgramFiles%\Opera\launcher.exe" (
    start "" "%ProgramFiles%\Opera\launcher.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%ProgramFiles(x86)%\Opera\launcher.exe" (
    start "" "%ProgramFiles(x86)%\Opera\launcher.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%LocalAppData%\Programs\Opera\launcher.exe" (
    start "" "%LocalAppData%\Programs\Opera\launcher.exe" "%URL%"
    goto BROWSER_DONE
)

echo.
echo Opera is not installed.
echo.
pause
goto CHOOSE_BROWSER


REM =================================================
REM Vivaldi
REM =================================================

:OPEN_VIVALDI

if exist "%ProgramFiles%\Vivaldi\Application\vivaldi.exe" (
    start "" "%ProgramFiles%\Vivaldi\Application\vivaldi.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%ProgramFiles(x86)%\Vivaldi\Application\vivaldi.exe" (
    start "" "%ProgramFiles(x86)%\Vivaldi\Application\vivaldi.exe" "%URL%"
    goto BROWSER_DONE
)

if exist "%LocalAppData%\Vivaldi\Application\vivaldi.exe" (
    start "" "%LocalAppData%\Vivaldi\Application\vivaldi.exe" "%URL%"
    goto BROWSER_DONE
)

echo.
echo Vivaldi is not installed.
echo.
pause
goto CHOOSE_BROWSER


REM =================================================
REM Default
REM =================================================

:OPEN_DEFAULT

start "" "%URL%"
goto BROWSER_DONE


:BROWSER_DONE

echo.
echo ==========================================
echo Browser opened.
echo URL: %URL%
echo ==========================================
echo.

exit /b 0


:EXIT_BROWSER

echo.
echo Browser opening cancelled.
echo.

exit /b 0