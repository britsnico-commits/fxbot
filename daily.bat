@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ============================================
echo FXBOT DAILY ONE-CLICK CHECK
echo ============================================
echo.
echo [1/3] Downloading market data and running predictor...
python predictor_v3.py
echo.
echo [2/3] Checking if forecaster is accurate...
python check.py
echo.
echo [3/3] Testing fake money...
python paper_trade_v2.py
echo.
echo ============================================
echo DONE - Check results folder for equity curves
echo ============================================
pause
