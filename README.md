# Review Intelligence Engine (RIE) — IEEE Ignite Hackathon 2026

**Team Name:** [Your Team Name]
**Track / Problem Statement:** AI for Business Intelligence & CX Optimization
**Hackathon:** IEEE Ignite 2026

---

# 📑 Table of Contents

* Introduction
* Problem Statement
* Our Solution
* Tech Stack
* Architecture Overview
* Getting Started
* Demo
* ML / AI Models
* Team

---

# 🚀 Introduction

Review Intelligence Engine (RIE) is an AI-powered system that analyzes customer reviews to prioritize business issues based on **financial impact rather than frequency**. It transforms raw feedback into actionable insights by combining machine learning with intelligent summarization.

---

# ❗ Problem Statement

Businesses receive thousands of customer reviews, but current systems prioritize issues based on **volume**, not **business impact**.

This leads to:

* High-value customer issues being ignored
* Revenue loss due to unresolved critical problems
* Poor prioritization by CX and product teams

Existing tools fail to answer:

> “Which problem is costing us the most money?”

---

# 💡 Our Solution

RIE introduces an **impact-first decision system**:

* Evaluates each review based on **Customer Importance (CIS)** and **Severity**
* Calculates **Impact Score = CIS × Severity**
* Aggregates product-level insights
* Identifies **Revenue at Risk**
* Uses ML to predict risk probability
* Uses LLM (Grok) to generate business insights

---

### 🔥 Key Differentiation:

* Not all reviews are treated equally
* Focus on **high-value customers + severe issues**
* Combines:

  * ML (quantitative intelligence)
  * LLM (qualitative insights)

---

# 🛠 Tech Stack

| Layer           | Technology                         |
| --------------- | ---------------------------------- |
| Frontend        | Streamlit                          |
| Backend         | Python                             |
| Data Processing | Pandas, NumPy                      |
| ML Model        | Scikit-learn (Logistic Regression) |
| NLP / LLM       | Grok API                           |
| Visualization   | Plotly / Streamlit Charts          |
| Deployment      | Local / Cloud-ready                |

---

# 🏗 Architecture Overview

See `docs/architecture.md` for detailed breakdown.

### High-Level Pipeline:

```
Raw Data (API / CSV)
        ↓
Data Cleaning
        ↓
Feature Engineering
        ↓
ML Model (Risk Prediction)
        ↓
Aggregation (Product Level)
        ↓
Metrics Calculation
        ↓
LLM (Grok Insights)
        ↓
Streamlit Dashboard
```

---

# ⚙️ Core Logic

### 1. Customer Importance Score (CIS)

Weighted combination of:

* Lifetime Value (LTV)
* Order Value
* Repeat Purchases
* Verified Purchase
* Helpful Votes
* Recency

---

### 2. Severity Score

Based on:

* Rating
* Sentiment

---

### 3. Impact Score

```
Impact = CIS × Severity
```

---

### 4. Product Priority Score (PPS)

Based on:

* Review Frequency
* Average Order Value
* Repeat Rate
* Rating Drop
* Negative Ratio

---

### 5. Final Score

```
Final Score = log(1 + ΣImpact) × (1 + PPS)
```

---

### 6. Revenue at Risk

```
Sum of LTV where:
rating ≤ 2 AND sentiment = negative
```

---

### 7. Decision Matrix

Using percentile thresholds:

* Fire-Fight → High Impact, High Frequency
* VIP Nudge → High Impact, Low Frequency
* Slow Burn → Low Impact, High Frequency
* Noise → Low Impact, Low Frequency

---

# ▶️ Getting Started

## Prerequisites

* Python ≥ 3.10
* Node.js ≥ 18 (if frontend separated)

---

## Installation

```bash
git clone https://github.com/[your-org]/[your-repo].git
cd [your-repo]
```

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

---

## Environment Setup

```bash
cp env.example .env
```

Add:

* GROK_API_KEY
* Any dataset/API configs

---

## Running the Project

```bash
cd backend
streamlit run app.py
```

App runs on:

```
http://localhost:8501
```

---

# 📊 Dashboard Features

### KPI Cards:

* Total Revenue at Risk
* Total Reviews
* % Negative Reviews
* Avg Risk Probability

---

### Visualizations:

* Impact vs Frequency (Quadrant)
* Revenue at Risk (Bar Chart)
* Rating vs Risk (Scatter)
* High Risk Share (Donut)
* Issue Breakdown (Stacked Bar)

---

### Product Table:

* Product Name
* Final Score
* Revenue at Risk
* Risk Probability
* Decision Quadrant

---

### AI Insights Panel:

* LLM-generated recommendations
* Business-focused summaries

---

# 🎥 Demo

### Screenshots

| Feature            | Screenshot             |
| ------------------ | ---------------------- |
| Dashboard Overview | demo/screenshots/1.png |
| Quadrant Analysis  | demo/screenshots/2.png |

---

### Video Demo

[Add YouTube / Drive Link]

---

# 🤖 ML / AI Models

See `docs/ml-ai.md` for full details.

---

## ML Model

**Model:** Logistic Regression

### Objective:

Predict risk probability of a review

```
risk_label = 1 if rating ≤ 2 else 0
```

---

### Outputs:

* Risk Probability
* High-Risk Classification

---

## LLM Integration (Grok)

### Role:

* Converts ML outputs into business insights

### Input:

* Aggregated metrics
* Top risky products

### Output:

* Risk explanation
* Business recommendations
* Actionable insights

---

# 👥 Team

| Name            | Role                        | GitHub        |
| --------------- | ---------------------       | ------------- |
| Akshat Mukkawar | BAckend, ML & System Design | @Sungjinwoo26 |
| [Abin Johnson]  |  Backend & LLM              | @Dynamo80     |
| [Palak Agarwal] |  Frontend                   | @Palakkk168   |


---

# 📜 License

MIT License

---

# 🧠 Core Principle

> Prioritize problems based on **business impact**, not just volume

> Combine **Machine Learning (numbers)** + **LLM (insight)**

---

# 🚀 Future Scope

* Explainable AI (why risk is high)
* Clustering (issue grouping)
* Real-time alerts
* Chat-based CX assistant
* Auto ticket generation

---

**Submitted to IEEE Ignite Hackathon 2026**
