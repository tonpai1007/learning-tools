import os
from pathlib import Path
from lt.converters.pdf import extract_pdf_to_text

files = {
    "exam": r"C:\Users\Tonpa\Downloads\midterm\Midterm machine design.pdf",
    "answer": r"C:\Users\Tonpa\Downloads\midterm\Answer Midterm 2564.pdf",
    "problem": r"C:\Users\Tonpa\Downloads\midterm\Problem Midterm Machine Design.pdf",
    "ch02": r"C:\Users\Tonpa\Downloads\midterm\Machine\Ch02 - Materials.pdf",
    "ch03": r"C:\Users\Tonpa\Downloads\midterm\Machine\Ch03 - Load and stress analysis.pdf",
}

out_dir = Path("data") / "extracted"
out_dir.mkdir(parents=True, exist_ok=True)

for name, path in files.items():
    out_file = out_dir / f"{name}.txt"
    try:
        if not os.path.exists(path):
            print(f"Skipping (not found): {path}")
            continue
        text = extract_pdf_to_text(path, out_file)
        print(f"Extracted {name} -> {out_file} ({len(text.splitlines())} lines)")
    except Exception as e:
        print(f"Error on {name}: {e}")
