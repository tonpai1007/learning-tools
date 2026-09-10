import pdfplumber
import os

files = {
    "exam": r"C:\Users\Tonpa\Downloads\midterm\Midterm machine design.pdf",
    "answer": r"C:\Users\Tonpa\Downloads\midterm\Answer Midterm 2564.pdf",
    "problem": r"C:\Users\Tonpa\Downloads\midterm\Problem Midterm Machine Design.pdf",
    "ch02": r"C:\Users\Tonpa\Downloads\midterm\Machine\Ch02 - Materials.pdf",
    "ch03": r"C:\Users\Tonpa\Downloads\midterm\Machine\Ch03 - Load and stress analysis.pdf",
}

os.makedirs("extracted", exist_ok=True)

for name, path in files.items():
    out_path = os.path.join("extracted", f"{name}.txt")
    lines = []
    try:
        if not os.path.exists(path):
            lines.append(f"FILE NOT FOUND: {path}")
        else:
            with pdfplumber.open(path) as pdf:
                lines.append(f"FILE: {path}")
                lines.append(f"TOTAL PAGES: {len(pdf.pages)}")
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    text = text if text else "[NO TEXT - image page]"
                    images = page.images
                    lines.append(f"\n{'='*60}")
                    lines.append(f"PAGE {i+1} (images: {len(images)})")
                    lines.append(f"{'='*60}")
                    lines.append(text)
    except Exception as e:
        lines.append(f"ERROR: {e}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_path} with {len(lines)} lines")