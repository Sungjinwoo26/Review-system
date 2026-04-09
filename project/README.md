# 📊 Review Intelligence Engine

A comprehensive MVP for analyzing customer reviews, identifying product issues, and prioritizing business actions using machine learning and data science.

## 🎯 What This Does

**Problem:** Companies get thousands of reviews but don't know which ones matter.

**Solution:** This engine analyzes reviews to answer:
- Which customers are most valuable?
- Which products have the biggest issues?
- What should we fix first?

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone <repo-url>
cd project

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### Run Application

```bash
streamlit run app.py
```

Visit: **http://localhost:8501**

## 📁 Project Structure

```
project/
├── app.py                          # Main Streamlit dashboard
├── requirements.txt                # Python dependencies
│
├── services/                       # Core business logic
│   ├── ingestion.py               # Fetch reviews from API with retry logic
│   ├── preprocessing.py           # Clean & normalize data
│   ├── features.py                # Engineer severity, recency, sentiment
│   ├── scoring.py                 # Compute customer & impact scores
│   ├── aggregation.py             # Product-level metrics
│   └── decision.py                # Generate action recommendations
│
├── utils/                          # Shared utilities
│   ├── cache.py                   # Smart caching (5-minute TTL)
│   ├── error_handler.py           # Error handling & retry logic
│   └── logger.py                  # Logging setup
│
├── tests/                          # Unit tests
│   ├── test_preprocessing.py       # Test data cleaning
│   ├── test_features.py            # Test feature engineering
│   ├── test_scoring.py             # Test scoring logic
│   └── test_api.py                 # Test API integration
│
└── DEPLOYMENT_GUIDE.md             # Complete deployment & testing guide
```

## 🔄 Data Pipeline

```
Raw Reviews (API)
       ↓
   [INGESTION] → Fetch with pagination & retry
       ↓
   [PREPROCESSING] → Handle nulls, normalize features
       ↓
   [FEATURES] → Severity, recency, sentiment scoring
       ↓
   [SCORING] → Customer importance & impact calculation
       ↓
   [AGGREGATION] → Product-level metrics
       ↓
   [DECISION] → Action recommendations
       ↓
   [DASHBOARD] → Visualize & prioritize
```

## 📊 Key Metrics

### Customer Importance Score (CIS)
Measures how valuable the customer is (0-1):
- 30% Customer LTV
- 20% Order Value
- 15% Repeat Customer
- 10% Verified Purchase
- 10% Helpful Votes
- 15% Recency

### Impact Score
How much the review matters to business:
```
Impact = CIS × (0.6 × Severity + 0.4 × Sentiment)
```

### Final Priority Score
Combined business importance:
```
Priority = log(1 + Total Impact) × (1 + PPS)
```

## 🧪 Testing

### Run All Tests
```bash
pytest tests/ -v --cov=services
```

### Run Specific Test
```bash
pytest tests/test_preprocessing.py -v
```

### Coverage Report
```bash
pytest tests/ --cov=services --cov-report=html
open htmlcov/index.html
```

## 🛡️ Features

✅ **Robust API Integration**
- Exponential backoff retry logic
- Graceful error handling
- Request timeout management

✅ **Intelligent Caching**
- 5-minute smart cache (TTL)
- Manual cache clearing
- Reduces API calls

✅ **Comprehensive Error Handling**
- Try-catch at every layer
- User-friendly error messages
- Detailed logging

✅ **Data Validation**
- Check required columns
- Handle missing values
- Validate numeric ranges

✅ **Performance Optimized**
- Vectorized NumPy operations
- Pagination for large datasets
- Streamlit caching

✅ **Security**
- No API keys in frontend
- Server-side API calls
- Environment-based config

## 🚀 Deployment

### Streamlit Cloud (Easiest)
1. Push code to GitHub
2. Go to https://share.streamlit.io
3. Select repository & main file
4. Click "Deploy"

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

### Other Options
- **Render.com** — Free tier (750 hrs/month)
- **Railway.app** — Free $5/month tier
- **Heroku** — Paid (from $7/month)

## 📈 Dashboard Features

**📥 Data Ingestion Tab**
- Fetch reviews from API
- Run full pipeline
- Data validation & preview

**📊 Review Analytics Tab**
- Rating distribution
- Impact score histogram
- Top problematic reviews
- KPI metrics

**🎯 Product Priorities Tab**
- Product ranking table
- Priority heatmap
- Revenue at risk
- Recommended actions

**ℹ️ About Tab**
- How it works
- Deployment options
- Troubleshooting

## 🔧 Configuration

### Environment Variables
Create `.streamlit/secrets.toml`:
```toml
API_ENDPOINT = "https://mosaicfellowship.in/api/data/cx/reviews"
CACHE_TTL = 300
MAX_RETRIES = 3
LOG_LEVEL = "INFO"
```

### API Configuration
Adjust pagination limits in `app.py`:
```python
# Fetch fewer pages for faster testing
raw_df = fetch_reviews(max_pages=5)
```

## 📝 Logging

Logs are captured at multiple levels:

```python
from utils.logger import log_event, log_error

# Log successful events
log_event("FETCH_COMPLETE", {"total_reviews": 150})

# Log errors with context
log_error("API_FAILED", "Timeout", {"page": 3})
```

View logs:
- **Console:** Terminal output
- **Streamlit Cloud:** Dashboard → Manage app → View logs

## 🚨 Troubleshooting

### Issue: API Returns Empty Data
```python
# Check if endpoint is responding
curl https://mosaicfellowship.in/api/data/cx/reviews?page=1&limit=10
```

### Issue: Missing Required Columns
```python
# Verify column names in API response
raw_df = fetch_reviews(max_pages=1)
print(raw_df.columns)
```

### Issue: Slow Performance
```python
# Check data size
print(f"Processing {len(df)} reviews")

# Increase cache timeout
@cached(ttl=600)  # 10 minutes instead of 5
```

### Issue: NaN Values in Output
```python
# Check preprocessing defaults
print(df.isnull().sum())

# Verify normalization clipping
print((df['ltv_norm'] >= 0).all() and (df['ltv_norm'] <= 1).all())
```

## 📚 Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) — Complete deployment & testing guide
- [services/](services/) — Service docstrings explain each function
- [utils/](utils/) — Utility functions with inline comments

## 🎓 Learning Resources

- **Streamlit Docs:** https://docs.streamlit.io
- **Pandas:** https://pandas.pydata.org/docs/
- **NumPy:** https://numpy.org/doc/
- **Pytest:** https://docs.pytest.org/

## 📊 Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| App Response Time | < 3s | ✅ |
| Test Coverage | > 80% | ✅ |
| Error Handling | All cases | ✅ |
| Data Processing | > 500 reviews | ✅ |
| Mobile Responsive | All devices | ✅ |

## 🤝 Contributing

1. Create a new branch: `git checkout -b feature/your-feature`
2. Make changes and test: `pytest tests/ -v`
3. Commit: `git commit -m "Add feature"`
4. Push: `git push origin feature/your-feature`
5. Open Pull Request

## 📄 License

MIT License - See LICENSE file for details

## 📧 Support

For questions or issues:
1. Check [troubleshooting](#-troubleshooting) section
2. Review logs in Streamlit dashboard
3. Contact development team

---

**Built with ❤️ using Python, Pandas, NumPy, and Streamlit**
