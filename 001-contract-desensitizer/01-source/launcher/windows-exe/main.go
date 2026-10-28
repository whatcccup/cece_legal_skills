// Windows installed application launcher. Uses only the runtime shipped beside this EXE.
package main

import (
  "fmt"
  "os"
  "os/exec"
  "path/filepath"
  "syscall"
  "unsafe"
)

func showError(message string) {
  text, _ := syscall.UTF16PtrFromString(message)
  title, _ := syscall.UTF16PtrFromString("Contract Redactor")
  syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW").Call(0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), 0x10)
}

func main() {
  exe, err := os.Executable()
  if err != nil { showError(err.Error()); os.Exit(1) }
  root := filepath.Dir(exe)
  runtime := filepath.Join(root, "_support", "runtime", "python.exe")
  app := filepath.Join(root, "_support", "tool", "contract_app_server.py")
  cache, err := os.UserCacheDir()
  if err != nil { showError(err.Error()); os.Exit(1) }
  data := filepath.Join(cache, "ContractRedactor", "Data")
  mutexName, _ := syscall.UTF16PtrFromString("Local\\ContractRedactor")
  handle, _, mutexErr := syscall.NewLazyDLL("kernel32.dll").NewProc("CreateMutexW").Call(0, 0, uintptr(unsafe.Pointer(mutexName)))
  if handle == 0 { showError(mutexErr.Error()); os.Exit(1) }
  defer syscall.CloseHandle(syscall.Handle(handle))
  if mutexErr == syscall.Errno(183) { showError("工具已运行，请在浏览器访问 http://127.0.0.1:18800/。需要重新启动时，请先从旧工具网页退出。"); os.Exit(1) }
  if err := os.MkdirAll(data, 0700); err != nil { showError(err.Error()); os.Exit(1) }
  logPath := filepath.Join(data, "startup.log")
  log, err := os.OpenFile(logPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0600)
  if err != nil { showError(err.Error()); os.Exit(1) }
  defer log.Close()
  args := []string{"-I", "-X", "utf8", "-u", app, "--workdir", filepath.Join(data, "sessions"), "--open-browser"}
  if len(os.Args) > 1 && os.Args[1] == "--self-test" {
    args = []string{"-I", "-X", "utf8", "-c", "import docx, pdfplumber, pypdf, reportlab, pypdfium2, PIL, contract_app_server, contract_app_ui, contract_redactor, contract_sensitive_detector, docx_text; print('Bundled runtime imports OK')"}
  }
  cmd := exec.Command(runtime, args...)
  cmd.Dir = root
  cmd.Env = append(os.Environ(), "CONTRACT_REDACTOR_RULES="+filepath.Join(cache, "ContractRedactor", "Rules", "脱敏规则清单.md"))
  cmd.Stdout, cmd.Stderr = log, log
  cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
  if err := cmd.Run(); err != nil {
    showError(fmt.Sprintf("Cannot start the tool.\nPlease reinstall the application if its files are missing.\nPort 18800 may already be in use. Use the existing tool or close it from its own window. No other process was stopped.\n\nDetails: %s\n%s", logPath, err))
    os.Exit(1)
  }
}
