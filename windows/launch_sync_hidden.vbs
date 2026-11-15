Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "E:\2026\3. Temp\kindle-dashboard\kindle-dashboard\windows"
WshShell.Run """C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe"" ""E:\2026\3. Temp\kindle-dashboard\kindle-dashboard\windows\antigravity_sync.py"" --spawn-hidden", 0, True