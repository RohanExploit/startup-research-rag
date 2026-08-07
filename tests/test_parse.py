from docling.document_converter import DocumentConverter
from pathlib import Path
import json

file_path = Path("R:/Startup research/Start up V2/Results Dataset/cse 5 reg.pdf")
out_md_path = Path("R:/Startup research/Start up V2/cse_5_reg_parsed.md")

converter = DocumentConverter()
result = converter.convert(file_path)
md_text = result.document.export_to_markdown()

with open(out_md_path, "w", encoding="utf-8") as f:
    f.write(md_text)

print(f"Saved to {out_md_path}")
