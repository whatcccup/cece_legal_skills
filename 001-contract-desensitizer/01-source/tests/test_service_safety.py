# -*- coding: utf-8 -*-
import unittest, tempfile, threading, http.client, json, io, zipfile, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from docx import Document
import contract_app_server as S
class Service(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=S.start_app_server('127.0.0.1',0,self.tmp.name);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.token=self.server.RequestHandlerClass.state.token
 def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
 def request(self,path,body=b'',headers=None,method='POST'):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10);c.request(method,path,body,headers or {});r=c.getresponse();data=r.read();status=r.status;c.close();return status,data
 def upload(self):
  d=Document();d.add_paragraph('电话：\t13800138000；结束');b=io.BytesIO();d.save(b)
  body=b'--regression\r\nContent-Disposition: form-data; name="file"; filename="test.docx"\r\n\r\n'+b.getvalue()+b'\r\n--regression--\r\n'
  code,data=self.request('/api/upload',body,{'X-Contract-Token':self.token,'Content-Type':'multipart/form-data; boundary=regression'});self.assertEqual(code,200,data);return json.loads(data)['sid']
 def test_bad_host_origin_and_missing_token(self):
  for headers in [{'Host':'untrusted.example','X-Contract-Token':self.token},{'Origin':'https://untrusted.example','X-Contract-Token':self.token},{}]:self.assertEqual(self.request('/api/upload',headers=headers)[0],403)
 def test_oversize_rejected_before_body_sent(self):
  self.assertEqual(self.request('/api/upload',headers={'X-Contract-Token':self.token,'Content-Length':str(S.MAX_UPLOAD_BYTES+2*1024*1024)})[0],413)
 def test_every_export_has_separate_mapping_and_no_embedded_originals(self):
  sid=self.upload()
  for mode in [None,'reversible']:
   req={'enabled_types':['PHONE_MOBILE']}
   if mode:req['export_mode']=mode
   code,data=self.request('/api/apply/'+sid,json.dumps(req),{'X-Contract-Token':self.token,'Content-Type':'application/json'});self.assertEqual(code,200,data);r=json.loads(data)
   self.assertTrue(r['mapping_url'])
   if mode is None: external_url=r['output_url']
   else: self.assertEqual(r['output_url'],external_url)
   code,blob=self.request(r['output_url'],method='GET');self.assertEqual(code,200)
   with zipfile.ZipFile(io.BytesIO(blob)) as z:
    self.assertNotIn('customXml/mapping.json', z.namelist())
    self.assertFalse(any(b'13800138000' in z.read(n) for n in z.namelist()))
  code,blob=self.request(external_url,method='GET')
  with zipfile.ZipFile(io.BytesIO(blob)) as z:self.assertNotIn('customXml/mapping.json',z.namelist())
 def test_web_rule_loaded_twice(self):
  p=Path(self.tmp.name);r=p/'rules.md';r.write_text('| 28 | TEST_CODE | 商业信息 | 中 | 工号 | 隐藏 | keep_head=2 | 是 | ZQC[0-9]{8} |\n');f=p/'x.txt';f.write_text('员工工号：ZQC58374926')
  for _ in range(2):self.assertTrue(any(i['type']=='TEST_CODE' for i in S._run_detector(str(f),str(r))['report']['items']))
 def test_guard_blocks_external_before_socket_connect(self):
  code="""import socket
import contract_sensitive_detector as D
D.enforce_loopback_only()
actions=[lambda:socket.socket().connect(('203.0.113.1',9)),lambda:socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto(b'test',('203.0.113.1',9)),lambda:socket.getaddrinfo('outside.example',80)]
for action in actions:
 try:action()
 except RuntimeError:print('blocked')
 else:raise AssertionError('external call not blocked')
s=socket.create_connection(('127.0.0.1',PORT),timeout=2)
s.sendall(b'GET /health HTTP/1.1\\r\\nHost: 127.0.0.1:PORT\\r\\nConnection: close\\r\\n\\r\\n')
assert b'200' in s.recv(4096)
s.close()
""".replace('PORT',str(self.server.server_port))
  p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10);self.assertEqual(p.returncode,0,p.stderr);self.assertIn('blocked',p.stdout)
if __name__=='__main__':unittest.main()
