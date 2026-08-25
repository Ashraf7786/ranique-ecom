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

    pdf_bytes = file.read()
    log.info('Stamping PDF (%d bytes) with link=%s name=%s convert_4x6=%s',
             len(pdf_bytes), store_link, store_name, convert_4x6)

    try:
        result = add_store_strip(pdf_bytes, store_link, store_name, convert_4x6=convert_4x6)
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
    """
    from address_verifier import (
        verify_indian_address, 
        extract_text_from_pdf, 
        run_local_ocr, 
        extract_address_and_hub
    )

    address_to_verify = ""
    extracted_text = ""
    delivery_hub = "Standard Delivery Hub"
    courier_name = "Standard Courier"
    file_used = False

    # A. Check for file upload
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            file_used = True
            filename = file.filename.lower()
            
            if filename.endswith('.pdf'):
                # PDF Text Extraction
                pdf_bytes = file.read()
                extracted_text = extract_text_from_pdf(pdf_bytes)
            elif filename.endswith(('.png', '.jpg', '.jpeg')):
                # Image local OCR using Windows Engine
                os.makedirs('temp', exist_ok=True)
                temp_path = os.path.join('temp', f"ocr_{file.filename}")
                file.save(temp_path)
                try:
                    extracted_text = run_local_ocr(temp_path)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                return jsonify({'error': 'Unsupported file type. Upload PDF, PNG, or JPG.'}), 400

            # Parse extracted text for address and routing info
            address_to_verify, delivery_hub, courier_name = extract_address_and_hub(extracted_text)
            if not address_to_verify.strip():
                return jsonify({
                    'error': 'Could not extract any readable address text from the uploaded document.'
                }), 400
    else:
        # B. Check for JSON input
        data = request.get_json() or {}
        address_to_verify = data.get('address', '').strip()
        if not address_to_verify:
            return jsonify({'error': 'Please provide an address or upload a label file.'}), 400

    try:
        report = verify_indian_address(address_to_verify)
        # Enrich report with parsing info if file was uploaded
        report['file_used'] = file_used
        report['extracted_text'] = extracted_text
        report['delivery_hub'] = delivery_hub
        report['courier_name'] = courier_name
        return jsonify(report)
    except Exception as exc:
        log.exception('Address verification failed')
        return jsonify({'error': f'Verification failed: {exc}'}), 500


if __name__ == '__main__':
    print('\n' + '=' * 50)
    print('  Ranique Store Strip Stamper')
    print('  http://localhost:5000')
    print('=' * 50 + '\n')
    app.run(debug=True, host='0.0.0.0', port=5000)
