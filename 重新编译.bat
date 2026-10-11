@echo off
chcp 65001 >nul
echo ============================================
echo  东北大学开题报告 LaTeX 模板 - 编译
echo ============================================
echo.
echo [1/2] 第一遍编译...
xelatex -interaction=nonstopmode 开题报告模板.tex >nul
echo [2/2] 第二遍编译（背景框需要页码引用）...
xelatex -interaction=nonstopmode 开题报告模板.tex >nul
if exist 开题报告模板.pdf (
  echo.
  echo 编译成功：开题报告模板.pdf
  start "" 开题报告模板.pdf
) else (
  echo.
  echo 编译失败，请查看 开题报告模板.log
)
pause
