Unicode True
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!ifndef PAYLOAD
!error "PAYLOAD must point to the bundled application"
!endif
!ifndef OUTPUT
!error "OUTPUT must name the local preview installer"
!endif
Name "合同脱敏工具"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\ContractRedactor"
InstallDirRegKey HKCU "Software\ContractRedactor" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
VIProductVersion "1.3.0.0"
VIAddVersionKey /LANG=2052 "ProductName" "合同脱敏工具"
VIAddVersionKey /LANG=2052 "FileDescription" "合同脱敏工具安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "1.3.0.0"
VIAddVersionKey /LANG=2052 "LegalCopyright" "LegalTech CC · MIT"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\ContractRedactor.exe"
!define MUI_FINISHPAGE_RUN_TEXT "启动合同脱敏工具"
!define MUI_WELCOMEPAGE_TEXT "安装后从桌面图标打开，无需安装 Python 或联网准备依赖。$\r$\n$\r$\n合同处理在本机进行，不需要 AI 或 Python 安装。"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${PAYLOAD}/LICENSE"
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Function CheckAppClosed
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\ContractRedactor") p.r0'
  ${If} $0 != 0
    System::Call 'kernel32::CloseHandle(p r0)'
    MessageBox MB_OK|MB_ICONEXCLAMATION "请先从工具网页右上角点击“退出”，再安装或卸载。关闭浏览器标签页不会停止工具。"
    Abort
  ${EndIf}
FunctionEnd
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "本安装包需要 64 位 Windows 10 或 Windows 11。"
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "本安装包需要 Windows 10 或 Windows 11。"
    Abort
  ${EndIf}
  SetShellVarContext current
  Call CheckAppClosed
FunctionEnd
Function un.onInit
  SetShellVarContext current
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\ContractRedactor") p.r0'
  ${If} $0 != 0
    System::Call 'kernel32::CloseHandle(p r0)'
    MessageBox MB_OK|MB_ICONEXCLAMATION "请先从工具网页退出服务，再卸载。"
    Abort
  ${EndIf}
FunctionEnd
Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}/*.*"
  CreateShortcut "$DESKTOP\合同脱敏工具.lnk" "$INSTDIR\ContractRedactor.exe"
  CreateDirectory "$SMPROGRAMS\合同脱敏工具"
  CreateShortcut "$SMPROGRAMS\合同脱敏工具\合同脱敏工具.lnk" "$INSTDIR\ContractRedactor.exe"
  CreateShortcut "$SMPROGRAMS\合同脱敏工具\使用说明.lnk" "$INSTDIR\README-先读.md"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\ContractRedactor" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ContractRedactor" "DisplayName" "合同脱敏工具"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ContractRedactor" "DisplayVersion" "1.3.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ContractRedactor" "Publisher" "LegalTech CC"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ContractRedactor" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ContractRedactor" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ContractRedactor" "NoRepair" 1
SectionEnd
Section "Uninstall"
  ; App data lives outside INSTDIR and is deliberately preserved.
  Delete "$DESKTOP\合同脱敏工具.lnk"
  Delete "$SMPROGRAMS\合同脱敏工具\合同脱敏工具.lnk"
  Delete "$SMPROGRAMS\合同脱敏工具\使用说明.lnk"
  RMDir "$SMPROGRAMS\合同脱敏工具"
  RMDir /r "$INSTDIR\_support"
  RMDir /r "$INSTDIR\其他资料"
  Delete "$INSTDIR\ContractRedactor.exe"
  Delete "$INSTDIR\README-先读.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\BUILD-MANIFEST.json"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\ContractRedactor"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ContractRedactor"
SectionEnd
