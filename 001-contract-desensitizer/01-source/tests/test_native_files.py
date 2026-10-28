import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docx import Document
import native_files as N
import contract_app_server as S


class NativeFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'CONTRACT_REDACTOR_DESKTOP': '1',
                                          'CONTRACT_REDACTOR_RULES': str(self.root/'rules.md')})
        self.env.start()
        self.server = S.start_app_server('127.0.0.1', 0, str(self.root/'sessions'))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.token = self.server.RequestHandlerClass.state.token

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        self.env.stop(); self.tmp.cleanup()

    def post(self, path, data=None, token=True):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        headers = {'Content-Type': 'application/json'}
        if token: headers['X-Contract-Token'] = self.token
        conn.request('POST', path, json.dumps(data or {}), headers)
        r = conn.getresponse(); result = (r.status, json.loads(r.read())); conn.close()
        return result

    def upload(self):
        src = self.root/'原合同.docx'
        d = Document(); d.add_paragraph('联系电话：13800138000'); d.save(src)
        with patch.object(N, 'choose_contract', return_value=str(src)):
            status, result = self.post('/api/native/open', {'path': '/untrusted'})
        self.assertEqual(status, 200); self.assertTrue(result['ok'])
        return src, result['sid']

    def test_native_upload_apply_save_restore(self):
        src, sid = self.upload(); original = src.read_bytes()
        # Even an old browser requesting reversible must never embed original data.
        status, result = self.post('/api/apply/'+sid, {'export_mode': 'reversible'})
        self.assertEqual(status, 200); self.assertTrue(result['mapping_url'])
        target = self.root/'已脱敏.docx'
        with patch.object(N, '_dialog', return_value=str(target)) as dialog:
            status, saved = self.post('/api/native/save/'+sid, {'path': '/untrusted'})
        self.assertEqual(status, 200); self.assertEqual(len(saved['files']), 2)
        self.assertEqual(Path(dialog.call_args.args[1]), self.root/'原合同_脱敏.docx')
        self.assertEqual(src.read_bytes(), original)
        self.assertTrue(Path(str(target)+'.mapping.json').exists())
        with patch.object(N, 'choose_contract', return_value=str(target)):
            status, restored = self.post('/api/native/open', {'mode': 'restore'})
        self.assertTrue(restored['mapping_found'])
        status, restored = self.post('/api/restore/'+restored['sid'])
        self.assertEqual(status, 200); self.assertTrue(restored['ok'])

    def test_cancel_auth_and_disabled(self):
        with patch.object(N, 'choose_contract', return_value=None) as chooser:
            self.assertEqual(self.post('/api/native/open', token=False)[0], 403)
            chooser.assert_not_called()
            self.assertTrue(self.post('/api/native/open')[1]['cancelled'])
        with patch.dict(os.environ, {'CONTRACT_REDACTOR_DESKTOP': '0'}), patch.object(N, 'choose_contract') as chooser:
            self.assertEqual(self.post('/api/native/open')[0], 400); chooser.assert_not_called()

    def test_pair_collision_rolls_back_and_cancel_writes_nothing(self):
        src, sid = self.upload(); self.post('/api/apply/'+sid)
        target = self.root/'输出.docx'
        mapping = Path(str(target)+'.mapping.json'); mapping.write_text('user data')
        with patch.object(N, '_dialog', return_value=str(target)):
            self.assertEqual(self.post('/api/native/save/'+sid)[0], 409)
        self.assertFalse(target.exists()); self.assertEqual(mapping.read_text(), 'user data')
        with patch.object(N, '_dialog', return_value=str(src)):
            self.assertEqual(self.post('/api/native/save/'+sid)[0], 409)
        self.assertTrue(src.exists())
        with patch.object(N, '_dialog', return_value=None):
            self.assertTrue(self.post('/api/native/save/'+sid)[1]['cancelled'])

    def test_dialog_paths_are_data_and_lock_is_released(self):
        with patch.object(N.sys, 'platform', 'darwin'), patch.object(N.subprocess, 'run') as run:
            run.return_value.stdout = '/tmp/合同 " $(touch ignored).docx\n'
            self.assertIn('$(touch ignored)', N._dialog('save', '/tmp/中文合同.docx'))
            self.assertEqual(run.call_args.args[0][-2:], ['/tmp', '中文合同.docx'])
        with patch.object(N.sys, 'platform', 'win32'), patch.object(N.subprocess, 'run') as run:
            run.return_value.stdout = 'C:\\中文合同.docx'.encode('utf-8')
            self.assertEqual(N.choose_contract(), 'C:\\中文合同.docx')
            self.assertIn('-STA', run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['env']['CONTRACT_DIALOG_KIND'], 'open')
        with patch.object(N.sys, 'platform', 'darwin'), patch.object(N.subprocess, 'run', side_effect=OSError('unavailable')):
            with self.assertRaisesRegex(RuntimeError, '系统文件窗口'):
                N.choose_contract()
        self.assertFalse(N.DIALOG_LOCK.locked())


if __name__ == '__main__': unittest.main()
