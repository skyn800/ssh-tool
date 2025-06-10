@echo off
pyinstaller main.spec
if %errorlevel% == 0 (
    echo PyInstaller successfully executed.
    
     REM Copy the icon folder to the dist folder
    REM Use xcopy for a more robust copy, including subdirectories and files
    xcopy /E /I /Y icon dist\icon
    xcopy /E /I /Y image dist\image
    
    echo Icon folder has been copied to the dist folder.
) else (
    echo PyInstaller failed with error code %errorlevel%.
)
pause