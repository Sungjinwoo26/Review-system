"""
Flask API Server for Review Intelligence Engine
Bridges HTML/JS frontend with Python backend services
Handles: API key validation, file uploads, data processing
"""

from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import logging

from services.ingestion import (
    fetch_dynamic_api,
    parse_uploaded_file,
    normalize_schema,
    load_data
)
from services.scoring_engine import (
    apply_scoring_pipeline,
    aggregate_to_products,
    classify_quadrants,
    calculate_revenue_at_risk
)
from utils.error_handler import APIError, DataError
from utils.logger import log_event, log_error, logger

# ===== FLASK APP SETUP =====
app = Flask(__name__, static_folder='web', static_url_path='')

# Configuration
ALLOWED_EXTENSIONS = {'csv', 'json'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
UPLOAD_FOLDER = 'uploads'
MOSAIC_DEFAULT_API_KEY = "mosaic_api_key_default"  # Replace with actual default key
MOSAIC_API_URL = "https://mosaicfellowship.in/api/data/cx/reviews"

# Create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Session storage for uploaded data (in production, use Redis or database)
session_data = {}

# ===== UTILITY FUNCTIONS =====
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_schema(df):
    """
    Validate that dataframe has required columns
    
    Required: product_name, rating (or similar)
    Optional but preferred: review_text, ltv, revenue_at_risk
    """
    required_cols = {
        'product_name': ['product', 'product_name', 'product_id'],
        'rating': ['rating', 'score', 'stars']
    }
    
    missing_required = []
    actual_cols = df.columns.str.lower().tolist()
    
    for required, alternatives in required_cols.items():
        found = any(alt.lower() in actual_cols for alt in alternatives)
        if not found:
            missing_required.append(required)
    
    if missing_required:
        return False, f"Missing required columns: {', '.join(missing_required)}"
    
    return True, "Schema valid"

def normalize_dataframe(df):
    """
    Normalize dataframe schema to expected format
    Fill missing columns with defaults
    """
    df = df.copy()
    
    # Normalize column names  
    column_mapping = {
        'product': 'product_name',
        'product_id': 'product_name', 
        'score': 'rating',
        'stars': 'rating',
        'review': 'review_text',
        'text': 'review_text',
        'ltv': 'ltv',
        'revenue': 'revenue_at_risk',
        'date': 'review_date'
    }
    
    # Case-insensitive column renaming
    for old_col in df.columns:
        lower_col = old_col.lower()
        if lower_col in column_mapping:
            df = df.rename(columns={old_col: column_mapping[lower_col]})
    
    # Ensure required columns exist
    if 'product_name' not in df.columns:
        df['product_name'] = 'Unknown Product'
    if 'rating' not in df.columns:
        df['rating'] = 3.0  # Default neutral rating
    if 'review_date' not in df.columns:
        df['review_date'] = datetime.now().isoformat()
    
    # Optional columns with defaults
    if 'review_text' not in df.columns:
        df['review_text'] = ''
    if 'ltv' not in df.columns:
        df['ltv'] = 1000  # Default LTV
    if 'revenue_at_risk' not in df.columns:
        df['revenue_at_risk'] = 0
    
    return df

def transform_to_dashboard_format(df):
    """
    Transform processed dataframe to dashboard PRODUCTS format
    Returns list of product records compatible with dashboard
    """
    try:
        # Ensure required columns
        df = normalize_dataframe(df)
        
        # Group by product for aggregation
        products_list = []
        
        if df.empty:
            return products_list
        
        for product_name in df['product_name'].unique():
            product_df = df[df['product_name'] == product_name]
            
            total_reviews = len(product_df)
            avg_rating = product_df['rating'].astype(float).mean()
            
            # Calculate negative review percentage (rating <= 2)
            negative_count = (product_df['rating'].astype(float) <= 2).sum()
            negative_pct = (negative_count / total_reviews * 100) if total_reviews > 0 else 0
            
            # Revenue at risk calculation
            total_revenue_at_risk = product_df['revenue_at_risk'].astype(float).sum() if 'revenue_at_risk' in df.columns else product_df['ltv'].astype(float).sum() * (negative_pct / 100)
            
            # Risk probability (simplified)
            risk_probability = min(negative_pct / 100, 1.0)
            
            # Determine severity
            if risk_probability >= 0.7:
                severity = "High"
            elif risk_probability >= 0.4:
                severity = "Medium"
            else:
                severity = "Low"
            
            # Create product record
            product_record = {
                'name': str(product_name),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'finalScore': round(risk_probability, 2),
                'revenueAtRisk': int(total_revenue_at_risk),
                'riskProbability': round(risk_probability, 2),
                'negativePct': round(negative_pct, 1),
                'quadrant': 'Fire Fight' if severity == 'High' else 'VIP Nudge' if severity == 'Medium' else 'Noise',
                'frequency': int(total_reviews),
                'impact': int(min((total_revenue_at_risk / 100000) * 100, 100)),  # Normalize to 0-100
                'rating': round(avg_rating, 1),
                'trend': 'Stable',  # Simplified for now
                'severity': severity,
                'totalReviews': total_reviews,
                'issues': {
                    'delivery': int(total_reviews * 0.25),
                    'quality': int(total_reviews * 0.35),
                    'packaging': int(total_reviews * 0.20),
                    'support': int(total_reviews * 0.20)
                }
            }
            
            products_list.append(product_record)
        
        logger.debug(f"Transformed {len(products_list)} products to dashboard format")
        return products_list
        
    except Exception as e:
        logger.error(f"Error transforming data: {str(e)}")
        return []

# ===== ROUTES: DATA SOURCE CONFIGURATION =====

@app.route('/api/data/default', methods=['POST'])
def use_default_data():
    """
    Load default/sample data
    """
    try:
        logger.info("Loading default data")
        
        # Load from ingestion service or use embedded sample
        # For now, we'll use a sample dataset
        sample_data = pd.DataFrame({
            'product_name': ['Atlas Desk', 'Pulse Earbuds', 'North Mug', 'Harbor Lamp', 'Summit Bottle'],
            'rating': [2.8, 3.1, 3.6, 3.4, 3.9],
            'revenue_at_risk': [920000, 640000, 410000, 285000, 198000],
            'review_date': [datetime.now().isoformat()] * 5,
            'review_text': ['High issues'] * 5,
            'ltv': [10000] * 5
        })
        
        products = transform_to_dashboard_format(sample_data)
        session_data['current_data'] = products
        session_data['last_updated'] = datetime.now().isoformat()
        
        log_event("DEFAULT_DATA_LOADED", {"count": len(products)})
        
        return jsonify({
            'success': True,
            'message': 'Default data loaded successfully',
            'products': products,
            'timestamp': session_data['last_updated']
        })
        
    except Exception as e:
        logger.error(f"Error loading default data: {str(e)}")
        log_error("DEFAULT_DATA_ERROR", str(e))
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/data/fetch', methods=['POST'])
def fetch_with_api_key():
    """
    Fetch data from Mosaic API with provided API key
    
    Expected JSON:
    {
        "api_key": "...",
        "use_default": true/false
    }
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        use_default = data.get('use_default', False)
        
        # If using default, apply default API key
        if use_default:
            api_key = MOSAIC_DEFAULT_API_KEY
            logger.info("Using default Mosaic API key")
        
        if not api_key:
            return jsonify({'success': False, 'error': 'API key is required'}), 400
        
        logger.info(f"Fetching data from Mosaic API with key: {api_key[:8]}...")
        
        # Call ingestion service
        try:
            df = fetch_dynamic_api(
                api_url=MOSAIC_API_URL,
                api_key=api_key,
                timeout=30
            )
            
            if df is None or df.empty:
                return jsonify({
                    'success': False,
                    'error': 'No data returned from API'
                }), 400
            
            # Validate and normalize
            df = normalize_dataframe(df)
            products = transform_to_dashboard_format(df)
            
            session_data['current_data'] = products
            session_data['last_updated'] = datetime.now().isoformat()
            
            log_event("API_DATA_FETCHED", {
                "count": len(products),
                "rows": len(df)
            })
            
            return jsonify({
                'success': True,
                'message': f'Successfully fetched {len(products)} products',
                'products': products,
                'timestamp': session_data['last_updated'],
                'stats': {
                    'total_rows': len(df),
                    'total_products': len(products)
                }
            })
            
        except APIError as e:
            logger.error(f"API Error: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'API Error: {str(e)}'
            }), 503
        except Exception as e:
            logger.error(f"Error fetching from API: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch data: {str(e)}'
            }), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in fetch_with_api_key: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/data/upload', methods=['POST'])
def upload_file():
    """
    Upload and parse CSV/JSON file
    
    Expected: multipart/form-data with 'file' field
    """
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        logger.info(f"Processing uploaded file: {file.filename}")
        
        try:
            # Parse file
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Load data
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath)
            elif filename.endswith('.json'):
                df = pd.read_json(filepath)
            else:
                return jsonify({'success': False, 'error': 'Unsupported file format'}), 400
            
            # Validate schema
            is_valid, validation_msg = validate_schema(df)
            if not is_valid:
                return jsonify({
                    'success': False,
                    'error': f'Invalid schema: {validation_msg}'
                }), 400
            
            # Normalize and transform
            df = normalize_dataframe(df)
            logger.info(f"Normalized dataframe shape: {df.shape}")
            logger.info(f"Normalized columns: {df.columns.tolist()}")
            logger.info(f"First row: {df.iloc[0].to_dict() if len(df) > 0 else 'empty'}")
            
            products = transform_to_dashboard_format(df)
            logger.info(f"Transformed {len(products)} products")
            if products:
                logger.info(f"First product: {products[0]}")
            
            session_data['current_data'] = products
            session_data['last_updated'] = datetime.now().isoformat()
            session_data['source_file'] = filename
            
            log_event("FILE_UPLOADED", {
                "filename": filename,
                "rows": len(df),
                "products": len(products)
            })
            
            return jsonify({
                'success': True,
                'message': f'Successfully processed {len(products)} products from file',
                'products': products,
                'timestamp': session_data['last_updated'],
                'stats': {
                    'total_rows': len(df),
                    'total_products': len(products),
                    'filename': filename
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Error processing file: {str(e)}'
            }), 400
    
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ===== ROUTES: DATA RETRIEVAL =====

@app.route('/api/data/current', methods=['GET'])
def get_current_data():
    """Get currently loaded data"""
    if 'current_data' not in session_data:
        return jsonify({
            'success': False,
            'error': 'No data loaded'
        }), 400
    
    return jsonify({
        'success': True,
        'products': session_data.get('current_data', []),
        'timestamp': session_data.get('last_updated'),
        'source': session_data.get('source_file', 'API')
    })

# ===== HEALTH CHECK =====

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'data_loaded': 'current_data' in session_data
    })

# ===== ROUTES: FRONTEND SERVING =====

@app.route('/')
def serve_index():
    """Serve landing page"""
    return send_from_directory('web', 'index.html')

@app.route('/dashboard.html')
def serve_dashboard():
    """Serve dashboard page"""
    return send_from_directory('web', 'dashboard.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory('web', path)

# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

# ===== MAIN =====

if __name__ == '__main__':
    logger.info("Starting Review Intelligence Engine API Server")
    logger.info(f"Serving files from: web/")
    logger.info(f"Loading uploads to: {UPLOAD_FOLDER}")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )
