import pdfplumber

def extract_text():
    path = "R:/Startup research/Start up V2/Results Dataset/cse 5 reg.pdf"
    with pdfplumber.open(path) as pdf:
        for i in range(min(2, len(pdf.pages))):
            text = pdf.pages[i].extract_text(layout=True)
            print(f"--- PAGE {i} ---")
            print(text)

if __name__ == '__main__':
    extract_text()
