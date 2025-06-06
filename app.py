import os
import gc
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import easyocr
import uuid

# Initialize Flask app
app = Flask(__name__)

# Configure CORS properly for your GitHub Pages domain
CORS(app, 
     origins=['https://adityaaojhaaa.github.io', 'http://localhost:3000', 'http://127.0.0.1:3000'],
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'],
     supports_credentials=True)

# Global reader variable - will be initialized lazily
reader = None

# Set upload folder
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB limit

def get_reader():
    """Lazy initialization of EasyOCR reader to save memory"""
    global reader
    if reader is None:
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return reader

def extract_text(image_path):
    """Extract text from image using EasyOCR with memory optimization"""
    try:
        with Image.open(image_path) as img:
            max_size = (800, 800)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img.save(image_path, optimize=True, quality=80)
        
        ocr_reader = get_reader()
        result = ocr_reader.readtext(image_path, detail=0, paragraph=True)
        gc.collect()
        
        return " ".join(result)
    except Exception as e:
        gc.collect()
        raise Exception(f"OCR processing failed: {str(e)}")

def clean_text(text):
    """Clean the extracted text for readability"""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://adityaaojhaaa.github.io')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "TextExtract OCR API is running!",
        "status": "active",
        "engine": "easyocr",
        "cors": "enabled"
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# Handle preflight OPTIONS requests
@app.route('/upload', methods=['OPTIONS'])
def handle_options():
    response = jsonify({'status': 'OK'})
    response.headers.add('Access-Control-Allow-Origin', 'https://adityaaojhaaa.github.io')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

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
            raw_text = extract_text(file_path)
            cleaned_text = clean_text(raw_text)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            gc.collect()
            
            return jsonify({
                'success': True,
                'text': cleaned_text,
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

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 8MB.'}), 413

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
