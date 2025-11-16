@echo off
chcp 65001 >nul
echo ========================================
echo   ACU Simulator 终极打包方案
echo ========================================
echo.

echo 使用--collect-all方式包含所有Qt依赖...
echo.

python -m PyInstaller --name "ACU_Simulator" ^
  --windowed ^
  --onedir ^
  --add-data "protocol_parser.py;." ^
  --add-data "setup_qt_environment.py;." ^
  --collect-all PySide6 ^
  --hidden-import=psutil ^
  --clean ^
  --noconfirm ^
  ACU_simulation.py

if exist "dist\ACU_Simulator.exe" (
    echo ✓ 终极打包成功！
    echo 文件应该包含所有Qt依赖
    start dist
) else (
    echo ✗ 打包失败
)
pause