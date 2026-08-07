import sys as _sys
from pathlib import Path as _Path
for _p in (_Path(__file__).resolve().parent, _Path(__file__).resolve().parent.parent):
    if str(_p) not in _sys.path:
        _sys.path.append(str(_p))
from config import PROJECT_ROOT
from docling.document_converter import DocumentConverter
from pathlib import Path
import json

file_path = Path(f"{PROJECT_ROOT}/Results Dataset/cse 5 reg.pdf")
out_md_path = Path(f"{PROJECT_ROOT}/cse_5_reg_parsed.md")

converter = DocumentConverter()
result = converter.convert(file_path)
md_text = result.document.export_to_markdown()

with open(out_md_path, "w", encoding="utf-8") as f:
    f.write(md_text)

print(f"Saved to {out_md_path}")
