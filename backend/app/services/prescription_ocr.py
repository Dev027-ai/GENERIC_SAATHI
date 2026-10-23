"""Best-effort OCR adapter for prescription images. Does not interpret or prescribe."""
from io import BytesIO

def extract_prescription_text(data: bytes, content_type: str) -> dict:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("Prescription OCR is not configured. Install Pillow and pytesseract, and install the Tesseract OCR engine on this computer.") from exc
    try:
        if content_type == "application/pdf":
            try:
                from pdf2image import convert_from_bytes
            except ImportError as exc:
                raise RuntimeError("PDF OCR requires pdf2image and Poppler. For now, upload a prescription image (JPG or PNG).") from exc
            pages = convert_from_bytes(data, first_page=1, last_page=3)
            text = "\n\n".join(pytesseract.image_to_string(page) for page in pages)
        else:
            image = Image.open(BytesIO(data)).convert("RGB")
            text = pytesseract.image_to_string(image)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Could not read this file. Try a clearer, well-lit image with the full prescription visible.") from exc
    return {"extracted_text": text.strip(), "review_required": True, "engine": "Tesseract OCR", "saved": False}
