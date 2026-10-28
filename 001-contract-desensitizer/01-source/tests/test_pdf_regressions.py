import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reportlab.pdfgen import canvas
from pypdf import PdfReader
import contract_redactor as R
class PDF(unittest.TestCase):
 def test_hit_page_redacted_unhit_page_keeps_text(self):
  with tempfile.TemporaryDirectory() as t:
   src=str(Path(t)/'in.pdf');out=str(Path(t)/'out.pdf');c=canvas.Canvas(src);c.drawString(72,700,'Contact: 13800138000');c.showPage();c.drawString(72,700,'Appendix without confidential values.');c.showPage();c.save()
   r=R.redact_file(src,types=['PHONE_MOBILE'],out_path=out,export_mode='external');self.assertEqual(r['applied'],1)
   pages=PdfReader(out).pages;self.assertEqual(len(pages),2);self.assertNotIn('13800138000',pages[0].extract_text());self.assertIn('Appendix without confidential values.',pages[1].extract_text())
 def test_page_without_text_cannot_be_called_checked(self):
  with tempfile.TemporaryDirectory() as t:
   src=str(Path(t)/'image.pdf');c=canvas.Canvas(src);c.rect(72,700,200,50);c.showPage();c.save()
   with self.assertRaisesRegex(RuntimeError,'检查'):
    R.redact_file(src,types=['PHONE_MOBILE'],out_path=str(Path(t)/'out.pdf'),export_mode='external')
if __name__=='__main__':unittest.main()
