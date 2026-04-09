"""
ML Model Training Module

Trains a Logistic Regression model to predict product risk probability.
Uses percentile-based labeling to identify high-risk products.

Input: aggregated_df with engineered features and final_score
Output: Trained Logistic Regression model ready for prediction
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import warnings

warnings.filterwarnings('ignore')


def create_risk_labels(df: pd.DataFrame, quantile: float = 0.75) -> pd.DataFrame:
    """
    Create binary risk labels using percentile-based thresholding.
    
    This approach:
    - Uses the existing final_score to determine high-risk products
    - Products in top 25% (by default) of final_score → high_risk = 1
    - Products in bottom 75% → high_risk = 0
    
    Rationale:
    - Final score already represents business-validated risk assessment
    - Top 25% products require immediate attention/action
    - Creates balanced or slightly imbalanced dataset (depending on data distribution)
    
    Args:
        df: Product-level aggregated DataFrame with 'final_score' column
        quantile: Percentile threshold (default: 0.75 for top 25%)
    
    Returns:
        DataFrame with 'high_risk' binary column added
    """
    df = df.copy()
    
    # Calculate the threshold at the specified quantile
    threshold = df['final_score'].quantile(quantile)
    
    # Create binary risk label
    # Products with final_score > threshold are labeled as high_risk
    df['high_risk'] = (df['final_score'] > threshold).astype(int)
    
    return df


def train_risk_model(df: pd.DataFrame, features: list, quantile: float = 0.75):
    """
    Train Logistic Regression model to predict product risk.
    
    Model Configuration:
    - Algorithm: Logistic Regression (interpretable, fast, production-ready)
    - Solver: lbfgs (accurate when data is small-medium)
    - Max iterations: 1000 (sufficient for convergence)
    - Scaling: StandardScaler (critical for LR convergence)
    
    Args:
        df: Product-level aggregated DataFrame with features and final_score
        features: List of feature column names for model training
        quantile: Percentile for binary labeling (default: 0.75)
    
    Returns:
        Dictionary containing:
        - 'model': Trained LogisticRegression object
        - 'scaler': StandardScaler object (for prediction)
        - 'features': List of features used for training
        - 'threshold': Score threshold for high_risk classification
        - 'training_stats': Dict with training metrics
    
    Note:
        - Returns dict (not just model) to enable stateless prediction later
        - Scaler must be included because it was fitted on training data
    """
    
    df = df.copy()
    
    # Step 1: Create risk labels
    df = create_risk_labels(df, quantile=quantile)
    
    # Step 2: Prepare features matrix X and target vector y
    X = df[features].values
    y = df['high_risk'].values
    
    # Step 3: Scale features
    # Logistic Regression is distance-based and benefits from scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Step 4: Train model
    model = LogisticRegression(
        max_iter=1000,
        solver='lbfgs',
        random_state=42,
        n_jobs=-1  # Use all available CPU cores
    )
    model.fit(X_scaled, y)
    
    # Step 5: Calculate training stats
    train_score = model.score(X_scaled, y)
    threshold = df['final_score'].quantile(quantile)
    
    training_stats = {
        'training_accuracy': float(train_score),
        'high_risk_count': int(y.sum()),
        'low_risk_count': int((1 - y).sum()),
        'model_threshold': float(threshold),
        'quantile_used': quantile,
        'num_features': len(features),
        'samples_trained': len(df)
    }
    
    return {
        'model': model,
        'scaler': scaler,
        'features': features,
        'threshold': threshold,
        'training_stats': training_stats
    }


def get_feature_importance(model_dict: dict) -> pd.DataFrame:
    """
    Extract feature importance from trained Logistic Regression model.
    
    For Logistic Regression:
    - Coefficients represent the log-odds change per unit feature change
    - Larger absolute coefficients = stronger predictive power
    - Positive coefficients = increased risk probability
    - Negative coefficients = decreased risk probability
    
    Args:
        model_dict: Dictionary returned from train_risk_model()
    
    Returns:
        DataFrame with feature names and importance scores, sorted by absolute importance
    """
    
    model = model_dict['model']
    features = model_dict['features']
    
    # Extract coefficients (importance scores)
    importance = model.coef_[0]
    
    # Create importance dataframe
    importance_df = pd.DataFrame({
        'feature': features,
        'coefficient': importance,
        'abs_coefficient': np.abs(importance)
    }).sort_values('abs_coefficient', ascending=False)
    
    return importance_df
