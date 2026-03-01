import fitz  # PyMuPDF
import re
from io import BytesIO
from PIL import Image, ImageChops, ImageFilter
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = FastAPI()


# -------------------------------
# Embedded Frontend
# -------------------------------
HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Foodsby Label Generator</title>
<style>
body{font-family:sans-serif;background:#f3f4f6;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.card{background:#fff;padding:30px;border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.1);width:400px;text-align:center}
input{margin:15px 0}
button{padding:10px 20px;background:#4f46e5;color:#fff;border:none;border-radius:6px;cursor:pointer}
button:hover{opacity:.9}
</style>
</head>
<body>
<div class="card">
<h2>Foodsby Labels</h2>
<p>Generate A4 (4×2 grid)</p>
<input type="file" id="files" multiple accept="application/pdf"/>
<br/>
<button onclick="generate()">Generate PDF</button>
</div>

<script>
async function generate(){
    const files = document.getElementById("files").files;
    if(!files.length) return alert("Select PDF files");

    const formData = new FormData();
    for(const f of files){ formData.append("files", f); }

    const res = await fetch("/generate", {method:"POST", body:formData});
    if(!res.ok){
        const txt = await res.text();
        alert("Error: " + txt);
        return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "Foodsby_A4_Labels.pdf";
    a.click();
    URL.revokeObjectURL(url);
}
</script>
</body>
</html>
"""


# -------------------------------
# Auto Crop (Pillow Only) - Edge-based Aggressive Crop
# -------------------------------
def auto_crop(image: Image.Image) -> Image.Image:
    """
    Aggressive edge-based crop.
    Removes whitespace from all edges until content is found.
    """
    gray = image.convert("L")
    
    # Threshold: anything > 250 is whitespace
    pixels = gray.load()
    width, height = gray.size
    
    # Crop from top
    top = 0
    for y in range(height):
        has_content = False
        for x in range(width):
            if pixels[x, y] <= 250:  # Found non-white pixel
                has_content = True
                break
        if has_content:
            top = y
            break
    
    # Crop from bottom
    bottom = height
    for y in range(height - 1, -1, -1):
        has_content = False
        for x in range(width):
            if pixels[x, y] <= 250:
                has_content = True
                break
        if has_content:
            bottom = y + 1
            break
    
    # Crop from left
    left = 0
    for x in range(width):
        has_content = False
        for y in range(height):
            if pixels[x, y] <= 250:
                has_content = True
                break
        if has_content:
            left = x
            break
    
    # Crop from right
    right = width
    for x in range(width - 1, -1, -1):
        has_content = False
        for y in range(height):
            if pixels[x, y] <= 250:
                has_content = True
                break
        if has_content:
            right = x + 1
            break
    
    # Add minimal padding
    padding = 2
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(width, right + padding)
    bottom = min(height, bottom + padding)
    
    if left < right and top < bottom:
        return image.crop((left, top, right, bottom))
    
    return image


# -------------------------------
# Extract Labels
# -------------------------------
def extract_labels(pdf_bytes: bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    labels = []
    seen = set()

    for page in doc:
        text = page.get_text()
        match = re.search(r"Order\s*#\s*(\d+)", text)
        if not match:
            continue

        order_id = match.group(1)
        if order_id in seen:
            continue
        seen.add(order_id)

        # Find content bounds using text layout
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        
        top_y = None
        bottom_y = None
        
        for block in blocks:
            if block.get("type") != 0:  # Text blocks only
                continue
            
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    bbox = span.get("bbox", [])
                    
                    if not bbox:
                        continue
                    
                    # Track top
                    if top_y is None:
                        top_y = bbox[1]
                    
                    # Look for "Delivered by Vitality Bowls" to find bottom
                    if "Delivered by Vitality Bowls" in span_text or "Vitality" in span_text:
                        bottom_y = bbox[3]
        
        # Fallback
        if top_y is None:
            top_y = page.rect.y0
        if bottom_y is None:
            bottom_y = page.rect.y1
        
        # Tight crop bounds with padding
        top_y = max(page.rect.y0, top_y - 10)
        bottom_y = min(page.rect.y1, bottom_y + 10)
        
        # Render clipped region at 300 DPI
        clip_rect = fitz.Rect(page.rect.x0, top_y, page.rect.x1, bottom_y)
        mat = fitz.Matrix(300/72, 300/72)
        pix = page.get_pixmap(clip=clip_rect, matrix=mat)
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = auto_crop(img)
        labels.append(img)

    doc.close()
    return labels


# -------------------------------
# Generate A4 5x2 Layout (5 rows, 2 cols)
# -------------------------------
def build_a4(labels):
    buffer = BytesIO()
    page_w, page_h = A4
    rows, cols = 5, 2
    margin_lr = 15  # Left and right margin
    margin_tb = 10  # Top and bottom margin
    gutter = 8     # Space between columns

    usable_w = page_w - (2 * margin_lr) - gutter
    cell_w = usable_w / cols
    cell_h = (page_h - 2 * margin_tb) / rows

    c = canvas.Canvas(buffer, pagesize=A4)

    for i, img in enumerate(labels):
        if i % 10 == 0 and i != 0:
            c.showPage()

        row = (i % 10) // cols
        col = (i % 10) % cols

        # Position with proper margins and gutter
        if col == 0:
            x = margin_lr
        else:
            x = margin_lr + cell_w + gutter
        
        y = page_h - margin_tb - (row + 1) * cell_h

        iw, ih = img.size
        scale = min(cell_w / iw, cell_h / ih)

        new_w = iw * scale
        new_h = ih * scale

        x += (cell_w - new_w) / 2
        y += (cell_h - new_h) / 2

        c.drawInlineImage(img, x, y, new_w, new_h)

    c.save()
    buffer.seek(0)
    return buffer


# -------------------------------
# Routes
# -------------------------------
@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_CONTENT


@app.post("/generate")
async def generate(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    all_labels = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files allowed")

        pdf_bytes = await file.read()
        labels = extract_labels(pdf_bytes)
        all_labels.extend(labels)

    if not all_labels:
        raise HTTPException(status_code=400, detail="No valid labels detected")

    output = build_a4(all_labels)

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Foodsby_A4_Labels.pdf"}
    )