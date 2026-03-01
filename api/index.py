import fitz  # PyMuPDF
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageChops
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = FastAPI()

# HTML Frontend (embedded)
HTML_CONTENT = """
<!DOCTYPE html>
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
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
            max-width: 500px;
            width: 100%;
        }

        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }

        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .upload-zone {
            border: 2px dashed #667eea;
            border-radius: 8px;
            padding: 40px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f8f9ff;
        }

        .upload-zone:hover {
            border-color: #764ba2;
            background: #f0f2ff;
        }

        .upload-zone.dragover {
            border-color: #764ba2;
            background: #e8ebff;
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 48px;
            margin-bottom: 10px;
        }

        .upload-text {
            color: #333;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .upload-hint {
            color: #999;
            font-size: 13px;
        }

        #fileInput {
            display: none;
        }

        .file-list {
            margin-top: 20px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 6px;
            max-height: 150px;
            overflow-y: auto;
        }

        .file-item {
            padding: 8px 0;
            color: #666;
            font-size: 13px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .file-item:last-child {
            border-bottom: none;
        }

        .file-size {
            color: #999;
            font-size: 12px;
        }

        .button-group {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 30px;
        }

        button {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .btn-generate {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            grid-column: 1 / 2;
        }

        .btn-generate:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }

        .btn-generate:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-clear {
            background: #e0e0e0;
            color: #333;
            grid-column: 2 / 3;
        }

        .btn-clear:hover {
            background: #d0d0d0;
        }

        .loading {
            display: none;
            margin-top: 20px;
            text-align: center;
        }

        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .loading-text {
            color: #666;
            font-size: 14px;
        }

        .message {
            margin-top: 20px;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
            font-size: 13px;
        }

        .message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .empty-state {
            color: #999;
            font-size: 13px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Foodsby Labels</h1>
        <p class="subtitle">Generate print-ready A4 PDF (4×2 grid)</p>

        <div class="upload-zone" id="uploadZone">
            <div class="upload-icon">📄</div>
            <div class="upload-text">Drop PDFs here or click to select</div>
            <div class="upload-hint">Each PDF page = 1 label with Order #</div>
            <input type="file" id="fileInput" multiple accept=".pdf,application/pdf">
        </div>

        <div class="file-list" id="fileList">
            <div class="empty-state">No files selected</div>
        </div>

        <div class="button-group">
            <button class="btn-generate" id="generateBtn" disabled>Generate PDF</button>
            <button class="btn-clear" id="clearBtn">Clear</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div class="loading-text">Processing labels...</div>
        </div>

        <div class="message" id="message"></div>
    </div>

    <script>
        let selectedFiles = [];
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        const generateBtn = document.getElementById('generateBtn');
        const clearBtn = document.getElementById('clearBtn');
        const loading = document.getElementById('loading');
        const message = document.getElementById('message');

        // Upload zone click
        uploadZone.addEventListener('click', () => fileInput.click());

        // File selection
        fileInput.addEventListener('change', (e) => {
            selectedFiles = Array.from(e.target.files);
            updateFileList();
        });

        // Drag and drop
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            selectedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
            updateFileList();
        });

        // Update file list display
        function updateFileList() {
            generateBtn.disabled = selectedFiles.length === 0;

            if (selectedFiles.length === 0) {
                fileList.innerHTML = '<div class="empty-state">No files selected</div>';
                return;
            }

            fileList.innerHTML = selectedFiles
                .map(file => {
                    const sizeMB = (file.size / 1024 / 1024).toFixed(2);
                    return `
                        <div class="file-item">
                            <span>📄 ${file.name}</span>
                            <span class="file-size">${sizeMB} MB</span>
                        </div>
                    `;
                })
                .join('');
        }

        // Clear files
        clearBtn.addEventListener('click', () => {
            selectedFiles = [];
            fileInput.value = '';
            updateFileList();
            message.innerHTML = '';
        });

        // Generate PDF
        generateBtn.addEventListener('click', async () => {
            if (selectedFiles.length === 0) return;

            const formData = new FormData();
            selectedFiles.forEach(file => formData.append('files', file));

            loading.style.display = 'block';
            message.innerHTML = '';
            generateBtn.disabled = true;

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    const error = await response.text();
                    throw new Error(error || 'Failed to generate PDF');
                }

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'Foodsby_A4_Labels.pdf';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();

                message.className = 'message success';
                message.textContent = '✓ PDF downloaded successfully!';

                selectedFiles = [];
                fileInput.value = '';
                updateFileList();
            } catch (error) {
                message.className = 'message error';
                message.textContent = '✗ Error: ' + error.message;
                generateBtn.disabled = false;
            } finally {
                loading.style.display = 'none';
            }
        });

        // Update file input when fileList changes
        fileInput.addEventListener('change', updateFileList);
    </script>
</body>
</html>
"""


def auto_crop_pillow(image: Image.Image, padding: int = 30) -> Image.Image:
    """
    Auto-crop whitespace using Pillow only (no OpenCV, no numpy).
    
    This function finds the non-white content area and crops the image
    with optional padding.
    """
    # Convert to grayscale if needed
    if image.mode != 'L':
        gray = image.convert('L')
    else:
        gray = image
    
    # Invert (make white pixels black, non-white pixels white)
    inverted = ImageChops.invert(gray)
    
    # Apply threshold to get binary image (anything darker than 240 becomes white)
    # We use a threshold to define "white" as pixels > 240
    alpha = inverted.point(lambda x: 255 if x > 15 else 0)  # 15 is roughly inverse of 240
    
    # Find bounding box of non-white areas
    bbox = alpha.getbbox()
    
    if bbox is None:
        # No content found, return original
        return image
    
    # Add padding
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    
    # Crop
    return image.crop((left, top, right, bottom))


def extract_labels_from_pdf_bytes(pdf_bytes: bytes) -> list[tuple[Image.Image, str]]:
    """
    Extract labels from PDF in memory.
    
    Returns: list of (Image, order_id) tuples
    """
    pdf_stream = BytesIO(pdf_bytes)
    doc = fitz.open(stream=pdf_stream, filetype="pdf")
    
    labels = []
    seen_orders = set()
    
    for page_num, page in enumerate(doc):
        # Extract text to find Order ID
        text = page.get_text()
        
        # Find Order # using regex
        order_match = re.search(r'Order\s*#\s*(\d+)', text)
        if not order_match:
            continue
        
        order_id = f"Order #{order_match.group(1)}"
        
        # Deduplicate
        if order_id in seen_orders:
            continue
        
        seen_orders.add(order_id)
        
        # Find content bounding box using text positions
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        
        top_anchor = None
        bottom_anchor = None
        
        for block in blocks:
            if block.get("type") != 0:  # Only text blocks
                continue
            
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text_content = span.get("text", "")
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    
                    if top_anchor is None:
                        top_anchor = bbox[1]
                    
                    # Look for "Vitality" as end marker
                    if "Vitality" in text_content:
                        bottom_anchor = bbox[3]
        
        # Fallback if markers not found
        if top_anchor is None:
            top_anchor = page.rect.y0
        if bottom_anchor is None:
            bottom_anchor = page.rect.y1 - 80
        
        # Add margins
        top_anchor = max(page.rect.y0, top_anchor - 20)
        bottom_anchor = min(page.rect.y1, bottom_anchor + 20)
        
        # Render page at 300 DPI
        clip_rect = fitz.Rect(
            page.rect.x0,
            top_anchor,
            page.rect.x1,
            bottom_anchor
        )
        
        mat = fitz.Matrix(300/72, 300/72)  # Convert points to 300 DPI
        pix = page.get_pixmap(clip=clip_rect, matrix=mat)
        
        # Convert pixmap to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Auto-crop whitespace
        img = auto_crop_pillow(img, padding=30)
        
        labels.append((img, order_id))
    
    doc.close()
    return labels


def create_a4_pdf_4x2(labels: list[Image.Image]) -> BytesIO:
    """
    Create A4 PDF with 4 rows × 2 columns layout.
    
    Returns: BytesIO buffer with PDF data
    """
    buffer = BytesIO()
    page_w, page_h = A4
    rows, cols = 4, 2
    margin = 20
    
    cell_w = (page_w - 2 * margin) / cols
    cell_h = (page_h - 2 * margin) / rows
    
    c = canvas.Canvas(buffer, pagesize=A4)
    
    for i, img in enumerate(labels):
        # Create new page every 8 labels (4x2 grid)
        if i % 8 == 0 and i != 0:
            c.showPage()
        
        # Calculate position
        row = (i % 8) // cols
        col = (i % 8) % cols
        
        x = margin + col * cell_w
        y = page_h - margin - (row + 1) * cell_h
        
        # Calculate scaling to fit cell while preserving aspect ratio
        img_w, img_h = img.size
        scale = min(cell_w / img_w, cell_h / img_h)
        new_w = img_w * scale
        new_h = img_h * scale
        
        # Center image in cell
        x_centered = x + (cell_w - new_w) / 2
        y_centered = y + (cell_h - new_h) / 2
        
        c.drawInlineImage(img, x_centered, y_centered, width=new_w, height=new_h)
    
    c.save()
    buffer.seek(0)
    return buffer


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the HTML frontend."""
    return HTML_CONTENT


@app.post("/generate")
async def generate_pdf(files: list[UploadFile] = File(...)):
    """
    Generate A4 PDF from uploaded Foodsby PDF files.
    
    - Accepts multiple PDFs via multipart/form-data
    - Each PDF page = one label with "Order #XXXXXX"
    - Returns print-ready A4 PDF (4×2 grid)
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    all_labels = []
    
    # Process each uploaded file
    for file in files:
        if file.content_type != "application/pdf" and not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file.filename}")
        
        try:
            # Read file content into memory
            pdf_bytes = await file.read()
            
            # Extract labels
            labels = extract_labels_from_pdf_bytes(pdf_bytes)
            all_labels.extend([img for img, _ in labels])
        
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing {file.filename}: {str(e)}")
    
    if not all_labels:
        raise HTTPException(status_code=400, detail="No valid labels found in PDFs. Each label must contain 'Order #XXXXXX'.")
    
    # Generate PDF
    try:
        output_pdf = create_a4_pdf_4x2(all_labels)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
    
    # Return as streaming response
    return StreamingResponse(
        iter([output_pdf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Foodsby_A4_Labels.pdf"}
    )
