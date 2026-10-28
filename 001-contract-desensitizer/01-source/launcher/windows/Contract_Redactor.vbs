' ---------------------------------------------------------------------------
' Contract Redactor Windows 启动器
' 显示初始化窗口，确保安装错误和端口占用提示可见。
' ---------------------------------------------------------------------------
Option Explicit

Dim fso, shell, baseDir, batPath, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(baseDir, "Start.bat")
If Not fso.FileExists(batPath) Then batPath = fso.BuildPath(baseDir, "Contract_Redactor.bat")

If Not fso.FileExists(batPath) Then
    MsgBox "找不到 Contract_Redactor.bat，请确认两个文件在同一目录。", 16, "合同脱敏 / 还原"
    WScript.Quit 1
End If

' 1 = 显示初始化窗口；服务启动后初始化窗口自动退出。
cmd = "cmd /c """ & batPath & """"
shell.Run cmd, 1, False

WScript.Quit 0
