"""
app.py  —  Ranique Store Strip Stamper
---------------------------------------
POST /api/stamp   → Upload Meesho PDF + store link → returns stamped PDF
GET  /            → Serves the single-page UI
"""

import io
import logging
import os
from flask import Flask, request, jsonify, send_file, send_from_directory
from store_overlay import add_store_strip

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024   # 30 MB

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/stamp', methods=['POST'])
def api_stamp():
    """
    Accepts multipart/form-data with:
      - pdf        : the Meesho label PDF
      - store_link : URL to encode in QR (e.g. Instagram, WhatsApp, website)
      - store_name : (optional) display name — default "RANIQUE LIFESTYLE"

    Returns the modified PDF as a download.
    """
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF uploaded. Use field name "pdf".'}), 400

    file = request.files['pdf']
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Please upload a valid PDF file.'}), 400

    store_link = (request.form.get('store_link') or '').strip()
    if not store_link:
        return jsonify({'error': 'store_link is required.'}), 400

    store_name = (request.form.get('store_name') or 'RANIQUE LIFESTYLE').strip()
    convert_4x6 = request.form.get('convert_4x6', 'false').lower() == 'true'
    shop_icon = (request.form.get('shop_icon') or 'shop').strip()

    pdf_bytes = file.read()
    log.info('Stamping PDF (%d bytes) with link=%s name=%s convert_4x6=%s icon=%s',
             len(pdf_bytes), store_link, store_name, convert_4x6, shop_icon)

    try:
        result = add_store_strip(pdf_bytes, store_link, store_name, convert_4x6=convert_4x6, shop_icon=shop_icon)
    except Exception as exc:
        log.exception('Overlay failed')
        return jsonify({'error': f'Failed to add store strip: {exc}'}), 500

    log.info('Done. Output: %d bytes', len(result))
    return send_file(
        io.BytesIO(result),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='ranique_label.pdf',
    )


@app.route('/api/verify-address', methods=['POST'])
def api_verify_address():
    """
    Accepts EITHER:
      - JSON body: { "address": "..." }
      - Multipart form-data: upload a file (PDF, PNG, JPG)
    Extracts text, isolates shipping address + courier hub, and verifies it.
    Returns a list of verification reports (one report per page for PDFs).
    """
    from address_verifier import (
        verify_indian_address, 
        run_local_ocr, 
        extract_address_and_hub
    )
    import pymupdf as fitz

    # A. Check for file upload
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            filename = file.filename.lower()
            
            if filename.endswith('.pdf'):
                pdf_bytes = file.read()
                page_num_str = request.form.get('page_num')
                reports = []
                try:
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    if len(doc) == 0:
                        return jsonify({'error': 'The uploaded PDF has no pages.'}), 400
                    
                    if page_num_str is not None:
                        page_idx = int(page_num_str)
                        if page_idx < 0 or page_idx >= len(doc):
                            return jsonify({'error': f'Invalid page_num: {page_idx}'}), 400
                        pages_to_process = [(page_idx, doc[page_idx])]
                    else:
                        pages_to_process = list(enumerate(doc))
                    
                    for page_num, page in pages_to_process:
                        page_text = page.get_text() or ""
                        # If page text is completely empty (scanned image PDF page)
                        if not page_text.strip():
                            log.info("Page %d has no vector text. Attempting OCR...", page_num + 1)
                            os.makedirs('temp', exist_ok=True)
                            temp_path = os.path.join('temp', f"ocr_page_{page_num}_{file.filename}.png")
                            try:
                                pix = page.get_pixmap(dpi=150)
                                pix.save(temp_path)
                                page_text = run_local_ocr(temp_path)
                            except Exception as ocr_err:
                                log.error("OCR rendering/processing failed for page %d: %s", page_num + 1, ocr_err)
                            finally:
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)

                        address_to_verify, delivery_hub, courier_name = extract_address_and_hub(page_text)
                        
                        # Verify this specific address
                        report = verify_indian_address(address_to_verify)
                        report['file_used'] = True
                        report['extracted_text'] = page_text
                        report['delivery_hub'] = delivery_hub
                        report['courier_name'] = courier_name
                        reports.append(report)
                        
                    return jsonify(reports)
                except Exception as doc_err:
                    log.exception("Failed to parse PDF document")
                    return jsonify({'error': f'Failed to parse PDF document: {doc_err}'}), 500
            
            elif filename.endswith(('.png', '.jpg', '.jpeg')):
                # Image local OCR using Windows Engine
                os.makedirs('temp', exist_ok=True)
                temp_path = os.path.join('temp', f"ocr_{file.filename}")
                file.save(temp_path)
                try:
                    extracted_text = run_local_ocr(temp_path)
                    address_to_verify, delivery_hub, courier_name = extract_address_and_hub(extracted_text)
                    report = verify_indian_address(address_to_verify)
                    report['file_used'] = True
                    report['extracted_text'] = extracted_text
                    report['delivery_hub'] = delivery_hub
                    report['courier_name'] = courier_name
                    return jsonify([report])  # Return as list of size 1
                except Exception as img_err:
                    log.exception("Image OCR process failed")
                    return jsonify({'error': f'Failed to process image: {img_err}'}), 500
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                return jsonify({'error': 'Unsupported file type. Upload PDF, PNG, or JPG.'}), 400
    else:
        # B. Check for JSON input
        data = request.get_json() or {}
        address_to_verify = data.get('address', '').strip()
        if not address_to_verify:
            return jsonify({'error': 'Please provide an address or upload a label file.'}), 400

        try:
            report = verify_indian_address(address_to_verify)
            report['file_used'] = False
            report['extracted_text'] = address_to_verify
            report['delivery_hub'] = "Standard Delivery Hub"
            report['courier_name'] = "Standard Courier"
            return jsonify([report])  # Return as list of size 1
        except Exception as exc:
            log.exception('Address verification failed')
            return jsonify({'error': f'Verification failed: {exc}'}), 500


if __name__ == '__main__':
    print('\n' + '=' * 50)
    print('  Ranique Store Strip Stamper')
    print('  http://localhost:5000')
    print('=' * 50 + '\n')
    app.run(debug=True, host='0.0.0.0', port=5000)
