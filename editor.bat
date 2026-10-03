@echo off
rem サーバーを別ウィンドウで起動し、Windows側でブラウザを開く
start "Storyline editor" /min wsl.exe --cd ~/storyflow-d3 python3 scripts/storyline_editor_server.py 8001 --no-browser
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8001/editor.html
