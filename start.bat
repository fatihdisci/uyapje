@echo off
chcp 65001 >nul
echo UYAP Hukuk Asistani baslatiliyor...
echo.

where gemini >nul 2>&1
if %errorlevel% neq 0 (
    echo [UYARI] Gemini CLI bulunamadi.
    echo   Kurulum: npm install -g @google/gemini-cli
    echo   Auth   : gemini auth login
    echo.
)

start "UYAP Backend" cmd /k "cd backend && python -m uvicorn main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
start "UYAP Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 4 /nobreak >nul
start http://localhost:5173
echo.
echo Tamamlandi. Tarayici acildi.
