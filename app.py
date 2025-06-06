import os
import gc
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import easyocr
import uuid
import threading
import time

# Initialize Flask app
app = Flask(__name__)

# Configure CORS with your exact frontend URL
CORS(app, 
     origins=['https://adityaaojhaaa.github.io', 'https://adityaaojhaaa.github.io/ocrfrontend/', '*'],
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'])

# Global reader variable - initialize only once
reader = None
reader_lock = threading.Lock()

UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Reduced to 5MB

def initialize_reader():
    """Initialize EasyOCR reader with memory optimization"""
    global reader
    with reader_lock:
        if reader is None:
            try:
                print("Initializing EasyOCR reader...")
                # Use minimal configuration to reduce memory usage
                reader = easyocr.Reader(['en'], 
                                      gpu=False, 
                                      verbose=False,
                                      download_enabled=True,
                                      detector=True,
                                      recognizer=True)
                print("EasyOCR reader initialized successfully")
                gc.collect()  # Force garbage collection
            except Exception as e:
                print(f"Failed to initialize EasyOCR: {e}")
                reader = None
    return reader

def extract_text(image_path):
    """Extract text with aggressive memory management"""
    try:
        # Compress image aggressively
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to reduce memory usage
            max_size = (600, 600)  # Further reduced size
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img.save(image_path, optimize=True, quality=70)
        
        # Get reader
        ocr_reader = initialize_reader()
        if ocr_reader is None:
            raise Exception("Failed to initialize OCR reader")
        
        # Process with minimal memory footprint
        result = ocr_reader.readtext(image_path, detail=0, paragraph=False)
        
        # Immediate cleanup
        gc.collect()
        
        return " ".join(result) if result else "No text found"
        
    except Exception as e:
        gc.collect()
        raise Exception(f"OCR processing failed: {str(e)}")

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({'status': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "TextExtract OCR API is running!",
        "status": "active",
        "engine": "easyocr-optimized"
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

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
        
        # Generate unique filename
        unique_filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save file
        file.save(file_path)
        
        try:
            # Extract text
            raw_text = extract_text(file_path)
            
            # Clean up file immediately
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Force garbage collection
            gc.collect()
            
            return jsonify({
                'success': True,
                'text': raw_text,
                'message': 'Text extracted successfully'
            })
            
        except Exception as ocr_error:
            # Clean up on error
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
