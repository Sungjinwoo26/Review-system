"""
ML Model Prediction Module

Applies trained Logistic Regression model to generate risk probability predictions.
Handles scaling and prediction with graceful error handling.

Input: Trained model dict + product DataFrame with features
Output: Product DataFrame with 'risk_probability' column added
"""

import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')


def predict_risk(model_dict: dict, df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate risk probability predictions for products.
    
    Process:
    1. Extract model, scaler, and features from model_dict
    2. Scale features using the fitted scaler
    3. Generate probability predictions using the trained model
    4. Add 'risk_probability' column to dataframe
    
    Args:
        model_dict: Dictionary returned from train_risk_model() containing:
            - model: Trained LogisticRegression object
            - scaler: StandardScaler fitted on training data
            - features: List of feature names used in training
            - threshold: High-risk classification threshold
        
        df: Product-level DataFrame with feature columns
    
    Returns:
        DataFrame with 'risk_probability' column added
        - risk_probability: Probability of product being high-risk (0-1)
        - risk_category: Categorical label (Low/Medium/High)
        - high_risk_predicted: Binary prediction (0 or 1)
    
    Error Handling:
    - Missing features: Returns default risk_probability = 0
    - Scaling errors: Returns default risk_probability = 0
    - Prediction errors: Returns default risk_probability = 0
    - Gracefully degrades if model fails (backward compatible)
    """
    
    df = df.copy()
    model = model_dict['model']
    scaler = model_dict['scaler']
    features = model_dict['features']
    threshold = model_dict['threshold']
    
    try:
        # Step 1: Validate that all required features exist
        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            raise ValueError(f"Missing features in dataframe: {missing_features}")
        
        # Step 2: Extract feature matrix
        X = df[features].values
        
        # Step 3: Scale features using the trained scaler
        # Critical: Use the same scaler that was fitted on training data
        X_scaled = scaler.transform(X)
        
        # Step 4: Generate probability predictions
        # predict_proba returns array of shape (n_samples, n_classes)
        # Column 0 = probability of class 0 (low risk)
        # Column 1 = probability of class 1 (high risk)
        risk_probabilities = model.predict_proba(X_scaled)[:, 1]
        
        # Step 5: Generate binary predictions
        binary_predictions = model.predict(X_scaled)
        
        # Step 6: Add columns to dataframe
        df['risk_probability'] = risk_probabilities
        df['high_risk_predicted'] = binary_predictions
        
        # Step 7: Create categorical risk levels for dashboard display
        # 0-0.3 = Low, 0.3-0.7 = Medium, 0.7-1.0 = High
        df['risk_category'] = pd.cut(
            df['risk_probability'],
            bins=[0, 0.3, 0.7, 1.0],
            labels=['Low', 'Medium', 'High'],
            include_lowest=True
        )
        
        # Fill any NaN in risk_category (edge case)
        df['risk_category'] = df['risk_category'].fillna('Low')
        
        return df
    
    except Exception as e:
        # Graceful degradation: if prediction fails, add default columns
        # This ensures the pipeline doesn't break if ML module has issues
        print(f"⚠️ Warning: Risk prediction failed: {e}")
        
        df['risk_probability'] = 0.0
        df['high_risk_predicted'] = 0
        df['risk_category'] = 'Low'
        
        return df


def get_risk_summary(df: pd.DataFrame) -> dict:
    """
    Generate summary statistics about predicted risks.
    
    Args:
        df: DataFrame with 'risk_probability' and 'risk_category' columns
    
    Returns:
        Dictionary with:
        - high_risk_count: Number of products with high risk
        - medium_risk_count: Number of products with medium risk
        - low_risk_count: Number of products with low risk
        - avg_risk_probability: Average risk probability across all products
        - max_risk_product: Product with highest risk probability
        - max_risk_probability: Highest risk probability value
    """
    
    try:
        summary = {
            'high_risk_count': int((df['risk_category'] == 'High').sum()),
            'medium_risk_count': int((df['risk_category'] == 'Medium').sum()),
            'low_risk_count': int((df['risk_category'] == 'Low').sum()),
            'avg_risk_probability': float(df['risk_probability'].mean()),
            'max_risk_product': df.loc[df['risk_probability'].idxmax(), 'product']
            if 'product' in df.columns else 'N/A',
            'max_risk_probability': float(df['risk_probability'].max()),
        }
        return summary
    
    except Exception as e:
        print(f"⚠️ Warning: Failed to generate risk summary: {e}")
        return {
            'high_risk_count': 0,
            'medium_risk_count': 0,
            'low_risk_count': 0,
            'avg_risk_probability': 0.0,
            'max_risk_product': 'N/A',
            'max_risk_probability': 0.0,
        }
