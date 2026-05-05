Set shell = CreateObject("WScript.Shell")
projectPath = "C:\Users\Murat\Desktop\Python Projelerim\Notes"
launcher = Chr(34) & projectPath & "\Pelixi-Ac.bat" & Chr(34)
shell.Run launcher, 0, False
