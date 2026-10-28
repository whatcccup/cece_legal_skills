"""Start the bundled engine without relying on user packages or Python settings."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'tool'))
if sys.argv[1:] == ['--self-test']:
    import docx, pdfplumber, pypdf, reportlab, pypdfium2, PIL
    import contract_app_server, contract_app_ui, contract_redactor, contract_sensitive_detector, docx_text
    print('Bundled runtime imports OK', sys.version)
else:
    import contract_app_server
    raise SystemExit(contract_app_server.main(sys.argv[1:]))
