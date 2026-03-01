# Foodsby Label Generator - Vercel API

A production-ready FastAPI serverless application that generates print-ready A4 PDFs from Foodsby label PDFs.

## Features

✓ FastAPI serverless (Vercel-compatible)  
✓ Upload multiple Foodsby PDF files  
✓ Auto-detect labels using "Order #XXXXXX"  
✓ Deduplicate labels automatically  
✓ Auto-crop whitespace (Pillow-only, no OpenCV)  
✓ Generate A4 PDF in 4×2 grid layout  
✓ Modern drag-and-drop UI  
✓ Fully in-memory processing (no disk I/O)  
✓ Production-optimized

## Project Structure

```
.
├── api/
│   └── index.py          (FastAPI app + embedded HTML)
├── requirements.txt      (Dependencies)
├── vercel.json          (Vercel configuration)
└── README.md
```

## Local Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Locally

```bash
uvicorn api.index:app --reload
```

Visit `http://localhost:8000` in your browser.

### Test the API

```bash
# Upload PDF files
curl -X POST http://localhost:8000/generate \
  -F "files=@label1.pdf" \
  -F "files=@label2.pdf" \
  -o output.pdf
```

## Deployment to Vercel

### Prerequisites

- Vercel CLI: `npm i -g vercel`
- Git repository

### Deploy

```bash
vercel
```

The app will be deployed at `https://your-project.vercel.app`

## API Endpoints

### GET /

Serves the HTML upload interface.

### POST /generate

Generates print-ready A4 PDF from uploaded Foodsby PDFs.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Parameter: `files` (multiple PDF files)

**Returns:**
- Content-Type: `application/pdf`
- Attachment: `Foodsby_A4_Labels.pdf`

**Example:**
```bash
curl -X POST https://your-project.vercel.app/generate \
  -F "files=@order1.pdf" \
  -F "files=@order2.pdf" \
  --output labels.pdf
```

## How It Works

1. **Upload PDFs** - Users select or drag-drop Foodsby PDF files
2. **Extract Labels** - Each PDF page is rendered as an image at 300 DPI
3. **Detect Order IDs** - Regex finds "Order #XXXXXX" text in each label
4. **Deduplicate** - Labels with duplicate Order IDs are removed
5. **Auto-Crop** - Whitespace is removed from each label image
6. **Generate PDF** - Labels are arranged in 4×2 A4 grid with aspect ratio preserved
7. **Download** - User receives the print-ready PDF

## Technical Details

- **Memory-Efficient**: All processing happens in-memory using BytesIO
- **No OpenCV**: Uses Pillow only for image processing
- **No NumPy**: All array operations use Python standard library
- **Vercel Compatible**: Works with Python serverless runtime
- **300 DPI**: Labels render at high quality for printing
- **Pillow Auto-Crop**: Smart whitespace removal without external dependencies

## Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `PyMuPDF` - PDF processing and rendering
- `Pillow` - Image processing
- `reportlab` - PDF generation
- `python-multipart` - File upload handling

## License

MIT