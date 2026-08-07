import pdfplumber

def extract_text():
    path = "R:/Startup research/Start up V2/Results Dataset/cse 5 reg.pdf"
    with pdfplumber.open(path) as pdf:
        with open("R:/Startup research/Start up V2/Results Dataset/raw_text.txt", "w", encoding="utf-8") as f:
            for i in range(len(pdf.pages)):
                text = pdf.pages[i].extract_text(layout=True)
                f.write(text + "\n")

if __name__ == '__main__':
    extract_text()
