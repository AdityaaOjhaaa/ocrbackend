import os
import gc
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import easyocr
import uuid

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global reader variable - will be initialized lazily
reader = None

# Set upload folder
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # Reduced to 8MB

def get_reader():
    """Lazy initialization of EasyOCR reader to save memory"""
    global reader
    if reader is None:
        # Initialize with minimal memory footprint
        reader = easyocr.Reader(['en'], gpu=False, verbose=False, 
                               quantize=True, width_ths=0.7, height_ths=0.7)
    return reader

def extract_text(image_path):
    """Extract text from image using EasyOCR with memory optimization"""
    try:
        # Compress image before processing to reduce memory usage
        with Image.open(image_path) as img:
            # Resize large images to reduce memory consumption
            max_size = (1024, 1024)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img.save(image_path, optimize=True, quality=85)
        
        # Get reader and process
        ocr_reader = get_reader()
        result = ocr_reader.readtext(image_path, detail=0, paragraph=True)
        
        # Force garbage collection after processing
        gc.collect()
        
        return " ".join(result)
    except Exception as e:
        gc.collect()  # Clean up memory even on error
        raise Exception(f"OCR processing failed: {str(e)}")

def clean_text(text):
    """Clean the extracted text for readability"""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "TextExtract OCR API is running!",
        "status": "active",
        "memory_optimized": True
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if file is an image
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            return jsonify({'error': 'Invalid file type. Please upload an image.'}), 400
        
        # Generate unique filename
        unique_filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save file
        file.save(file_path)
        
        try:
            # Perform OCR
            raw_text = extract_text(file_path)
            cleaned_text = clean_text(raw_text)
            
            # Clean up uploaded file immediately
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Force garbage collection
            gc.collect()
            
            return jsonify({
                'success': True,
                'text': cleaned_text,
                'message': 'Text extracted successfully'
            })
            
        except Exception as ocr_error:
            # Clean up uploaded file in case of error
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

