# Streamlit Dashboard - Quick Start Guide

## 🚀 Launch the Dashboard

```bash
# Navigate to project directory
cd "d:\0 to 1cr\Pratice\Review system\project"

# Run dashboard
streamlit run app.py

# Opens in browser at http://localhost:8501
```

---

## 📊 Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 Review Intelligence Engine                                   │
│ Intelligent review analysis and prioritization system           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ⚙️ Control Panel                                                │
│ ├─ 🔄 Fetch Data [Button]                                      │
│ ├─ 🗑️  Clear Cache [Button]                                    │
│ ├─ Status: ✅ Data loaded / ⏳ Waiting                          │
│ └─ Last refresh: HH:MM:SS                                       │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ 🔍 FILTER DATA                                                  │
│ ├─ 📦 Products: [Multi-select dropdown]                         │
│ ├─ 📅 Date Range: [Optional date picker]                        │
│ └─ ⚠️  Severity: [Slider 0.0-1.0]                              │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ 📊 KEY PERFORMANCE INDICATORS                                   │
│ ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│ │ Revenue      │ Total        │ % Negative   │ Top Risk     │  │
│ │ at Risk      │ Reviews      │ Reviews      │ Product      │  │
│ │              │              │              │              │  │
│ │ ₹2,300,000   │ 500          │ 35.2%        │ ProductA     │  │
│ └──────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ 📈 PRIORITIZATION ANALYSIS                                      │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │                                                             │ │
│ │  Product Priority Quadrant Matrix                          │ │
│ │                                                             │ │
│ │  ┌─────────────────────────────────────────────────────┐  │ │
│ │  │        VIP        │           FIRE-FIGHT            │  │ │
│ │  │       NUDGE       │   (High priority products)     │  │ │
│ │  │                   │                                 │  │ │
│ │  ├─────────────────────────────────────────────────────┤  │ │
│ │  │                   │                                 │  │ │
│ │  │       NOISE       │          SLOW BURN             │  │ │
│ │  │  (Track)          │   (Monitor)                    │  │ │
│ │  └─────────────────────────────────────────────────────┘  │ │
│ │                                                             │ │
│ │  [Interactive Plotly Chart with hover data]               │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ 🎯 PRODUCT RANKING BY PRIORITY                                  │
│ ┌────────────┬────────┬────────┬────────┬────────┬────────────┐ │
│ │ Product    │ Reviews│ Rating │ Neg %  │ Score  │ Revenue    │ │
│ ├────────────┼────────┼────────┼────────┼────────┼────────────┤ │
│ │ Product-A  │  150   │  2.3   │ 45.2%  │ 0.89   │ ₹2,100,000 │ │
│ │ Product-B  │  120   │  3.8   │ 12.5%  │ 0.45   │ ₹450,000   │ │
│ │ Product-C  │  230   │  4.1   │  8.3%  │ 0.22   │ ₹89,000    │ │
│ └────────────┴────────┴────────┴────────┴────────┴────────────┘ │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ 📊 Data Preview | 📈 Charts | ℹ️ About                          │
│                                                                   │
│ [Tabs for additional analysis and information]                   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 How to Use

### Step 1: Fetch Data
```
1. Click "🔄 Fetch Data" button in sidebar
2. Dashboard fetches reviews from API (paginated, max 5 pages)
3. Runs full scoring pipeline automatically
4. Displays: "✅ Loaded XXX reviews across YYY products"
```

### Step 2: Apply Filters
```
1. Select products from dropdown (or keep defaults)
2. Optional: Enable date range filter
3. Adjust severity threshold slider
4. Results update automatically
```

### Step 3: Analyze Quadrant Chart
```
1. View bubble positions:
   - Left side: Low negative ratio (good)
   - Right side: High negative ratio (concerning)
   - Bottom: Low revenue at risk (less impact)
   - Top: High revenue at risk (critical)

2. Bubble colors:
   - Red: High priority (top-right)
   - Orange: Medium priority
   - Green: Low priority (bottom-left)

3. Bubble size: Larger = higher final score

4. Read quadrant label:
   - Fire-Fight: Immediate action needed
   - VIP Nudge: Engage key customers
   - Slow Burn: Monitor closely
   - Noise: Lower priority
```

### Step 4: Review Ranking Table
```
1. Products sorted by final_score (highest first)
2. Click column headers to sort (Streamlit's built-in feature)
3. Hover over metrics for full precision values
4. Use for execution priority
```

### Step 5: Explore Additional Analysis
```
Click tabs at bottom:
- "📊 Data Preview" - View individual reviews
- "📈 Charts" - Rating distribution, impact score histogram
- "ℹ️ About" - System explanation and metrics guide
```

---

## 📊 Key Metrics Explained

| Metric | Range | Interpretation |
|--------|-------|-----------------|
| **Revenue at Risk** | ₹0+ | Total LTV of negative reviews |
| **Total Reviews** | 1+ | Reviews analyzed |
| **% Negative** | 0-100% | Rating ≤ 2 percentage |
| **Final Score** | 0.0-1.0 | Product priority (1.0 = highest) |
| **Negative Ratio** | 0-100% | Proportion of critical issues |

---

## 🎯 Decision Framework

### Fire-Fight Quadrant (Top-Right)
**Action**: Immediate investigation required
- High product risk + High revenue impact
- **Next Steps**: 
  1. Identify root cause
  2. Contact affected customers
  3. Issue hotfix/patch
  4. Monitor closely post-fix

### VIP Nudge Quadrant (Top-Left)
**Action**: Engage key customers
- Low product risk + High value customers
- **Next Steps**:
  1. Reach out personally
  2. Address specific concerns
  3. Offer loyalty incentive
  4. Prevent churn

### Slow Burn Quadrant (Bottom-Right)
**Action**: Monitor and investigate
- High product risk + Lower revenue impact
- **Next Steps**:
  1. Track trend over time
  2. Set up alerts for escalation
  3. Plan long-term improvement
  4. Test in beta before rollout

### Noise Quadrant (Bottom-Left)
**Action**: Track and categorize
- Low product risk + Low revenue impact
- **Next Steps**:
  1. Batch similar issues
  2. Plan quarterly review
  3. Low urgency fixes
  4. Monitor for spikes

---

## 🐛 Troubleshooting

### Issue: "No reviews fetched"
**Cause**: API server down or network issue
**Fix**: 
1. Check internet connection
2. Verify API endpoint is accessible
3. Try again in 1 minute
4. Check error logs: `tail -f review_system.log`

### Issue: "No reviews match selected filters"
**Cause**: Filters too restrictive
**Fix**:
1. Reduce severity threshold
2. Expand date range
3. Select all products
4. Click "Clear Cache" and try again

### Issue: Dashboard runs slow
**Cause**: Large dataset or complex computation
**Fix**:
1. Reduce max_pages in fetch (currently 5)
2. Apply date range filter
3. Filter to specific products
4. Clear cache and reload

### Issue: Charts not rendering
**Cause**: Missing data or invalid values
**Fix**:
1. Verify data was fetched successfully
2. Check for NaN values
3. Ensure at least 2 products in data
4. Try different filter settings

---

## 💡 Pro Tips

1. **Save Filter Preferences**
   - Selected products persist in state
   - Reopen browser tab to restore state
   - Click "Clear Cache" to reset to defaults

2. **Performance Optimization**
   - Keep max ~500 reviews for best performance
   - Use date filters to reduce dataset
   - Filter to top 5-10 products for detailed analysis

3. **Decision Making**
   - Focus on Fire-Fight quadrant first
   - Use Final Score as ranking metric
   - Monitor Slow Burn tab for emerging issues
   - Track quadrant movement over time

4. **Data Export**
   - Copy data from table (Ctrl+A, Ctrl+C)
   - Export to CSV (feature coming soon)
   - Screenshot charts for presentations

---

## 📞 Support & Issues

**For bugs or questions**:
1. Check error message at top of screen
2. Open browser console (F12 → Console tab)
3. Check logs: `tail -f review_system.log`
4. Review [DASHBOARD_IMPLEMENTATION.md](DASHBOARD_IMPLEMENTATION.md) for detailed docs

**Common Log Files**:
- `review_system.log` - System logs and errors
- `.streamlit/logs/` - Streamlit debug logs

---

## ✅ Verification Checklist

Before using dashboard in production:

- [ ] Dashboard loads without errors
- [ ] "Fetch Data" button works
- [ ] KPI cards show non-zero values
- [ ] Quadrant chart displays bubbles
- [ ] Table shows products sorted by score
- [ ] Filters update results
- [ ] All 24 tests passing
- [ ] API credentials configured
- [ ] Error logs monitored
- [ ] Performance acceptable (< 5 sec load time)

---

## 🚀 Production Deployment

### Option 1: Streamlit Cloud (Free)
```bash
# Push to GitHub
git add .
git commit -m "Production dashboard"
git push

# Go to https://streamlit.io/cloud
# Deploy directly from GitHub repo
```

### Option 2: Docker Container
```bash
# Build image
docker build -t rie-dashboard .

# Run container
docker run -p 8501:8501 rie-dashboard
```

### Option 3: Linux Server
```bash
# Install dependencies
pip install -r requirements.txt

# Run as service
nohup streamlit run app.py > app.log 2>&1 &

# Monitor with PM2
pm2 start "streamlit run app.py" --name "rie-dashboard"
```

---

## 📚 Related Documentation

- [DASHBOARD_IMPLEMENTATION.md](DASHBOARD_IMPLEMENTATION.md) - Detailed implementation guide
- [ERROR_HANDLING_LOGGING.md](ERROR_HANDLING_LOGGING.md) - Error handling system
- [README.md](README.md) - Project overview
- [ROBUSTNESS_QUICK_REFERENCE.md](ROBUSTNESS_QUICK_REFERENCE.md) - Data robustness layer

---

**Dashboard Status**: ✅ **PRODUCTION-READY**  
**Last Updated**: April 9, 2026  
**Test Coverage**: 24/24 tests passing

