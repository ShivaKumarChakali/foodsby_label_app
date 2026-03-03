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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Foodsby Label Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 50px 40px;
            max-width: 450px;
            width: 100%;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        
        .logo {
            font-size: 48px;
            margin-bottom: 16px;
            display: block;
            animation: bounce 2s infinite;
        }
        
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-8px); }
        }
        
        h1 {
            color: #1f2937;
            font-size: 32px;
            margin-bottom: 8px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }
        
        .tagline {
            color: #6b7280;
            font-size: 16px;
            margin-bottom: 40px;
            font-weight: 400;
            line-height: 1.6;
        }
        
        .upload-area {
            border: 2px dashed #d1d5db;
            border-radius: 12px;
            padding: 40px 20px;
            margin-bottom: 24px;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f9fafb;
        }
        
        .upload-area:hover {
            border-color: #667eea;
            background: #f3f4f8;
        }
        
        .upload-area.dragover {
            border-color: #667eea;
            background: #ede9fe;
            transform: scale(1.02);
        }
        
        .upload-icon {
            font-size: 40px;
            margin-bottom: 12px;
            display: block;
        }
        
        .upload-text {
            color: #1f2937;
            font-weight: 600;
            margin-bottom: 6px;
            font-size: 15px;
        }
        
        .upload-hint {
            color: #9ca3af;
            font-size: 13px;
        }
        
        #fileInput {
            display: none;
        }
        
        .file-list {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 24px;
            max-height: 120px;
            overflow-y: auto;
        }
        
        .file-item {
            background: white;
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 13px;
            color: #374151;
        }
        
        .file-item:last-child {
            margin-bottom: 0;
        }
        
        .file-name {
            flex: 1;
            text-align: left;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .empty-state {
            color: #9ca3af;
            font-size: 13px;
            padding: 8px;
        }
        
        .button-group {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-top: 30px;
        }
        
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            letter-spacing: 0.3px;
        }
        
        .btn-generate {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            grid-column: 1 / 2;
        }
        
        .btn-generate:hover:not(:disabled) {
            background: linear-gradient(135deg, #5567d8 0%, #6a3f94 100%);
            transform: translateY(-2px);
        }
        
        .btn-generate:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-clear {
            background: #e5e7eb;
            color: #374151;
            grid-column: 2 / 3;
        }
        
        .btn-clear:hover {
            background: #d1d5db;
        }
        
        .status {
            margin-top: 20px;
            padding: 12px;
            border-radius: 8px;
            font-size: 13px;
            min-height: 16px;
            display: none;
        }
        
        .status.show {
            display: block;
        }
        
        .status.loading {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .status.success {
            background: #dcfce7;
            color: #15803d;
        }
        
        .status.error {
            background: #fee2e2;
            color: #b91c1c;
        }
        
        .spinner {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid rgba(0,0,0,.1);
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 0.8s linear infinite;
            margin-right: 6px;
            vertical-align: middle;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <span class="logo">📋</span>
        <h1>Foodsby Labels</h1>
        <p class="tagline">Generate print-ready A4 PDFs instantly</p>
        
        <div class="upload-area" id="uploadArea">
            <span class="upload-icon">📄</span>
            <p class="upload-text">Drop your PDFs here</p>
            <p class="upload-hint">or click to select files</p>
        </div>
        
        <div class="file-list" id="fileList">
            <div class="empty-state">No files selected</div>
        </div>
        
        <input type="file" id="fileInput" accept=".pdf" multiple style="display: none;">
        
        <div class="button-group">
            <button class="btn-generate" id="generateBtn" disabled>Generate PDF</button>
            <button class="btn-clear" id="clearBtn">Clear All</button>
        </div>
        
        <div class="status" id="status"></div>
    </div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        const generateBtn = document.getElementById('generateBtn');
        const clearBtn = document.getElementById('clearBtn');
        const status = document.getElementById('status');
        
        let selectedFiles = [];
        
        // Click to upload
        uploadArea.addEventListener('click', () => fileInput.click());
        
        // File selection
        fileInput.addEventListener('change', (e) => {
            selectedFiles = Array.from(e.target.files);
            updateFileList();
        });
        
        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            selectedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
            fileInput.files = e.dataTransfer.files;
            updateFileList();
        });
        
        // Update file list
        function updateFileList() {
            generateBtn.disabled = selectedFiles.length === 0;
            
            if (selectedFiles.length === 0) {
                fileList.innerHTML = '<div class="empty-state">No files selected</div>';
                return;
            }
            
            fileList.innerHTML = selectedFiles.map((file, i) => {
                const sizeMB = (file.size / 1024 / 1024).toFixed(2);
                return `
                    <div class="file-item">
                        <span class="file-name">📄 ${file.name}</span>
                        <span style="color: #9ca3af; font-size: 12px;">${sizeMB}MB</span>
                    </div>
                `;
            }).join('');
        }
        
        // Clear
        clearBtn.addEventListener('click', () => {
            selectedFiles = [];
            fileInput.value = '';
            status.classList.remove('show');
            updateFileList();
        });
        
        // Generate
        generateBtn.addEventListener('click', async () => {
            if (selectedFiles.length === 0) return;
            
            generateBtn.disabled = true;
            showStatus('loading', '<span class="spinner"></span>Processing your labels...');
            
            try {
                const formData = new FormData();
                selectedFiles.forEach(file => formData.append('files', file));
                
                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error('Failed to generate PDF');
                }
                
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'Foodsby_A4_Labels.pdf';
                document.body.appendChild(a);
                a.click();
                URL.revokeObjectURL(url);
                a.remove();
                
                showStatus('success', '✓ PDF downloaded successfully!');
                selectedFiles = [];
                fileInput.value = '';
                updateFileList();
            } catch (error) {
                showStatus('error', '✗ Error: ' + error.message);
            } finally {
                generateBtn.disabled = selectedFiles.length === 0;
            }
        });
        
        function showStatus(type, message) {
            status.className = `status ${type} show`;
            status.innerHTML = message;
            
            if (type !== 'loading') {
                setTimeout(() => status.classList.remove('show'), 3000);
            }
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

    for page in doc:
        text = page.get_text()
        match = re.search(r"Order\s*#\s*(\d+)", text)
        if not match:
            continue

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
    margin_lr = 5   # Left and right margin (reduced to move left column more left)
    margin_tb = 10  # Top and bottom margin
    gutter = 25     # Space between columns (increased for better separation)

    usable_w = page_w - (2 * margin_lr) - gutter
    cell_w = usable_w / cols
    cell_h = (page_h - 2 * margin_tb) / rows

    c = canvas.Canvas(buffer, pagesize=A4)
    labels_per_page = rows * cols  # 10 labels per page

    for i, img in enumerate(labels):
        # Start a new page when needed (but not on the first label)
        if i > 0 and i % labels_per_page == 0:
            c.showPage()

        # Calculate position within current page
        position_on_page = i % labels_per_page
        row = position_on_page // cols
        col = position_on_page % cols

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