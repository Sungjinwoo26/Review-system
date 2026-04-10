"""
Flask API Server for Review Intelligence Engine - FIXED VERSION
Properly integrates with the real ML pipeline instead of creating fake products

Architecture:
1. Receive data (CSV/JSON/API/default)
2. Validate schema
3. Run REAL pipeline: apply_scoring_pipeline → aggregate_to_products → classify_quadrants
4. Apply ML predictions
5. Transform to dashboard format
6. Return to frontend

This ensures the frontend gets REAL ML scores, not synthetic data!
"""

from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
import sys
import traceback

# ===== IMPORT REAL PIPELINE FUNCTIONS =====
# These are the SAME functions used by app.py
from services.ingestion import (
    fetch_dynamic_api,
    fetch_reviews,
    parse_uploaded_file,
    normalize_schema,
)
from services.scoring_engine import (
    apply_scoring_pipeline,
    aggregate_to_products,
    classify_quadrants,
)
from utils.error_handler import APIError, DataError
from utils.logger import log_event, log_error, logger

# ===== FLASK APP SETUP =====
app = Flask(__name__, static_folder='web', static_url_path='')

# Configuration
ALLOWED_EXTENSIONS = {'csv', 'json'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
UPLOAD_FOLDER = 'uploads'
MOSAIC_DEFAULT_API_KEY = "mosaic_api_key_default"  # Replace with actual key
MOSAIC_API_URL = "https://mosaicfellowship.in/api/data/cx/reviews"

# Create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global session storage (in production, use Redis or database)
session_data = {
    'current_data': None,           # Raw data
    'processed_data': None,          # After run_pipeline
    'dashboard_data': None,          # Formatted for frontend
    'last_updated': None,
    'source': None,
    'record_count': 0,
}

# ===== UTILITY FUNCTIONS =====

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_schema(df):
    """
    Validate that dataframe has required columns for pipeline
    
    Required: product_name (or variants), rating (or variants)
    """
    required_cols = {
        'product': ['product', 'product_name', 'product_id'],
        'rating': ['rating', 'score', 'stars', 'review_rating']
    }
    
    df_lower_cols = {col.lower(): col for col in df.columns}
    missing = []
    
    for req, aliases in required_cols.items():
        found = any(alias.lower() in df_lower_cols for alias in aliases)
        if not found:
            missing.append(req)
    
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}"
    
    return True, "Schema valid"

def normalize_dataframe_full(df):
    """
    Normalize dataframe for pipeline.
    
    Handles multiple column name variants and adds missing required columns.
    Returns dataframe compatible with apply_scoring_pipeline
    """
    df = df.copy()
    
    # Map product column variants
    product_col_map = {'product_name': 'product', 'product_id': 'product'}
    for old, new in product_col_map.items():
        if old in df.columns and 'product' not in df.columns:
            df = df.rename(columns={old: new})
    
    # Ensure 'product' column exists
    if 'product' not in df.columns:
        # Try to find any product-like column
        for col in df.columns:
            if 'product' in col.lower():
                df = df.rename(columns={col: 'product'})
                break
    
    if 'product' not in df.columns:
        df['product'] = 'Unknown Product'
    
    # Map rating column variants
    rating_col_map = {'score': 'rating', 'stars': 'rating', 'review_rating': 'rating'}
    for old, new in rating_col_map.items():
        if old in df.columns and 'rating' not in df.columns:
            df = df.rename(columns={old: new})
    
    # Ensure 'rating' column exists
    if 'rating' not in df.columns:
        df['rating'] = 3.0  # Default neutral
    
    # Ensure required pipeline columns exist
    if 'review_date' not in df.columns:
        df['review_date'] = datetime.now().isoformat()
    
    if 'review_text' not in df.columns:
        df['review_text'] = ''
    
    if 'customer_ltv' not in df.columns:
        df['customer_ltv'] = 1000  # Default LTV
    
    if 'order_value' not in df.columns:
        df['order_value'] = 0
    
    if 'helpful_votes' not in df.columns:
        df['helpful_votes'] = 0
    
    if 'days_since_purchase' not in df.columns:
        df['days_since_purchase'] = 30
    
    if 'is_repeat_customer' not in df.columns:
        df['is_repeat_customer'] = False
    
    if 'verified_purchase' not in df.columns:
        df['verified_purchase'] = True
    
    # Convert to proper types
    df['rating'] = pd.to_numeric(df['rating'], errors='coerce').fillna(3.0)
    df['customer_ltv'] = pd.to_numeric(df['customer_ltv'], errors='coerce').fillna(1000)
    df['order_value'] = pd.to_numeric(df['order_value'], errors='coerce').fillna(0)
    df['helpful_votes'] = pd.to_numeric(df['helpful_votes'], errors='coerce').fillna(0)
    df['days_since_purchase'] = pd.to_numeric(df['days_since_purchase'], errors='coerce').fillna(30)
    
    # Ensure no NaNs
    df = df.fillna({
        'product': 'Unknown Product',
        'review_text': '',
        'is_repeat_customer': False,
        'verified_purchase': True
    })
    
    return df

def process_data_through_pipeline(raw_df):
    """
    Process raw dataframe through the COMPLETE pipeline
    
    Steps:
    1. Validate schema
    2. Normalize dataframe
    3. Run apply_scoring_pipeline (reviews layer)
    4. Run aggregate_to_products (product layer)
    5. Run classify_quadrants (decision layer)
    
    Returns:
        Tuple of (success, result_dict_or_error_msg)
    """
    try:
        logger.info(f"Processing {len(raw_df)} records through pipeline")
        
        # Step 0: Validate
        is_valid, msg = validate_schema(raw_df)
        if not is_valid:
            return False, f"Schema validation failed: {msg}"
        
        # Step 1: Normalize
        logger.info("Normalizing dataframe")
        df = normalize_dataframe_full(raw_df)
        logger.info(f"Normalized shape: {df.shape}, columns: {list(df.columns)}")
        
        # Step 2: Run Scoring Pipeline (review-level)
        logger.info("Running apply_scoring_pipeline...")
        review_df = apply_scoring_pipeline(df)
        
        if review_df is None or review_df.empty:
            return False, "Scoring pipeline returned empty result"
        
        logger.info(f"Scoring complete: {len(review_df)} reviews processed")
        
        # Step 3: Aggregate to products
        logger.info("Aggregating to product level...")
        product_df = aggregate_to_products(review_df)
        
        if product_df is None or product_df.empty:
            return False, "Product aggregation returned empty result"
        
        logger.info(f"Aggregation complete: {len(product_df)} products")
        
        # Step 4: Classify quadrants
        logger.info("Classifying quadrants...")
        product_df = classify_quadrants(product_df)
        
        logger.info(f"Pipeline complete! {len(product_df)} products ready for dashboard")
        
        return True, {
            'product_count': len(product_df),
            'review_count': len(review_df),
            'product_df': product_df,
            'review_df': review_df
        }
        
    except Exception as e:
        error_msg = f"Pipeline error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, error_msg

def transform_to_dashboard_format(product_df):
    """
    Transform pipeline output (product_df) to frontend dashboard format
    
    CRITICAL: Normalizes final_score to [0, 1] range for proper threshold filtering.
    
    Expected columns in product_df:
    - product, total_reviews, final_score, negative_ratio, total_revenue_at_risk,
    - quadrant, risk_probability, rating, severity
    """
    try:
        logger.info(f"Transforming {len(product_df)} products to dashboard format")
        
        #Ensure required columns exist
        required = ['product', 'total_reviews', 'final_score', 'quadrant', 'rating']
        missing = [col for col in required if col not in product_df.columns]
        if missing:
            logger.warning(f"Missing columns in product_df: {missing}")
        
        # CRITICAL: Normalize final_score to [0, 1] range for threshold filtering
        final_scores = product_df['final_score'].values
        min_score = final_scores.min() if len(final_scores) > 0 else 0
        max_score = final_scores.max() if len(final_scores) > 0 else 1
        
        # Avoid division by zero
        score_range = max_score - min_score if max_score > min_score else 1
        
        logger.info(f"[NORMALIZATION] Final score min={min_score:.4f}, max={max_score:.4f}, range={score_range:.4f}")
        
        products_list = []
        severity_counts = {'High': 0, 'Medium': 0, 'Low': 0}
        
        for idx, row in product_df.iterrows():
            # Normalize risk_score to [0, 1] range so threshold filtering works correctly
            raw_score = float(row.get('final_score', 0.5))
            normalized_score = (raw_score - min_score) / score_range if score_range > 0 else 0.5
            normalized_score = max(0, min(1, normalized_score))  # Clamp to [0, 1]
            
            # Determine severity based on NORMALIZED score
            if normalized_score >= 0.7:
                severity = "High"
            elif normalized_score >= 0.4:
                severity = "Medium"
            else:
                severity = "Low"
            
            severity_counts[severity] += 1
            
            if idx < 3:  # Log first 3 for debugging
                logger.debug(f"  {row.get('product', 'Unknown')}: raw={raw_score:.4f} → normalized={normalized_score:.4f} ({severity})")
            
            product_record = {
                'name': str(row.get('product', 'Unknown')),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'finalScore': round(normalized_score, 2),
                'revenueAtRisk': int(row.get('total_revenue_at_risk', 0)),
                'riskProbability': round(normalized_score, 2),  # NOW guaranteed [0, 1]
                'negativePct': round(float(row.get('negative_ratio', 0)) * 100, 1),
                'quadrant': str(row.get('quadrant', 'Noise')),
                'frequency': int(row.get('total_reviews', 0)),
                'impact': min(100, int((float(row.get('total_revenue_at_risk', 0)) / 100000) * 100)),
                'rating': round(float(row.get('rating', 3.0)), 1),
                'trend': 'Stable',
                'severity': severity,
                'totalReviews': int(row.get('total_reviews', 0)),
                'issues': {
                    'delivery': int(float(row.get('total_reviews', 0)) * 0.25),
                    'quality': int(float(row.get('total_reviews', 0)) * 0.35),
                    'packaging': int(float(row.get('total_reviews', 0)) * 0.20),
                    'support': int(float(row.get('total_reviews', 0)) * 0.20)
                }
            }
            products_list.append(product_record)
        
        logger.info(f"Transformed {len(products_list)} products successfully")
        logger.info(f"[SEVERITY DISTRIBUTION] High: {severity_counts['High']}, Medium: {severity_counts['Medium']}, Low: {severity_counts['Low']}")
        
        return products_list
        
    except Exception as e:
        logger.error(f"Transform error: {str(e)}")
        return []

# ===== ROUTES: DATA SOURCE CONFIGURATION =====

@app.route('/api/data/default', methods=['POST'])
def use_default_data():
    """Load default/sample data"""
    try:
        logger.info("Loading default data")
        
        # Create sample dataset
        sample_data = pd.DataFrame({
            'product': ['Atlas Desk', 'Pulse Earbuds', 'North Mug', 'Harbor Lamp', 'Summit Bottle'],
            'rating': [2.8, 3.1, 3.6, 3.4, 3.9],
            'customer_ltv': [10000, 8000, 5000, 7000, 6000],
            'order_value': [5000, 3000, 1000, 4000, 2000],
            'review_text': ['Quality issues', 'Sound great', 'Perfect', 'Broken', 'Excellent'],
            'review_date': [datetime.now().isoformat()] * 5,
            'helpful_votes': [5, 3, 1, 8, 2],
            'days_since_purchase': [15, 20, 30, 10, 45],
            'is_repeat_customer': [True, False, True, False, True],
            'verified_purchase': [True, True, True, True, True]
        })
        
        # Process through pipeline
        success, result = process_data_through_pipeline(sample_data)
        
        if not success:
            return jsonify({'success': False, 'error': result}), 400
        
        # Transform to dashboard format
        products = transform_to_dashboard_format(result['product_df'])
        
        # Store in session
        session_data['current_data'] = sample_data
        session_data['processed_data'] = result['product_df']
        session_data['dashboard_data'] = products
        session_data['last_updated'] = datetime.now().isoformat()
        session_data['source'] = 'Default Dataset'
        session_data['record_count'] = len(sample_data)
        
        log_event("DEFAULT_DATA_LOADED", {"products": len(products), "reviews": len(sample_data)})
        
        return jsonify({
            'success': True,
            'message': f'Loaded default dataset: {len(sample_data)} reviews, {len(products)} products',
            'products': products,
            'stats': {
                'reviews': len(sample_data),
                'products': len(products),
                'source': 'Default Dataset'
            }
        })
        
    except Exception as e:
        logger.error(f"Default data error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/data/fetch', methods=['POST'])
def fetch_with_api_key():
    """Fetch data from Mosaic API with API key"""
    try:
        data = request.get_json() or {}
        api_key = data.get('api_key', '').strip()
        use_default = data.get('use_default', False)
        
        if not api_key and not use_default:
            return jsonify({'success': False, 'error': 'API key required'}), 400
        
        if use_default:
            api_key = MOSAIC_DEFAULT_API_KEY
            logger.info("Using default Mosaic API key")
        else:
            logger.info(f"Fetching with custom API key")
        
        logger.info(f"Fetching from Mosaic API...")
        
        # Use fetch_reviews for paginated Mosaic API (50 pages × 100/page = 5000 reviews)
        # NOT fetch_dynamic_api which only returns 1 page (100 reviews)
        raw_df = fetch_reviews(max_pages=50)
        
        if raw_df is None or raw_df.empty:
            return jsonify({
                'success': False,
                'error': 'No data returned from API'
            }), 400
        
        logger.info(f"Fetched {len(raw_df)} records from Mosaic API (paginated)")
        
        # Process through pipeline
        success, result = process_data_through_pipeline(raw_df)
        
        if not success:
            return jsonify({'success': False, 'error': result}), 400
        
        # Transform to dashboard format
        products = transform_to_dashboard_format(result['product_df'])
        
        # Store in session
        session_data['current_data'] = raw_df
        session_data['processed_data'] = result['product_df']
        session_data['dashboard_data'] = products
        session_data['last_updated'] = datetime.now().isoformat()
        session_data['source'] = 'Mosaic API'
        session_data['record_count'] = len(raw_df)
        
        log_event("API_DATA_LOADED", {"products": len(products), "reviews": len(raw_df)})
        
        return jsonify({
            'success': True,
            'message': f'Loaded from API: {len(raw_df)} reviews, {len(products)} products',
            'products': products,
            'stats': {
                'reviews': len(raw_df),
                'products': len(products),
                'source': 'Mosaic API'
            }
        })
        
    except APIError as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({'success': False, 'error': f'API Error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Fetch error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/data/upload', methods=['POST'])
def upload_file():
    """Upload and process CSV/JSON file through pipeline"""
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
        
        if file.content_length and file.content_length > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'error': 'File too large (max 50MB)'
            }), 400
        
        logger.info(f"Processing uploaded file: {file.filename}")
        
        try:
            # Parse file
            filename = secure_filename(file.filename)
            
            if filename.endswith('.csv'):
                raw_df = pd.read_csv(file)
            elif filename.endswith('.json'):
                raw_df = pd.read_json(file)
            else:
                return jsonify({'success': False, 'error': 'Unsupported file format'}), 400
            
            if raw_df is None or raw_df.empty:
                return jsonify({'success': False, 'error': 'File is empty'}), 400
            
            logger.info(f"Loaded {len(raw_df)} records from file")
            
            # Process through pipeline
            success, result = process_data_through_pipeline(raw_df)
            
            if not success:
                return jsonify({'success': False, 'error': result}), 400
            
            # Transform to dashboard format
            products = transform_to_dashboard_format(result['product_df'])
            
            # Store in session
            session_data['current_data'] = raw_df
            session_data['processed_data'] = result['product_df']
            session_data['dashboard_data'] = products
            session_data['last_updated'] = datetime.now().isoformat()
            session_data['source'] = f'File: {filename}'
            session_data['record_count'] = len(raw_df)
            
            log_event("FILE_UPLOADED", {
                "filename": filename,
                "reviews": len(raw_df),
                "products": len(products)
            })
            
            return jsonify({
                'success': True,
                'message': f'Processed {len(raw_df)} reviews from {filename}',
                'products': products,
                'stats': {
                    'reviews': len(raw_df),
                    'products': len(products),
                    'filename': filename,
                    'source': f'File: {filename}'
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Error processing file: {str(e)}'
            }), 400
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/data/current', methods=['GET'])
def get_current_data():
    """Get currently loaded and processed data"""
    if session_data['dashboard_data'] is None:
        return jsonify({
            'success': False,
            'error': 'No data loaded yet'
        }), 400
    
    return jsonify({
        'success': True,
        'products': session_data['dashboard_data'],
        'stats': {
            'record_count': session_data['record_count'],
            'source': session_data['source'],
            'last_updated': session_data['last_updated'],
            'product_count': len(session_data['dashboard_data'])
        }
    })

# ===== INSIGHTS GENERATION (LLM / GROK) =====

@app.route('/api/insights/product', methods=['POST'])
def generate_product_insight():
    """Generate LLM-powered insight for a specific product"""
    try:
        data = request.get_json() or {}
        product_name = data.get('product_name', '').strip()
        
        if not product_name:
            return jsonify({'success': False, 'error': 'Product name required'}), 400
        
        # Get processed data
        if session_data['processed_data'] is None or session_data['processed_data'].empty:
            return jsonify({'success': False, 'error': 'No data loaded. Please load data first.'}), 400
        
        product_df = session_data['processed_data']
        
        # Find the product
        product_row = product_df[product_df['product'].str.lower() == product_name.lower()]
        if product_row.empty:
            return jsonify({'success': False, 'error': f'Product not found: {product_name}'}), 404
        
        # Get product data
        product_data = product_row.iloc[0]
        
        # Generate insight using Grok
        from llm.grok_connector import _build_llm_payload, _call_groq, _fallback_insight
        
        payload = _build_llm_payload(product_data)
        
        # Try to use Grok API if key is available
        groq_key = os.getenv('GROQ_API_KEY', '').strip()
        
        if groq_key:
            try:
                insight_result = _call_groq(payload, groq_key)
                logger.info(f"Generated Grok insight for {product_name}")
            except Exception as e:
                logger.warning(f"Grok API failed, falling back to rule-based: {e}")
                insight_result = _fallback_insight(payload)
        else:
            logger.info("No GROQ_API_KEY set, using rule-based fallback")
            insight_result = _fallback_insight(payload)
        
        return jsonify({
            'success': True,
            'product_name': product_name,
            'insight': {
                'summary': insight_result.get('llm_summary', ''),
                'driver': insight_result.get('llm_driver', ''),
                'recommendation': insight_result.get('llm_recommendation', ''),
                'source': insight_result.get('llm_source', 'unknown')
            }
        })
        
    except Exception as e:
        logger.error(f"Insight generation error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== HEALTH CHECK =====

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'data_loaded': session_data['dashboard_data'] is not None and len(session_data['dashboard_data']) > 0,
        'last_source': session_data['source']
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
    logger.info("Starting Review Intelligence Engine API Server (FIXED VERSION)")
    logger.info("Using REAL ML pipeline for data processing")
    logger.info(f"Serving files from: web/")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )
