# process_pdfs.py

import fitz  # PyMuPDF
import json
import re
from pathlib import Path
import time
import string
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

def get_body_style(doc):
    sizes = Counter()
    page_count = doc.page_count
    pages_to_scan = set([p for p in [0, 1, page_count // 2, page_count - 1] if 0 <= p < page_count])
    
    for i in pages_to_scan:
        for block in doc[i].get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        sizes[round(span['size'])] += 1
                        
    return sizes.most_common(1)[0][0] if sizes else 10

def reconstruct_lines_with_spacing(doc):
    all_lines = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", sort=True).get("blocks", [])
        for block in blocks:
            last_y1 = 0
            for line in block.get("lines", []):
                if not line.get("spans"):
                    continue
                first_span = line["spans"][0]
                text = " ".join([s['text'] for s in line['spans']]).strip()
                if not text or len(text) < 2:
                    continue
                y0 = line['bbox'][1]
                all_lines.append({
                    "page": page_num + 1,
                    "text": text,
                    "size": round(first_span['size']),
                    "font": first_span['font'],
                    "is_bold": "bold" in first_span['font'].lower(),
                    "space_above": y0 - last_y1,
                    "y0": y0
                })
                last_y1 = line['bbox'][3]
    return all_lines

def clean_title(title: str):
    """
    Sanitizes the extracted title:
    - Removes most special characters.
    - Ensures it contains meaningful alphabetic content.
    """
    title = title.strip()
    title = re.sub(r'[^\w\s\-:]', '', title)  # Remove all except word characters, space, dash, colon
    title = re.sub(r'\s+', ' ', title)  # Normalize spaces

    # Reject if title is too short or contains no alphabet
    if len(title) < 5 or not re.search(r'[A-Za-z]', title):
        return None
    return title


def looks_like_cover_page(lines, body_size):
    large_lines = [line for line in lines if line["page"] == 1 and line["size"] > body_size * 1.3]
    if len(large_lines) >= 3 and all(line["space_above"] > 5 for line in large_lines[1:]):
        return True
    return False

def extract_title_from_cover(lines, body_size):
    lines = [line for line in lines if line["page"] == 1 and line["size"] > body_size * 1.2]
    title = " ".join(line["text"] for line in lines).strip()
    return title

def analyze_document_structure(doc):
    if doc.page_count == 0:
        return "Untitled Document", []

    body_size = get_body_style(doc)
    all_lines = reconstruct_lines_with_spacing(doc)

    # Detect cover page
    is_cover = looks_like_cover_page(all_lines, body_size)

    # Identify footers to ignore
    footers = Counter()
    page_count = doc.page_count
    pages_to_scan = [p for p in [0, 1, page_count - 2, page_count - 1] if 0 <= p < page_count]
    for page_num in pages_to_scan:
        footer_start = doc[page_num].rect.height * 0.85
        for line in all_lines:
            if line["page"] == page_num + 1 and line["y0"] >= footer_start:
                footers[line["text"]] += 1
    footers_to_ignore = {text for text, count in footers.items() if count > 1}

    # --- Step 2: Score each line to find heading candidates ---
    candidates = []
    for line in all_lines:
        text = line["text"].strip()

        # Skip known junk patterns
        if text in footers_to_ignore:
            continue
        if re.fullmatch(r'[.\-–—•\s]{5,}', text):  # Just dots or lines
            continue
        if re.fullmatch(r'\d+[\.:]?', text):  # Pure numbers like "1." or "10"
            continue
        if len(text) < 4:  # Very short strings
            continue
        if text.lower().startswith("table of contents"):
            continue

        # Reject list-style long sentences like "2) This report is expected..."
        if re.match(r'^\s*\d+[\.\):]\s+', text) and len(text.split()) > 10:
            continue

        score = 0
        if line["is_bold"]:
            score += 3
        if line["size"] > body_size * 1.1:
            score += 3
        if line["space_above"] > body_size * 0.8:
            score += 2
        if len(text.split()) < 15:
            score += 1

        # Only reward structured headings like "1. Title" if short and clean
        if re.match(r'^\s*(\d+(\.\d+)*|[A-Z])[\.\):\-]\s+[A-Z]', text) and len(text.split()) <= 10:
            score += 2

        # Penalize sentence-like lines (long + ends with period)
        if text.endswith('.') and len(text.split()) > 8:
            score -= 3

        if score >= 4:
            candidates.append(line)

    # Assign heading levels
    outline = []
    if candidates:
        heading_styles = sorted(set((c["size"], c["is_bold"]) for c in candidates), reverse=True)
        style_to_level = {style: f"H{i+1}" for i, style in enumerate(heading_styles)}

        seen = set()
        for c in candidates:
            key = (c["text"], c["page"])
            if key not in seen:
                seen.add(key)
                level = style_to_level.get((c["size"], c["is_bold"]), "H4")
                adj_page = c["page"] - 1 if is_cover and c["page"] > 1 else c["page"]
                outline.append({
                    "level": level,
                    "text": c["text"],
                    "page": adj_page
                })

    # Extract title
    if is_cover:
        title = extract_title_from_cover(all_lines, body_size)
    else:
        title = ""
        for line in all_lines:
            if line["page"] == 1 and line["size"] > body_size * 1.2 and line["text"] not in footers_to_ignore:
                title += line["text"] + " "
            elif title:
                break
        title = title.strip()

    # Sanitize the title
    cleaned = clean_title(title)
    if not cleaned:
        cleaned = clean_title(doc.metadata.get("title", "")) or (outline[0]["text"] if outline else "Untitled Document")
    title = cleaned

    return title, outline



def process_single_pdf(pdf_path, output_dir):
    try:
        with fitz.open(pdf_path) as doc:
            title, outline = analyze_document_structure(doc)
            output_data = {"title": title or pdf_path.stem, "outline": outline}
            output_file = output_dir / f"{pdf_path.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
        return f"✅ {pdf_path.name}"
    except Exception as e:
        return f"❌ {pdf_path.name}: {e}"

def main():
    input_dir = Path("./sample_dataset/pdfs")
    output_dir = Path("./sample_dataset/outputs")
    output_dir.mkdir(exist_ok=True)
    pdf_files = list(input_dir.glob("*.pdf"))

    with ProcessPoolExecutor() as executor:
        results = executor.map(process_single_pdf, pdf_files, [output_dir] * len(pdf_files))
        for result in results:
            print(result)

if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")
