' ---------------------------------------------------------------------------
' 合同脱敏助手 · Windows 静默启动器
' 双击本文件：不弹黑窗，后台启动服务并打开 http://127.0.0.1:18800/
' ---------------------------------------------------------------------------
Option Explicit

Dim fso, shell, baseDir, batPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(baseDir, "start.bat")

If Not fso.FileExists(batPath) Then
  MsgBox "找不到 start.bat，请确认两个文件在同一目录。", 16, "合同脱敏助手"
  WScript.Quit 1
End If

shell.Run "cmd /c """ & batPath & """", 0, False
WScript.Quit 0
