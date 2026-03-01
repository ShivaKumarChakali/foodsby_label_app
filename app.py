import os
import fitz  # PyMuPDF
import numpy as np
import cv2
from PIL import Image
from flask import Flask, render_template, request, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
from io import BytesIO

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------
# Smart Auto-Crop Function (Image Based)
# ---------------------------------------------------
# def smart_crop(image_np):
#     gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)

#     # Invert white background
#     _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

#     coords = cv2.findNonZero(thresh)
#     if coords is None:
#         return image_np

#     x, y, w, h = cv2.boundingRect(coords)

#     # Add padding
#     pad = 25
#     x = max(0, x - pad)
#     y = max(0, y - pad)
#     w = min(image_np.shape[1] - x, w + pad * 2)
#     h = min(image_np.shape[0] - y, h + pad * 2)

#     return image_np[y:y + h, x:x + w]

def smart_crop(image_np):
    gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold (better than fixed 240)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        51, 5
    )

    # Morph close to connect text areas
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return image_np

    # Find largest contour (main content block)
    largest = max(contours, key=cv2.contourArea)

    x, y, w, h = cv2.boundingRect(largest)

    # Add padding
    pad = 30
    x = max(0, x - pad)
    y = max(0, y - pad)
    w = min(image_np.shape[1] - x, w + pad * 2)
    h = min(image_np.shape[0] - y, h + pad * 2)

    return image_np[y:y+h, x:x+w]


# ---------------------------------------------------
# Extract Labels (1 label per page assumption)
# ---------------------------------------------------
def extract_labels_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    labels = []
    seen_orders = set()

    for page in doc:
        text = page.get_text()

        # Must contain an Order #
        order_id = None
        for line in text.split("\n"):
            if "Order #" in line:
                order_id = line.strip()
                break

        if not order_id:
            continue

        if order_id in seen_orders:
            continue

        seen_orders.add(order_id)

        # Now find bottom of content using text positions
        text_dict = page.get_text("dict")
        blocks = text_dict["blocks"]

        top_anchor = None
        bottom_anchor = None

        for block in blocks:
            if block["type"] != 0:
                continue

            for line in block["lines"]:
                for span in line["spans"]:

                    if top_anchor is None:
                        top_anchor = span["bbox"][1]

                    if "Vitality" in span["text"]:
                        bottom_anchor = span["bbox"][3]

        if not bottom_anchor:
            bottom_anchor = page.rect.y1 - 80

        rect = page.rect

        clip_rect = fitz.Rect(
            rect.x0,
            top_anchor - 20,
            rect.x1,
            bottom_anchor + 20
        )

        pix = page.get_pixmap(clip=clip_rect, dpi=300)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        labels.append(img)

    return labels


# ---------------------------------------------------
# Generate A4 5x2 Layout
# ---------------------------------------------------
def create_a4_pdf(labels):
    buffer = BytesIO()
    page_w, page_h = A4
    rows, cols = 5, 2
    margin = 20

    cell_w = (page_w - 2 * margin) / cols
    cell_h = (page_h - 2 * margin) / rows

    c = canvas.Canvas(buffer, pagesize=A4)

    for i, img in enumerate(labels):

        if i % 10 == 0 and i != 0:
            c.showPage()

        row = (i % 10) // cols
        col = (i % 10) % cols

        x = margin + col * cell_w
        y = page_h - margin - (row + 1) * cell_h

        iw, ih = img.size

        scale = min(cell_w / iw, cell_h / ih)
        new_w = iw * scale
        new_h = ih * scale

        x_centered = x + (cell_w - new_w) / 2
        y_centered = y + (cell_h - new_h) / 2

        c.drawInlineImage(img, x_centered, y_centered, width=new_w, height=new_h)

    c.save()
    buffer.seek(0)
    return buffer


# ---------------------------------------------------
# Flask Route
# ---------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        files = request.files.getlist("files")
        all_labels = []

        for file in files:
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            labels = extract_labels_from_pdf(path)
            all_labels.extend(labels)

        if not all_labels:
            return "No valid Foodsby labels detected."

        output_pdf = create_a4_pdf(all_labels)

        return send_file(
            output_pdf,
            as_attachment=True,
            download_name="Foodsby_A4_5x2_Print.pdf",
            mimetype="application/pdf"
        )

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)