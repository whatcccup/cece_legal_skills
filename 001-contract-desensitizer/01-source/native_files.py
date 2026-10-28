"""System file dialogs. Paths come only from OS dialogs, never from browser input."""
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

DIALOG_LOCK = threading.Lock()


def available():
    return os.environ.get('CONTRACT_REDACTOR_DESKTOP') == '1' and sys.platform in ('darwin', 'win32')


def _dialog(kind, default=''):
    if not available():
        raise RuntimeError('请从桌面 App 启动，才能使用系统文件窗口')
    if not DIALOG_LOCK.acquire(blocking=False):
        raise RuntimeError('已有文件窗口打开，请先完成或取消该窗口')
    try:
        if sys.platform == 'darwin':
            # Values travel as argv, not executable AppleScript.
            script = '''on run argv
try
activate
if item 1 of argv is "open" then
set chosen to choose file with prompt "选择合同（Word、PDF 或文本）"
else
set chosen to choose file name with prompt "保存脱敏文件；还原 JSON 会同时保存，JSON 不可外发。已有文件不会被覆盖，请使用新文件名。" default location (POSIX file (item 2 of argv)) default name (item 3 of argv)
end if
return POSIX path of chosen
on error number -128
return ""
end try
end run'''
            path = Path(default)
            args = ['/usr/bin/osascript', '-e', script, kind, str(path.parent), path.name]
            result = subprocess.run(args, capture_output=True, text=True, check=True)
            return result.stdout.rstrip('\r\n') or None
        script = r'''
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
if ($env:CONTRACT_DIALOG_KIND -eq 'open') {
  $d = New-Object System.Windows.Forms.OpenFileDialog
  $d.Title = '选择合同'
  $d.Filter = '合同文件|*.docx;*.pdf;*.txt;*.md'
} else {
  $d = New-Object System.Windows.Forms.SaveFileDialog
  $d.Title = '保存脱敏文件（同时保存不可外发的 JSON）'
  $d.InitialDirectory = [IO.Path]::GetDirectoryName($env:CONTRACT_DIALOG_DEFAULT)
  $d.FileName = [IO.Path]::GetFileName($env:CONTRACT_DIALOG_DEFAULT)
  $d.Filter = '脱敏文件|*' + [IO.Path]::GetExtension($env:CONTRACT_DIALOG_DEFAULT)
  $d.AddExtension = $true
  $d.DefaultExt = [IO.Path]::GetExtension($env:CONTRACT_DIALOG_DEFAULT).TrimStart('.')
  $d.OverwritePrompt = $true
}
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::Write($d.FileName)
}
$d.Dispose()
'''
        shell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
        env = dict(os.environ, CONTRACT_DIALOG_KIND=kind, CONTRACT_DIALOG_DEFAULT=default)
        result = subprocess.run([str(shell), '-NoProfile', '-STA', '-NonInteractive', '-EncodedCommand', encoded],
                                env=env, capture_output=True, check=True, creationflags=0x08000000)
        return result.stdout.decode('utf-8-sig').rstrip('\r\n') or None
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError('无法打开系统文件窗口，请重新启动工具后重试。') from exc
    finally:
        DIALOG_LOCK.release()


def choose_contract():
    return _dialog('open')


def save_pair(outputs, original_path=None):
    document = Path(outputs['document'])
    mapping = Path(outputs['mapping']) if outputs.get('mapping') else None
    if not mapping or not document.is_file() or not mapping.is_file():
        raise RuntimeError('请先完成脱敏，两个文件生成齐全后才能保存')
    folder = Path(original_path).parent if original_path else Path.home() / 'Documents'
    if not folder.is_dir():
        folder = Path.home()
    selected = _dialog('save', str(folder / document.name))
    if not selected:
        return {'ok': True, 'cancelled': True}
    target = Path(selected)
    if target.suffix.lower() != document.suffix.lower():
        raise ValueError('请保留原来的文件扩展名：' + document.suffix)
    mapping_target = Path(str(target) + '.mapping.json')
    created = []
    try:
        # Exclusive creation: never overwrite the contract, a symlink, or an existing JSON.
        for source, dest in ((document, target), (mapping, mapping_target)):
            with dest.open('xb') as out:
                created.append(dest)
                if os.name != 'nt':
                    os.chmod(dest, 0o600)
                with source.open('rb') as inp:
                    shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
    except Exception:
        for dest in created:
            dest.unlink()
        raise
    return {'ok': True, 'folder': str(target.parent),
            'files': [{'name': p.name, 'size': p.stat().st_size, 'how': 'native'} for p in created]}
