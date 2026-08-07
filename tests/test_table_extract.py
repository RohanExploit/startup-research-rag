import json
from pathlib import Path
from docling.document_converter import DocumentConverter

def test_docling():
    input_file = Path("R:/Startup research/Start up V2/Results Dataset/cse 5 reg.pdf")
    converter = DocumentConverter()
    print("Running docling on", input_file)
    result = converter.convert(input_file)
    md_text = result.document.export_to_markdown()
    
    out_md = Path("R:/Startup research/Start up V2/Results Dataset/cse 5 reg_docling.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md_text)
    
    print(f"Saved docling output to {out_md}")
    
    # Print the first few lines that look like a table
    lines = md_text.split('\n')
    table_lines = [l for l in lines if '|' in l]
    print(f"Found {len(table_lines)} table lines. First 20:")
    for l in table_lines[:20]:
        print(l)

if __name__ == '__main__':
    test_docling()
