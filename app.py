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

def initialize_reader():
    global reader
    if reader is None:
        try:
            reader = easyocr.Reader(['en'], gpu=False)
            print("EasyOCR reader initialized successfully")
        except Exception as e:
            print(f"Failed to initialize EasyOCR: {str(e)}")
            reader = None
    return reader

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'OK',
        'message': 'OCR Backend Service is running',
        'service': 'Python Flask OCR API'
    })

@app.route('/api/ocr', methods=['POST', 'OPTIONS'])
def process_ocr():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        # Initialize reader if not already done
        ocr_reader = initialize_reader()
        if ocr_reader is None:
            return jsonify({
                'success': False,
                'error': 'OCR service not available'
            }), 500

        # Check if image file is provided
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No image file provided'
            }), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No image file selected'
            }), 400

        # Process the image
        image = Image.open(file.stream)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Perform OCR
        results = ocr_reader.readtext(image)
        
        # Extract text from results
        extracted_text = ' '.join([result[1] for result in results])
        
        # Calculate confidence (average of all detections)
        confidence = sum([result[2] for result in results]) / len(results) if results else 0
        
        # Clean up
        image.close()
        gc.collect()

        return jsonify({
            'success': True,
            'text': extracted_text.strip(),
            'confidence': round(confidence * 100, 2),
            'detections': len(results)
        })

    except Exception as e:
        print(f"OCR processing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'OCR processing failed',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
