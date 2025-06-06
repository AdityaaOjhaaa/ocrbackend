import os
import gc
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import easyocr
import uuid

# Initialize Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, origins=['*'], methods=['GET', 'POST', 'OPTIONS'])

# Global reader variable - lazy initialization
reader = None

UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024  # Reduced to 3MB

def get_reader():
    """Ultra-lightweight EasyOCR initialization"""
    global reader
    if reader is None:
        try:
            # Minimal EasyOCR configuration for memory efficiency
            reader = easyocr.Reader(['en'], 
                                  gpu=False, 
                                  verbose=False,
                                  quantize=True,  # Reduces model size
                                  width_ths=0.9,  # More aggressive text detection
                                  height_ths=0.9)
            gc.collect()
        except Exception as e:
            print(f"EasyOCR init failed: {e}")
            return None
    return reader

def extract_text(image_path):
    """Memory-optimized text extraction"""
    try:
        # Aggressive image compression
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Very small size to reduce memory
            max_size = (400, 400)  # Much smaller
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img.save(image_path, optimize=True, quality=60)  # Lower quality
        
        ocr_reader = get_reader()
        if ocr_reader is None:
            return "OCR initialization failed"
        
        # Process with minimal settings
        result = ocr_reader.readtext(image_path, 
                                   detail=0, 
                                   paragraph=False,
                                   width_ths=0.9,
                                   height_ths=0.9)
        
        gc.collect()  # Immediate cleanup
        return " ".join(result) if result else "No text detected"
        
    except Exception as e:
        gc.collect()
        return f"Processing failed: {str(e)}"

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({'status': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "OCR API Running",
        "status": "active",
        "memory": "optimized"
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return jsonify({'error': 'Only PNG, JPG, JPEG allowed'}), 400
        
        # Save file
        unique_filename = str(uuid.uuid4()) + '.jpg'  # Always save as JPG
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        try:
            # Extract text
            text = extract_text(file_path)
            
            # Immediate cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
            gc.collect()
            
            return jsonify({
                'success': True,
                'text': text,
                'message': 'Processed successfully'
            })
            
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            gc.collect()
            return jsonify({'error': f'Processing error: {str(e)}'}), 500
            
    except Exception as e:
        gc.collect()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
