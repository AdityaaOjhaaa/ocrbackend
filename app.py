import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import easyocr
import uuid

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize EasyOCR Reader
reader = easyocr.Reader(['en'], gpu=False)

# Set upload folder
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def extract_text(image_path):
    """Extract text from image using EasyOCR"""
    try:
        result = reader.readtext(image_path, detail=0)
        return " ".join(result)
    except Exception as e:
        raise Exception(f"OCR processing failed: {str(e)}")

def clean_text(text):
    """Clean the extracted text for readability"""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "TextExtract OCR API is running!",
        "status": "active",
        "endpoints": {
            "upload": "/upload - POST - Upload image for OCR processing"
        }
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
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
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
            
            # Clean up uploaded file
            os.remove(file_path)
            
            return jsonify({
                'success': True,
                'text': cleaned_text,
                'message': 'Text extracted successfully'
            })
            
        except Exception as ocr_error:
            # Clean up uploaded file in case of error
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'error': str(ocr_error)}), 500
            
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
