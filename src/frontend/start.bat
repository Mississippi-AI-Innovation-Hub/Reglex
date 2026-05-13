@echo off
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║                  DOCUMENT AI ASSISTANT                         ║
echo ║               Professional Dark Theme Edition                  ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo [1/3] Navigating to project...
cd client
echo.
echo [2/3] Installing dependencies (if needed)...
call npm install --silent
echo.
echo [3/3] Starting development server...
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo    🚀 Server will start at: http://localhost:3000
echo    ⚙️  Configure API in: client\.env
echo    📚 Documentation: SETUP.md
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
call npm run dev
