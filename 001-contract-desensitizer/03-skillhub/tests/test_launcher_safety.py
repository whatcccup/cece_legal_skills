import sys,os,socket,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Launchers(unittest.TestCase):
 def test_mac_refuses_busy_port_without_stopping_owner(self):
  if sys.platform!='darwin':self.skipTest('requires macOS lsof')
  with socket.socket() as sentinel:
   sentinel.bind(('127.0.0.1',0));sentinel.listen()
   env=dict(os.environ,CONTRACT_REDACTOR_PORT=str(sentinel.getsockname()[1]))
   script=ROOT/'launcher/mac/Contract_Redactor.app/Contents/Resources/launch.sh'
   p=subprocess.run(['bash',str(script)],env=env,capture_output=True,text=True,timeout=10)
   self.assertEqual(p.returncode,1);self.assertIn('端口',p.stderr)
   with socket.create_connection(sentinel.getsockname(),timeout=2):pass
 def test_windows_does_not_terminate_port_owner(self):
  path=ROOT/'launcher/windows/Contract_Redactor.bat'
  if not path.exists(): self.skipTest('Windows launcher intentionally excluded from the Mac-only ZIP')
  source=path.read_text().lower()
  self.assertNotIn('taskkill',source);self.assertNotIn('stop-process',source)
  self.assertIn('goto port_busy',source)
if __name__=='__main__':unittest.main()
