. "$env:USERPROFILE\miniconda3\shell\condabin\conda-hook.ps1"
conda activate "$env:USERPROFILE\miniconda3"
pyinstaller --onefile --windowed --name=QAA-AirType --icon=icon.ico src\remote_server.py