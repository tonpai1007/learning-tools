@echo off
setlocal
cd /d "%~dp0"

set "PY=C:\Users\Tonpa\AppData\Local\Programs\Python\Python312\python.exe"

title Learning Tools
echo ============================================
echo   Learning Tools - AI + NotebookLM study kit
echo ============================================
echo.
echo  [1] Generate everything (cards + quiz + summaries)
echo  [2] Flashcards only        (adds to spaced repetition)
echo  [3] Quiz only
echo  [4] Summaries + NotebookLM pack
echo  [5] Tutor - chat with your material
echo  [6] Review - spaced repetition drill
echo  [7] Show progress
echo  [8] Write a sample file into sources/
echo  [q] Quit
echo.
set /p choice="Choose: "

if "%choice%"=="1" goto all
if "%choice%"=="2" goto cards
if "%choice%"=="3" goto quiz
if "%choice%"=="4" goto summarize
if "%choice%"=="5" goto tutor
if "%choice%"=="6" goto review
if "%choice%"=="7" goto stats
if "%choice%"=="8" goto sample
if "%choice%"=="q" goto end
goto :eof

:all
"%PY%" -m lt all
goto end

:cards
"%PY%" -m lt cards --add
goto end

:quiz
"%PY%" -m lt quiz
echo.
start "" "output\quiz.html"
goto end

:summarize
"%PY%" -m lt summarize
goto end

:tutor
"%PY%" -m lt tutor
goto end

:review
"%PY%" -m lt review
goto end

:stats
"%PY%" -m lt stats
goto end

:sample
"%PY%" -m lt sample
goto end

:end
echo.
pause
endlocal
