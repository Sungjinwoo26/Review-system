const PRODUCTS = [
  { name: "Atlas Desk", date: "2026-04-08", finalScore: 0.91, revenueAtRisk: 920000, riskProbability: 0.92, negativePct: 34.2, quadrant: "Fire Fight", frequency: 88, impact: 86, rating: 2.8, trend: "Rising", severity: "High", totalReviews: 4860, issues: { delivery: 162, quality: 204, packaging: 74, support: 88 } },
  { name: "Pulse Earbuds", date: "2026-04-09", finalScore: 0.84, revenueAtRisk: 640000, riskProbability: 0.86, negativePct: 29.5, quadrant: "Fire Fight", frequency: 79, impact: 78, rating: 3.1, trend: "Rising", severity: "High", totalReviews: 3980, issues: { delivery: 104, quality: 176, packaging: 58, support: 66 } },
  { name: "North Mug", date: "2026-04-03", finalScore: 0.73, revenueAtRisk: 410000, riskProbability: 0.74, negativePct: 21.3, quadrant: "VIP Nudge", frequency: 34, impact: 82, rating: 3.6, trend: "Stable", severity: "Medium", totalReviews: 2510, issues: { delivery: 62, quality: 84, packaging: 40, support: 29 } },
  { name: "Harbor Lamp", date: "2026-03-30", finalScore: 0.68, revenueAtRisk: 285000, riskProbability: 0.69, negativePct: 24.8, quadrant: "Slow Burn", frequency: 68, impact: 44, rating: 3.4, trend: "Rising", severity: "Medium", totalReviews: 2715, issues: { delivery: 58, quality: 76, packaging: 49, support: 44 } },
  { name: "Summit Bottle", date: "2026-03-26", finalScore: 0.61, revenueAtRisk: 198000, riskProbability: 0.63, negativePct: 17.2, quadrant: "Slow Burn", frequency: 59, impact: 39, rating: 3.9, trend: "Stable", severity: "Medium", totalReviews: 2330, issues: { delivery: 47, quality: 53, packaging: 61, support: 25 } },
  { name: "Vale Chair", date: "2026-03-22", finalScore: 0.57, revenueAtRisk: 144000, riskProbability: 0.58, negativePct: 14.1, quadrant: "Noise", frequency: 24, impact: 34, rating: 4.1, trend: "Falling", severity: "Low", totalReviews: 1820, issues: { delivery: 18, quality: 31, packaging: 22, support: 17 } },
  { name: "Cove Kettle", date: "2026-03-18", finalScore: 0.51, revenueAtRisk: 102000, riskProbability: 0.49, negativePct: 12.4, quadrant: "Noise", frequency: 18, impact: 28, rating: 4.2, trend: "Stable", severity: "Low", totalReviews: 1585, issues: { delivery: 14, quality: 20, packaging: 19, support: 12 } },
  { name: "Drift Frame", date: "2026-03-14", finalScore: 0.46, revenueAtRisk: 89000, riskProbability: 0.44, negativePct: 10.9, quadrant: "Noise", frequency: 16, impact: 24, rating: 4.4, trend: "Falling", severity: "Low", totalReviews: 1420, issues: { delivery: 11, quality: 18, packaging: 15, support: 10 } }
];

const state = {
  selectedProducts: [],
  startDate: "2026-03-01",
  endDate: "2026-04-10",
  severity: "All",
  threshold: 0.7,
  search: "",
  sortKey: "score",
  sortDirection: "desc",
  filteredProducts: [...PRODUCTS],
  lastInsight: "",
  lastLlmPrompt: "",
  lastLlmOutput: ""
};

const tooltip = document.getElementById("chart-tooltip");

document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  hydrateFilters();
  bindEvents();
  applyFilters({ withLoading: false });
});

function setupNavigation() {
  const toggle = document.querySelector(".nav-toggle");
  const topbar = document.querySelector(".topbar");
  toggle.addEventListener("click", () => {
    const open = topbar.classList.toggle("menu-open");
    toggle.setAttribute("aria-expanded", String(open));
  });

  document.querySelectorAll("[data-scroll-target]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector(button.dataset.scrollTarget)?.scrollIntoView({ behavior: "smooth" });
    });
  });
}

function hydrateFilters() {
  const productFilter = document.getElementById("product-filter");
  PRODUCTS.forEach((product) => {
    const option = document.createElement("option");
    option.value = product.name;
    option.textContent = product.name;
    productFilter.appendChild(option);
  });

  document.getElementById("date-start").value = state.startDate;
  document.getElementById("date-end").value = state.endDate;
  document.getElementById("severity-filter").value = state.severity;
  document.getElementById("risk-threshold").value = String(state.threshold);
  document.getElementById("threshold-value").textContent = state.threshold.toFixed(2);
}

function bindEvents() {
  document.getElementById("risk-threshold").addEventListener("input", (event) => {
    document.getElementById("threshold-value").textContent = Number(event.target.value).toFixed(2);
  });

  document.getElementById("apply-filters").addEventListener("click", () => applyFilters({ withLoading: true }));
  document.getElementById("reset-filters").addEventListener("click", resetFilters);
  document.getElementById("refresh-dashboard").addEventListener("click", () => applyFilters({ withLoading: true, refreshTimestamp: true }));
  document.getElementById("table-search").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderTable(state.filteredProducts);
  });

  document.querySelectorAll(".sort-button").forEach((button) => {
    button.addEventListener("click", () => {
      const { sort } = button.dataset;
      if (state.sortKey === sort) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = sort;
        state.sortDirection = sort === "name" || sort === "quadrant" || sort === "trend" ? "asc" : "desc";
      }
      renderTable(state.filteredProducts);
    });
  });

  document.getElementById("generate-insights").addEventListener("click", () => generateInsights(true));
  document.getElementById("refresh-insights").addEventListener("click", () => generateInsights(false));
  document.getElementById("copy-insights").addEventListener("click", copyInsights);
  document.getElementById("debug-toggle").addEventListener("click", toggleDebug);
}

function resetFilters() {
  state.selectedProducts = [];
  state.startDate = "2026-03-01";
  state.endDate = "2026-04-10";
  state.severity = "All";
  state.threshold = 0.7;
  state.search = "";

  const productFilter = document.getElementById("product-filter");
  Array.from(productFilter.options).forEach((option) => {
    option.selected = false;
  });

  document.getElementById("date-start").value = state.startDate;
  document.getElementById("date-end").value = state.endDate;
  document.getElementById("severity-filter").value = state.severity;
  document.getElementById("risk-threshold").value = String(state.threshold);
  document.getElementById("threshold-value").textContent = state.threshold.toFixed(2);
  document.getElementById("table-search").value = "";

  applyFilters({ withLoading: true });
}

function readFilterInputs() {
  const selectedProducts = Array.from(document.getElementById("product-filter").selectedOptions).map((option) => option.value);
  state.selectedProducts = selectedProducts;
  state.startDate = document.getElementById("date-start").value;
  state.endDate = document.getElementById("date-end").value;
  state.severity = document.getElementById("severity-filter").value;
  state.threshold = Number(document.getElementById("risk-threshold").value);
}

function applyFilters({ withLoading, refreshTimestamp = false }) {
  readFilterInputs();

  const run = () => {
    state.filteredProducts = PRODUCTS.filter((product) => {
      const matchesProduct = !state.selectedProducts.length || state.selectedProducts.includes(product.name);
      const matchesDate = product.date >= state.startDate && product.date <= state.endDate;
      const matchesSeverity = state.severity === "All" || product.severity === state.severity;
      const matchesThreshold = product.riskProbability >= state.threshold;
      return matchesProduct && matchesDate && matchesSeverity && matchesThreshold;
    });

    renderAll();
    if (refreshTimestamp) {
      updateTimestamp();
    }
  };

  if (!withLoading) {
    run();
    return;
  }

  const surfaces = document.querySelectorAll(".kpi-grid, .main-grid, .chart-grid, .lower-chart-grid, .insights-panel, .debug-panel");
  surfaces.forEach((surface) => surface.classList.add("is-loading"));
  window.setTimeout(() => {
    run();
    surfaces.forEach((surface) => surface.classList.remove("is-loading"));
  }, 260);
}

function renderAll() {
  const products = state.filteredProducts;
  renderKpis(products);
  renderTable(products);
  renderQuadrantChart(products);
  renderRevenueChart(products);
  renderRatingRiskChart(products);
  renderIssuesChart(products);
  renderRiskShareChart(products);
  renderDebug(products);
  generateInsights(false, true);
}

function renderKpis(products) {
  const totalRevenue = products.reduce((sum, item) => sum + item.revenueAtRisk, 0);
  const totalReviews = products.reduce((sum, item) => sum + item.totalReviews, 0);
  const weightedNegative = totalReviews ? products.reduce((sum, item) => sum + (item.negativePct / 100) * item.totalReviews, 0) / totalReviews : 0;
  const avgProbability = products.length ? products.reduce((sum, item) => sum + item.riskProbability, 0) / products.length : 0;
  const highRiskCount = products.filter((item) => item.severity === "High").length;

  const cards = [
    { title: "Total Revenue at Risk", value: formatCurrency(totalRevenue), note: `${products.length || 0} products in view` },
    { title: "Total Reviews", value: formatNumber(totalReviews), note: "Across filtered products" },
    { title: "Percentage Negative Reviews", value: `${(weightedNegative * 100).toFixed(1)}%`, note: weightedNegative > 0.22 ? "Above baseline" : "Within baseline" },
    { title: "Average Risk Probability", value: avgProbability.toFixed(2), note: "Model-weighted average" },
    { title: "High Risk Products", value: String(highRiskCount), note: "Severity classified as High" }
  ];

  document.getElementById("kpi-grid").innerHTML = cards.map((card) => `
    <article class="card kpi-card">
      <p>${card.title}</p>
      <strong>${card.value}</strong>
      <span>${card.note}</span>
    </article>
  `).join("");
}

function renderTable(products) {
  const body = document.getElementById("product-table-body");
  const empty = document.getElementById("table-empty");
  const searchable = products.filter((product) => product.name.toLowerCase().includes(state.search));
  const sorted = [...searchable].sort((a, b) => compareRows(a, b, state.sortKey, state.sortDirection));

  if (!sorted.length) {
    body.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }

  empty.classList.add("hidden");
  body.innerHTML = sorted.map((product) => `
    <tr class="clickable" data-row="${product.name}">
      <td>${product.name}</td>
      <td>${product.finalScore.toFixed(2)}</td>
      <td>${formatCurrency(product.revenueAtRisk)}</td>
      <td>${product.riskProbability.toFixed(2)}</td>
      <td>${product.negativePct.toFixed(1)}%</td>
      <td><span class="${quadrantTone(product.quadrant)}">${product.quadrant}</span></td>
      <td>${renderTrend(product.trend)}</td>
    </tr>
  `).join("");

  body.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => {
      row.classList.add("row-selected");
      window.setTimeout(() => row.classList.remove("row-selected"), 900);
    });
  });
}

function renderQuadrantChart(products) {
  const target = document.getElementById("quadrant-chart");
  if (!products.length) {
    target.innerHTML = renderEmptyChart("No products available for the current filter set.");
    return;
  }

  const width = target.clientWidth || 420;
  const height = target.clientHeight || 400;
  const margin = { top: 24, right: 28, bottom: 48, left: 52 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const xMax = Math.max(...products.map((p) => p.frequency)) * 1.1;
  const yMax = Math.max(...products.map((p) => p.impact)) * 1.1;

  const points = products.map((product) => {
    const x = margin.left + (product.frequency / xMax) * chartWidth;
    const y = margin.top + chartHeight - (product.impact / yMax) * chartHeight;
    return `
      <circle
        cx="${x}"
        cy="${y}"
        r="7"
        fill="${quadrantColor(product.quadrant)}"
        data-tooltip="${escapeHtml(`${product.name}<br>Revenue at risk: ${formatCurrency(product.revenueAtRisk)}<br>Average risk score: ${product.riskProbability.toFixed(2)}<br>${product.quadrant}`)}"
      ></circle>
    `;
  }).join("");

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Impact vs Frequency chart">
      <rect x="0" y="0" width="${width}" height="${height}" fill="#FFFFFF"></rect>
      <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      <line x1="${margin.left + chartWidth / 2}" y1="${margin.top}" x2="${margin.left + chartWidth / 2}" y2="${height - margin.bottom}" stroke="#E7E7E7" stroke-dasharray="4 4"></line>
      <line x1="${margin.left}" y1="${margin.top + chartHeight / 2}" x2="${width - margin.right}" y2="${margin.top + chartHeight / 2}" stroke="#E7E7E7" stroke-dasharray="4 4"></line>
      <text x="${width / 2}" y="${height - 12}" text-anchor="middle" fill="#6B6B6B" font-size="12">Frequency / Volume</text>
      <text x="16" y="${height / 2}" text-anchor="middle" fill="#6B6B6B" font-size="12" transform="rotate(-90 16 ${height / 2})">Impact Score</text>
      <text x="${margin.left + chartWidth * 0.75}" y="${margin.top + 18}" fill="#A3A3A3" font-size="12">Fire Fight</text>
      <text x="${margin.left + 12}" y="${margin.top + 18}" fill="#A3A3A3" font-size="12">VIP Nudge</text>
      <text x="${margin.left + chartWidth * 0.75}" y="${height - margin.bottom - 12}" fill="#A3A3A3" font-size="12">Slow Burn</text>
      <text x="${margin.left + 12}" y="${height - margin.bottom - 12}" fill="#A3A3A3" font-size="12">Noise</text>
      ${points}
    </svg>
    <div class="chart-legend">
      <span><i style="background:#DC2626"></i>Fire Fight</span>
      <span><i style="background:#F59E0B"></i>VIP Nudge</span>
      <span><i style="background:#D4A017"></i>Slow Burn</span>
      <span><i style="background:#9CA3AF"></i>Noise</span>
    </div>
  `;

  bindTooltip(target);
}

function renderRevenueChart(products) {
  const target = document.getElementById("revenue-chart");
  const sorted = [...products].sort((a, b) => b.revenueAtRisk - a.revenueAtRisk);
  if (!sorted.length) {
    target.innerHTML = renderEmptyChart("No bar chart data available.");
    return;
  }

  const width = target.clientWidth || 420;
  const height = target.clientHeight || 320;
  const margin = { top: 22, right: 20, bottom: 70, left: 58 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const maxValue = Math.max(...sorted.map((p) => p.revenueAtRisk)) * 1.1;
  const barWidth = chartWidth / sorted.length * 0.62;

  const bars = sorted.map((product, index) => {
    const x = margin.left + (index + 0.2) * (chartWidth / sorted.length);
    const barHeight = (product.revenueAtRisk / maxValue) * chartHeight;
    const y = margin.top + chartHeight - barHeight;
    const ratio = product.revenueAtRisk / maxValue;
    const fill = ratio > 0.7 ? "#DC2626" : ratio > 0.45 ? "#EE8B7D" : "#C9D7F2";
    return `
      <g>
        <rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="8" fill="${fill}" data-tooltip="${escapeHtml(`${product.name}<br>Revenue at risk: ${formatCurrency(product.revenueAtRisk)}`)}"></rect>
        <text x="${x + barWidth / 2}" y="${height - 28}" text-anchor="middle" fill="#6B6B6B" font-size="11">${truncate(product.name, 10)}</text>
      </g>
    `;
  }).join("");

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Revenue at Risk bar chart">
      <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      <text x="18" y="${margin.top + 10}" fill="#6B6B6B" font-size="12">Revenue</text>
      ${bars}
    </svg>
  `;
  bindTooltip(target);
}

function renderRatingRiskChart(products) {
  const target = document.getElementById("rating-risk-chart");
  if (!products.length) {
    target.innerHTML = renderEmptyChart("No scatter data available.");
    return;
  }

  const width = target.clientWidth || 420;
  const height = target.clientHeight || 320;
  const margin = { top: 20, right: 26, bottom: 48, left: 50 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  const dots = products.map((product) => {
    const x = margin.left + ((product.rating - 2.5) / (4.5 - 2.5)) * chartWidth;
    const y = margin.top + chartHeight - ((product.riskProbability - 0.3) / (1.0 - 0.3)) * chartHeight;
    return `
      <circle cx="${x}" cy="${y}" r="7" fill="${riskColor(product.riskProbability)}" data-tooltip="${escapeHtml(`${product.name}<br>Rating: ${product.rating.toFixed(1)}<br>Risk probability: ${product.riskProbability.toFixed(2)}`)}"></circle>
    `;
  }).join("");

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Rating vs Risk scatter plot">
      <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      <text x="${width / 2}" y="${height - 10}" text-anchor="middle" fill="#6B6B6B" font-size="12">Average Rating</text>
      <text x="18" y="${height / 2}" text-anchor="middle" fill="#6B6B6B" font-size="12" transform="rotate(-90 18 ${height / 2})">Risk Probability</text>
      ${dots}
    </svg>
    <div class="chart-legend">
      <span><i style="background:#16A34A"></i>Low</span>
      <span><i style="background:#F59E0B"></i>Medium</span>
      <span><i style="background:#DC2626"></i>High</span>
    </div>
  `;
  bindTooltip(target);
}

function renderIssuesChart(products) {
  const target = document.getElementById("issues-chart");
  if (!products.length) {
    target.innerHTML = renderEmptyChart("No issue breakdown available.");
    return;
  }

  const categories = [
    { key: "delivery", color: "#8CAEEB", label: "Delivery" },
    { key: "quality", color: "#B6C7E8", label: "Quality" },
    { key: "packaging", color: "#D7C28A", label: "Packaging" },
    { key: "support", color: "#D8D8D8", label: "Support" }
  ];

  const width = target.clientWidth || 420;
  const height = target.clientHeight || 320;
  const margin = { top: 20, right: 20, bottom: 70, left: 52 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const totals = products.map((product) => Object.values(product.issues).reduce((sum, value) => sum + value, 0));
  const maxValue = Math.max(...totals) * 1.1;
  const barWidth = chartWidth / products.length * 0.62;

  const stacks = products.map((product, index) => {
    const x = margin.left + (index + 0.2) * (chartWidth / products.length);
    let currentY = margin.top + chartHeight;
    const segments = categories.map((category) => {
      const value = product.issues[category.key];
      const segmentHeight = (value / maxValue) * chartHeight;
      currentY -= segmentHeight;
      return `<rect x="${x}" y="${currentY}" width="${barWidth}" height="${segmentHeight}" fill="${category.color}" data-tooltip="${escapeHtml(`${product.name}<br>${category.label}: ${value}`)}"></rect>`;
    }).join("");

    return `
      <g>
        ${segments}
        <text x="${x + barWidth / 2}" y="${height - 28}" text-anchor="middle" fill="#6B6B6B" font-size="11">${truncate(product.name, 10)}</text>
      </g>
    `;
  }).join("");

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Top Issues Breakdown stacked bar chart">
      <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="#DADADA"></line>
      ${stacks}
    </svg>
    <div class="chart-legend">
      ${categories.map((category) => `<span><i style="background:${category.color}"></i>${category.label}</span>`).join("")}
    </div>
  `;
  bindTooltip(target);
}

function renderRiskShareChart(products) {
  const target = document.getElementById("risk-share-chart");
  if (!products.length) {
    target.innerHTML = renderEmptyChart("No risk distribution available.");
    return;
  }

  const counts = {
    High: products.filter((item) => item.severity === "High").length,
    Medium: products.filter((item) => item.severity === "Medium").length,
    Low: products.filter((item) => item.severity === "Low").length
  };
  const total = products.length;
  const slices = [
    { key: "High", color: "#DC2626", value: counts.High },
    { key: "Medium", color: "#F59E0B", value: counts.Medium },
    { key: "Low", color: "#16A34A", value: counts.Low }
  ];

  let angle = -Math.PI / 2;
  const radius = 96;
  const innerRadius = 58;
  const centerX = 150;
  const centerY = 150;

  const paths = slices.map((slice) => {
    const portion = total ? slice.value / total : 0;
    const endAngle = angle + portion * Math.PI * 2;
    const path = donutArc(centerX, centerY, radius, innerRadius, angle, endAngle);
    const midAngle = angle + (endAngle - angle) / 2;
    const labelX = centerX + Math.cos(midAngle) * 76;
    const labelY = centerY + Math.sin(midAngle) * 76;
    const label = `${Math.round(portion * 100)}%`;
    const markup = `
      <path d="${path}" fill="${slice.color}" data-tooltip="${escapeHtml(`${slice.key} Risk<br>${slice.value} products<br>${label}`)}"></path>
      ${slice.value ? `<text x="${labelX}" y="${labelY}" text-anchor="middle" fill="#ffffff" font-size="11" font-weight="700">${label}</text>` : ""}
    `;
    angle = endAngle;
    return markup;
  }).join("");

  target.innerHTML = `
    <svg viewBox="0 0 300 300" role="img" aria-label="High Risk Share donut chart">
      ${paths}
      <circle cx="${centerX}" cy="${centerY}" r="${innerRadius - 1}" fill="#FFFFFF"></circle>
      <text x="${centerX}" y="${centerY - 4}" text-anchor="middle" fill="#1F1F1F" font-size="14" font-weight="700">${total}</text>
      <text x="${centerX}" y="${centerY + 16}" text-anchor="middle" fill="#6B6B6B" font-size="11">Products</text>
    </svg>
    <div class="chart-legend">
      <span><i style="background:#DC2626"></i>High Risk</span>
      <span><i style="background:#F59E0B"></i>Medium Risk</span>
      <span><i style="background:#16A34A"></i>Low Risk</span>
    </div>
  `;
  bindTooltip(target);
}

function generateInsights(forceLoading = false, silent = false) {
  const loading = document.getElementById("insight-loading");
  const error = document.getElementById("insight-error");
  const copy = document.getElementById("insight-copy");
  const items = state.filteredProducts;

  const render = () => {
    if (!items.length) {
      loading.classList.add("hidden");
      copy.textContent = "";
      error.classList.remove("hidden");
      state.lastInsight = "";
      state.lastLlmOutput = "";
      renderDebug(items);
      return;
    }

    const highestRevenue = [...items].sort((a, b) => b.revenueAtRisk - a.revenueAtRisk)[0];
    const highestImpact = [...items].sort((a, b) => b.impact - a.impact)[0];
    const issueTotals = aggregateIssues(items);
    const topIssue = Object.entries(issueTotals).sort((a, b) => b[1] - a[1])[0][0];
    const secondaryIssue = Object.entries(issueTotals).sort((a, b) => b[1] - a[1])[1][0];

    const summary = `${highestRevenue.name} carries the largest revenue exposure at ${formatCurrency(highestRevenue.revenueAtRisk)}, driven by elevated ${topIssue} complaints and a risk probability of ${highestRevenue.riskProbability.toFixed(2)}. ${highestImpact.name} remains the highest impact item in the current view, indicating a need for direct product and support coordination. Across the filtered set, ${toSentenceCase(topIssue)} and ${secondaryIssue} account for most issue volume, while lower-risk products remain commercially contained. Prioritize immediate remediation on Fire Fight items first, then address VIP Nudge products where issue frequency is lower but business impact remains material.`;

    state.lastInsight = summary;
    state.lastLlmPrompt = JSON.stringify({
      products: items.map((item) => ({
        name: item.name,
        revenueAtRisk: item.revenueAtRisk,
        riskProbability: item.riskProbability,
        quadrant: item.quadrant,
        severity: item.severity
      })),
      issueTotals
    }, null, 2);
    state.lastLlmOutput = summary;

    loading.classList.add("hidden");
    error.classList.add("hidden");
    copy.textContent = summary;
    renderDebug(items);
  };

  if (!forceLoading && silent) {
    render();
    return;
  }

  loading.classList.remove("hidden");
  error.classList.add("hidden");
  copy.textContent = "";

  window.setTimeout(render, forceLoading ? 520 : 260);
}

function copyInsights() {
  if (!state.lastInsight) {
    document.getElementById("insight-error").classList.remove("hidden");
    return;
  }

  const onCopied = () => {
    const button = document.getElementById("copy-insights");
    const original = button.textContent;
    button.textContent = "Copied";
    window.setTimeout(() => {
      button.textContent = original;
    }, 1200);
  };

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(state.lastInsight).then(onCopied);
    return;
  }

  const helper = document.createElement("textarea");
  helper.value = state.lastInsight;
  helper.setAttribute("readonly", "");
  helper.style.position = "absolute";
  helper.style.left = "-9999px";
  document.body.appendChild(helper);
  helper.select();
  document.execCommand("copy");
  document.body.removeChild(helper);
  onCopied();
}

function toggleDebug() {
  const panel = document.getElementById("debug-panel");
  const button = document.getElementById("debug-toggle");
  const hidden = panel.classList.toggle("hidden");
  button.textContent = hidden ? "Show Debug Panel" : "Hide Debug Panel";
}

function renderDebug(products) {
  const featureShape = { rows: products.length, columns: 12, activeThreshold: state.threshold.toFixed(2), selectedSeverity: state.severity };
  const sample = products[0] ? { product: products[0].name, predictedRisk: products[0].riskProbability, severity: products[0].severity, finalScore: products[0].finalScore } : { product: null };
  const snapshot = products.slice(0, 3).map((item) => ({ name: item.name, revenueAtRisk: item.revenueAtRisk, quadrant: item.quadrant }));

  document.getElementById("debug-feature-shape").textContent = JSON.stringify(featureShape, null, 2);
  document.getElementById("debug-risk-sample").textContent = JSON.stringify(sample, null, 2);
  document.getElementById("debug-data-snapshot").textContent = JSON.stringify(snapshot, null, 2);
  document.getElementById("debug-llm-input").textContent = state.lastLlmPrompt || "Waiting for insight generation...";
  document.getElementById("debug-llm-output").textContent = state.lastLlmOutput || "No LLM output yet.";
}

function updateTimestamp() {
  const now = new Date();
  document.getElementById("last-updated").textContent = `Last updated: ${now.toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata"
  })} IST`;
}

function bindTooltip(target) {
  target.querySelectorAll("[data-tooltip]").forEach((node) => {
    node.addEventListener("mouseenter", (event) => showTooltip(event));
    node.addEventListener("mousemove", (event) => moveTooltip(event));
    node.addEventListener("mouseleave", hideTooltip);
  });
}

function showTooltip(event) {
  tooltip.innerHTML = event.target.getAttribute("data-tooltip").replaceAll("&lt;br&gt;", "<br>");
  tooltip.classList.remove("hidden");
  moveTooltip(event);
}

function moveTooltip(event) {
  tooltip.style.transform = `translate(${event.clientX + 14}px, ${event.clientY + 14}px)`;
}

function hideTooltip() {
  tooltip.classList.add("hidden");
}

function compareRows(a, b, key, direction) {
  const map = {
    name: [a.name, b.name],
    score: [a.finalScore, b.finalScore],
    revenue: [a.revenueAtRisk, b.revenueAtRisk],
    probability: [a.riskProbability, b.riskProbability],
    negative: [a.negativePct, b.negativePct],
    quadrant: [a.quadrant, b.quadrant],
    trend: [a.trend, b.trend]
  };
  const [left, right] = map[key];
  const result = typeof left === "string" ? left.localeCompare(right) : left - right;
  return direction === "asc" ? result : -result;
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function quadrantColor(quadrant) {
  return { "Fire Fight": "#DC2626", "VIP Nudge": "#F59E0B", "Slow Burn": "#D4A017", "Noise": "#9CA3AF" }[quadrant];
}

function riskColor(probability) {
  if (probability >= 0.75) return "#DC2626";
  if (probability >= 0.55) return "#F59E0B";
  return "#16A34A";
}

function quadrantTone(quadrant) {
  return { "Fire Fight": "risk-high", "VIP Nudge": "risk-medium", "Slow Burn": "risk-medium", "Noise": "risk-low" }[quadrant];
}

function renderTrend(trend) {
  if (trend === "Rising") return `<span class="risk-high">Up</span>`;
  if (trend === "Falling") return `<span class="risk-low">Down</span>`;
  return `<span class="risk-medium">Flat</span>`;
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}...` : value;
}

function aggregateIssues(items) {
  return items.reduce((totals, item) => {
    Object.entries(item.issues).forEach(([key, value]) => {
      totals[key] = (totals[key] || 0) + value;
    });
    return totals;
  }, {});
}

function toSentenceCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderEmptyChart(message) {
  return `<div class="empty-state">${message}</div>`;
}

function escapeHtml(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function donutArc(cx, cy, outerRadius, innerRadius, startAngle, endAngle) {
  if (endAngle - startAngle <= 0) return "";
  const outerStart = polarToCartesian(cx, cy, outerRadius, endAngle);
  const outerEnd = polarToCartesian(cx, cy, outerRadius, startAngle);
  const innerStart = polarToCartesian(cx, cy, innerRadius, startAngle);
  const innerEnd = polarToCartesian(cx, cy, innerRadius, endAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
  return [`M ${outerStart.x} ${outerStart.y}`, `A ${outerRadius} ${outerRadius} 0 ${largeArc} 0 ${outerEnd.x} ${outerEnd.y}`, `L ${innerStart.x} ${innerStart.y}`, `A ${innerRadius} ${innerRadius} 0 ${largeArc} 1 ${innerEnd.x} ${innerEnd.y}`, "Z"].join(" ");
}

function polarToCartesian(cx, cy, radius, angle) {
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
}
