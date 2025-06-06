import os
import gc
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import pytesseract
import uuid

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

def extract_text_tesseract(image_path):
    """Extract text using Tesseract OCR"""
    try:
        # Open and optimize image
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize if too large
            max_size = (1200, 1200)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Extract text using Tesseract
            text = pytesseract.image_to_string(img, config='--psm 6')
            
        gc.collect()
        return text.strip()
        
    except Exception as e:
        gc.collect()
        raise Exception(f"OCR processing failed: {str(e)}")

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "TextExtract OCR API (Tesseract) is running!",
        "status": "active",
        "engine": "tesseract"
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            return jsonify({'error': 'Invalid file type. Please upload an image.'}), 400
        
        unique_filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(file_path)
        
        try:
            raw_text = extract_text_tesseract(file_path)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            gc.collect()
            
            return jsonify({
                'success': True,
                'text': raw_text,
                'message': 'Text extracted successfully'
            })
            
        except Exception as ocr_error:
            if os.path.exists(file_path):
                os.remove(file_path)
            gc.collect()
            return jsonify({'error': str(ocr_error)}), 500
            
    except Exception as e:
        gc.collect()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
