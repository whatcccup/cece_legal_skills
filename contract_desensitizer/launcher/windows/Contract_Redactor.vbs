' ---------------------------------------------------------------------------
' Contract Redactor . Windows 静默启动器
' 双击本文件（Contract_Redactor.vbs）：不弹出黑色命令行窗口，
' 后台启动服务并用 Chrome 应用窗口打开 http://127.0.0.1:18800/
' ---------------------------------------------------------------------------
Option Explicit

Dim fso, shell, baseDir, batPath, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(baseDir, "Contract_Redactor.bat")

If Not fso.FileExists(batPath) Then
    MsgBox "找不到 Contract_Redactor.bat，请确认两个文件在同一目录。", 16, "合同脱敏 / 还原"
    WScript.Quit 1
End If

' 0 = 隐藏窗口，False = 不等待
cmd = "cmd /c """ & batPath & """"
shell.Run cmd, 0, False

WScript.Quit 0
