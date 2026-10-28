import http.client, json, os, sys, tempfile, threading, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contract_sensitive_detector as D
import contract_app_server as S
class UserRules(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'Rules'/'rules.md'
  self.env=patch.dict(os.environ,{'CONTRACT_REDACTOR_RULES':str(self.path)});self.env.start()
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def test_first_copy_preserves_user_edits(self):
  self.assertEqual(Path(D.default_rules_path()).read_bytes(),(Path(D.__file__).parent/'脱敏规则清单.md').read_bytes())
  self.path.write_text('user edits');self.assertEqual(D.default_rules_path(),str(self.path));self.assertEqual(self.path.read_text(),'user edits')
 def test_settings_reloads_user_rule(self):
  D.default_rules_path();self.path.write_text('| 28 | REVIEW_CODE_28 | 商业信息 | 中 | 工号 | 隐藏 | keep_head=2; keep_tail=3 | 是 | ZQC[0-9]{8} |\n')
  with D.RULES_LOCK:
   self.assertEqual(len(D.load_settings().extra_specs),1);self.path.write_text('');self.assertEqual(len(D.load_settings().extra_specs),0)
 def test_open_requires_token_and_uses_fixed_path(self):
  server=S.start_app_server('127.0.0.1',0,str(Path(self.tmp.name)/'sessions'));threading.Thread(target=server.serve_forever,daemon=True).start()
  def request(headers=None):
   conn=http.client.HTTPConnection(*server.server_address);conn.request('POST','/api/rules/open',body=json.dumps({'path':'/untrusted/file'}),headers=headers or {});r=conn.getresponse();result=(r.status,json.loads(r.read()));conn.close();return result
  try:
   with patch('subprocess.Popen') as opener:
    self.assertEqual(request()[0],403);opener.assert_not_called();status,result=request({'X-Contract-Token':server.RequestHandlerClass.state.token});self.assertEqual(status,200);self.assertEqual(result['path'],str(self.path));self.assertEqual(opener.call_args.args[0][-1],str(self.path))
   with patch.object(S.sys,'platform','win32'), patch.object(S.os,'startfile',side_effect=OSError('no association'),create=True), patch('subprocess.Popen') as opener:
    status,result=request({'X-Contract-Token':server.RequestHandlerClass.state.token});self.assertEqual(status,200);self.assertTrue(opener.call_args.args[0][0].endswith('notepad.exe'));self.assertEqual(opener.call_args.args[0][-1],str(self.path))
   with patch('subprocess.Popen',side_effect=OSError('no editor')):
    status,result=request({'X-Contract-Token':server.RequestHandlerClass.state.token});self.assertEqual(status,500);self.assertEqual(result['path'],str(self.path))
  finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
