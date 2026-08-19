const state = { q: "", sector: "", status: "", page: 1, page_size: 10 };
let sectorChart, budgetChart;

const fmtKES = (n) => "KES " + Number(n).toLocaleString("en-KE", { maximumFractionDigits: 0 });

async function loadFilterOptions() {
  const res = await fetch("/api/sectors");
  const data = await res.json();
  const sectorSel = document.getElementById("sector-filter");
  const statusSel = document.getElementById("status-filter");
  data.sectors.forEach(s => sectorSel.insertAdjacentHTML("beforeend", `<option value="${s}">${s}</option>`));
  data.statuses.forEach(s => statusSel.insertAdjacentHTML("beforeend", `<option value="${s}">${s}</option>`));
}

async function loadStats() {
  const res = await fetch("/api/stats");
  const data = await res.json();

  document.getElementById("kpi-total").textContent = data.total_projects;
  document.getElementById("kpi-budget").textContent = fmtKES(data.total_budget);
  document.getElementById("kpi-completed").textContent = data.by_status["Completed"] || 0;
  document.getElementById("kpi-ongoing").textContent = data.by_status["Ongoing"] || 0;

  const sectorLabels = Object.keys(data.by_sector);
  const sectorCounts = Object.values(data.by_sector);
  const budgetValues = sectorLabels.map(s => data.budget_by_sector[s] || 0);

  const palette = ["#0E4F3C", "#B8862B", "#1B5E8C", "#8A6A1F", "#6B4226"];

  if (sectorChart) sectorChart.destroy();
  sectorChart = new Chart(document.getElementById("sectorChart"), {
    type: "doughnut",
    data: { labels: sectorLabels, datasets: [{ data: sectorCounts, backgroundColor: palette, borderWidth: 0 }] },
    options: { plugins: { legend: { position: "bottom", labels: { font: { family: "Inter" }, boxWidth: 10 } } } }
  });

  if (budgetChart) budgetChart.destroy();
  budgetChart = new Chart(document.getElementById("budgetChart"), {
    type: "bar",
    data: { labels: sectorLabels, datasets: [{ data: budgetValues, backgroundColor: "#0E4F3C", borderRadius: 3 }] },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { callback: v => (v / 1e6) + "M" } } }
    }
  });
}

function statusPillClass(status) {
  return { Planned: "status-planned", Ongoing: "status-ongoing", Completed: "status-completed" }[status] || "";
}

async function loadProjects() {
  const params = new URLSearchParams({
    page: state.page, page_size: state.page_size,
    ...(state.q ? { q: state.q } : {}),
    ...(state.sector ? { sector: state.sector } : {}),
    ...(state.status ? { status: state.status } : {}),
  });
  const res = await fetch(`/api/projects?${params.toString()}`);
  const data = await res.json();

  const tbody = document.getElementById("projects-tbody");
  tbody.innerHTML = data.results.map(p => `
    <tr>
      <td class="font-mono text-xs opacity-60">${p.project_id}</td>
      <td class="font-medium">${p.project_name}</td>
      <td>${p.sector}</td>
      <td>${p.ward || "—"}</td>
      <td>${fmtKES(p.budget)}</td>
      <td><span class="status-pill ${statusPillClass(p.status)}">${p.status}</span></td>
    </tr>
  `).join("") || `<tr><td colspan="6" class="text-center py-8 opacity-50">No projects match these filters.</td></tr>`;

  document.getElementById("result-count").textContent = `${data.total} project${data.total === 1 ? "" : "s"} found`;
  const totalPages = Math.max(1, Math.ceil(data.total / state.page_size));
  document.getElementById("page-indicator").textContent = `Page ${state.page} of ${totalPages}`;
  document.getElementById("prev-page").disabled = state.page <= 1;
  document.getElementById("next-page").disabled = state.page >= totalPages;
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

document.getElementById("search-input").addEventListener("input", debounce((e) => {
  state.q = e.target.value; state.page = 1; loadProjects();
}, 300));

document.getElementById("sector-filter").addEventListener("change", (e) => {
  state.sector = e.target.value; state.page = 1; loadProjects();
});
document.getElementById("status-filter").addEventListener("change", (e) => {
  state.status = e.target.value; state.page = 1; loadProjects();
});
document.getElementById("clear-filters").addEventListener("click", () => {
  state.q = ""; state.sector = ""; state.status = ""; state.page = 1;
  document.getElementById("search-input").value = "";
  document.getElementById("sector-filter").value = "";
  document.getElementById("status-filter").value = "";
  loadProjects();
});
document.getElementById("prev-page").addEventListener("click", () => { state.page--; loadProjects(); });
document.getElementById("next-page").addEventListener("click", () => { state.page++; loadProjects(); });

(async function init() {
  await loadFilterOptions();
  await loadStats();
  await loadProjects();
})();
