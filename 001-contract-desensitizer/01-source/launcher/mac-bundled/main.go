// Self-contained macOS application launcher; never invokes a system Python.
package main

import (
  "fmt"
  "os"
  "os/exec"
  "path/filepath"
  "syscall"
)

func showError(message string) {
  exec.Command("/usr/bin/osascript", "-e", "on run argv\ndisplay alert \"合同脱敏工具\" message (item 1 of argv) as critical\nend run", message).Run()
}
func main() {
  exe, err := os.Executable()
  if err != nil { showError(err.Error()); os.Exit(1) }
  resources := filepath.Join(filepath.Dir(exe), "..", "Resources")
  config, err := os.UserConfigDir()
  if err != nil { showError(err.Error()); os.Exit(1) }
  base := filepath.Join(config, "ContractRedactor")
  if err := os.MkdirAll(base, 0700); err != nil { showError(err.Error()); os.Exit(1) }
  lock, err := os.OpenFile(filepath.Join(base,"app.lock"), os.O_CREATE|os.O_RDWR,0600)
  if err != nil { showError(err.Error()); os.Exit(1) }
  defer lock.Close()
  if err := syscall.Flock(int(lock.Fd()),syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
    showError("工具已运行，请使用已打开的页面；需要重启时请先在原工具网页点击退出。"); os.Exit(1)
  }
  logPath := filepath.Join(base,"startup.log")
  log, err := os.OpenFile(logPath,os.O_CREATE|os.O_TRUNC|os.O_WRONLY,0600)
  if err != nil { showError(err.Error()); os.Exit(1) }
  defer log.Close()
  args:=[]string{"-I","-X","utf8","-B",filepath.Join(resources,"bootstrap.py"),"--workdir",filepath.Join(base,"Data","sessions"),"--open-browser"}
  if len(os.Args)>1 && os.Args[1]=="--self-test" {
    args=[]string{"-I","-X","utf8","-B",filepath.Join(resources,"bootstrap.py"),"--self-test"}
  } else { args=append(args,os.Args[1:]...) }
  cmd:=exec.Command(filepath.Join(resources,"python","bin","python3.13"),args...)
  cmd.Dir=base
  cmd.Env=append(os.Environ(),"CONTRACT_REDACTOR_RULES="+filepath.Join(base,"Rules","脱敏规则清单.md"))
  cmd.Stdout,cmd.Stderr=log,log
  if err:=cmd.Run();err!=nil {
    if len(os.Args)>1 && os.Args[1]=="--self-test" { fmt.Fprintln(os.Stderr,err,"log:",logPath) } else { showError("无法启动，请查看日志："+logPath+"。端口可能已占用；请先从原工具网页退出，不会结束其他程序。") }
    os.Exit(1)
  }
}
