const $ = (sel, root = document) => root.querySelector(sel);

function pct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `${(100 * Number(value)).toFixed(digits)}%`;
}

function num(value) {
  if (value == null || value === "") return "—";
  return Number(value).toLocaleString("en-US");
}

function correction(stock, key, weight) {
  const block = stock && stock.correction && stock.correction[key];
  return block ? block[weight] : null;
}

async function loadSite() {
  const response = await fetch("./data/site.json");
  if (!response.ok) {
    throw new Error("site.json is missing. Run: uv run oh publish --metro nyc");
  }
  return response.json();
}

function showError(err) {
  const host = $(".lede") || $(".content") || document.body;
  const p = document.createElement("p");
  p.className = "caveat";
  p.textContent = err.message || String(err);
  host.prepend(p);
}

function setText(id, text) {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
}

function renderHeadlines(data) {
  const stock = data.stock || {};
  const all = stock.private_all_entity_only || {};
  const info = stock.sfr_condo_entity_only || {};
  const unit = correction(stock, "private_all_entity_only", "unit") || {};
  const parcel = correction(stock, "private_all_entity_only", "parcel") || {};
  const infoUnit = correction(stock, "sfr_condo_entity_only", "unit") || {};
  const flow = data.flow || {};
  const priv = flow.private_residential || {};
  const opacity = (data.opacity && data.opacity.entity_owned) || {};
  const tiers = opacity.by_tier || {};
  const o1 = (tiers.O1 && tiers.O1.unit_share) || null;
  const o3 = (tiers.O3 && tiers.O3.unit_share) || null;
  const sfr = (data.opacity && data.opacity.sfr_condo) || {};
  const sfrO1 = sfr.by_tier && sfr.by_tier.O1 ? sfr.by_tier.O1.unit_share : null;

  setText(
    "lede",
    "Entity-owned here means a recorded owner that is an LLC, corporation, or partnership. Trusts are a separate series. Public and nonprofit owners are out of the private denominator.",
  );
  setText("stat-unit", pct(unit.corrected ?? all.unit_share));
  setText(
    "stat-unit-sub",
    unit.corrected == null
      ? `Raw ${pct(all.unit_share)} of ${num(all.units)} private residential units.`
      : `Corrected from raw ${pct(unit.observed)}. 95% interval ${pct(unit.corrected_lo)}–${pct(unit.corrected_hi)} (test gold n=${num(unit.n_labeled)}).`,
  );
  setText("stat-parcel", pct(parcel.corrected ?? all.parcel_share));
  setText(
    "stat-parcel-sub",
    parcel.corrected == null
      ? `Raw ${pct(all.parcel_share)} of ${num(all.parcels)} private lots.`
      : `Corrected from raw ${pct(parcel.observed)}. Interval ${pct(parcel.corrected_lo)}–${pct(parcel.corrected_hi)}.`,
  );
  setText("stat-sfr", pct(infoUnit.corrected ?? info.unit_share));
  setText(
    "stat-sfr-sub",
    `1–4 family + condo billing lots. Raw ${pct(info.unit_share)} of units (${pct(info.parcel_share)} of lots).`,
  );
  setText("stat-flow", pct(priv.sale_share));
  setText(
    "stat-flow-sub",
    `${num(priv.entity_sales)} of ${num(priv.sales)} arm’s-length sales, 2003–2025. Unit-weighted ${pct(priv.unit_share)}.`,
  );
  setText("stat-o1", pct(o1));
  setText(
    "stat-o1-sub",
    `Named person on that entity’s HPD or DOS record. Residual no-person share (O3) is ${pct(o3)}. Among 1–4 family + condo entity units, O1 is ${pct(sfrO1)}.`,
  );
}

function boroughFill(share) {
  if (share == null) return "var(--accent-soft)";
  const t = Math.min(1, Math.max(0, share / 0.55));
  const r = Math.round(154 + (255 - 154) * (1 - t));
  const g = Math.round(52 + (237 - 52) * (1 - t));
  const b = Math.round(18 + (213 - 18) * (1 - t));
  return `rgb(${r}, ${g}, ${b})`;
}

function renderBoroughMap(boroughs, selected, onPick) {
  const host = $("#borough-map");
  if (!host) return;
  host.innerHTML = "";
  const order = ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"];
  for (const name of order) {
    const row = boroughs.find((item) => item.borough === name) || { borough: name };
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "boro";
    btn.dataset.borough = name;
    btn.style.background = boroughFill(row.entity_unit_share);
    btn.setAttribute("aria-pressed", selected === name ? "true" : "false");
    btn.innerHTML = `<div class="name">${name}</div><div class="share">${pct(row.entity_unit_share)}</div><div class="note">${num(row.units)} units</div>`;
    btn.addEventListener("click", () => onPick(selected === name ? "" : name));
    host.appendChild(btn);
  }
}

function compareRows(a, b, key, dir) {
  const av = a[key];
  const bv = b[key];
  const an = av == null;
  const bn = bv == null;
  if (an && bn) return 0;
  if (an) return 1;
  if (bn) return -1;
  if (typeof av === "number" && typeof bv === "number") {
    return dir === "asc" ? av - bv : bv - av;
  }
  return dir === "asc"
    ? String(av).localeCompare(String(bv))
    : String(bv).localeCompare(String(av));
}

function renderNeighborhoods(data) {
  const rows = data.neighborhoods || [];
  const boroughs = data.boroughs || [];
  const state = { q: "", borough: "", sort: "entity_unit_share", dir: "desc", showSmall: false };

  const search = $("#nta-search");
  const boro = $("#nta-borough");
  const small = $("#nta-small");
  const tbody = $("#nta-body");

  function apply() {
    renderBoroughMap(boroughs, state.borough, (name) => {
      state.borough = name;
      if (boro) boro.value = name;
      apply();
    });
    let view = rows.filter((row) => {
      if (!state.showSmall && row.suppressed) return false;
      if (state.borough && row.borough !== state.borough) return false;
      if (state.q) {
        const hay = `${row.nta} ${row.nta_name} ${row.borough}`.toLowerCase();
        if (!hay.includes(state.q)) return false;
      }
      return true;
    });
    view = view.slice().sort((a, b) => compareRows(a, b, state.sort, state.dir));
    tbody.innerHTML = "";
    for (const row of view) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.nta_name || row.nta}</td>
        <td>${row.nta}</td>
        <td>${row.borough || "—"}</td>
        <td class="num">${num(row.units)}</td>
        <td class="num">${pct(row.entity_unit_share)}</td>
        <td class="num">${pct(row.entity_parcel_share)}</td>
        <td class="num">${pct(row.sfr_condo_entity_unit_share)}</td>
        <td>${row.suppressed ? "suppressed" : ""}</td>`;
      tbody.appendChild(tr);
    }
    setText("nta-count", `${view.length} neighborhoods`);
  }

  if (search) {
    search.addEventListener("input", () => {
      state.q = search.value.trim().toLowerCase();
      apply();
    });
  }
  if (boro) {
    const names = [...new Set(rows.map((row) => row.borough).filter(Boolean))].sort();
    for (const name of names) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      boro.appendChild(opt);
    }
    boro.addEventListener("change", () => {
      state.borough = boro.value;
      apply();
    });
  }
  if (small) {
    small.addEventListener("change", () => {
      state.showSmall = small.checked;
      apply();
    });
  }
  for (const th of document.querySelectorAll("th[data-sort]")) {
    th.addEventListener("click", () => {
      const key = th.getAttribute("data-sort");
      if (state.sort === key) {
        state.dir = state.dir === "desc" ? "asc" : "desc";
      } else {
        state.sort = key;
        state.dir = key.includes("share") || key === "units" ? "desc" : "asc";
      }
      for (const other of document.querySelectorAll("th[data-sort]")) {
        other.removeAttribute("aria-sort");
      }
      th.setAttribute("aria-sort", state.dir === "asc" ? "ascending" : "descending");
      apply();
    });
  }
  apply();
}

function lineChart(svg, series) {
  const years = series.map((row) => Number(row.year));
  const w = 760;
  const h = 280;
  const pad = { l: 48, r: 16, t: 16, b: 32 };
  const xmin = Math.min(...years);
  const xmax = Math.max(...years);
  const ymax = 0.8;
  const x = (year) => pad.l + ((year - xmin) / (xmax - xmin)) * (w - pad.l - pad.r);
  const y = (share) => pad.t + (1 - Number(share) / ymax) * (h - pad.t - pad.b);
  const path = (key) =>
    series
      .map((row, i) => `${i ? "L" : "M"}${x(row.year).toFixed(1)},${y(row[key]).toFixed(1)}`)
      .join(" ");
  const ticks = [];
  for (let year = xmin; year <= xmax; year += 2) {
    ticks.push(
      `<text x="${x(year).toFixed(1)}" y="${h - 8}" text-anchor="middle" font-size="11" fill="#57534e">${year}</text>`,
    );
  }
  for (const share of [0, 0.2, 0.4, 0.6, 0.8]) {
    ticks.push(
      `<text x="8" y="${y(share) + 4}" font-size="11" fill="#57534e">${pct(share, 0)}</text>`,
      `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y(share)}" y2="${y(share)}" stroke="#e7e0d4"/>`,
    );
  }
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = `${ticks.join("")}
    <path d="${path("sale_share")}" fill="none" stroke="#1c1917" stroke-width="2"/>
    <path d="${path("unit_share")}" fill="none" stroke="#9a3412" stroke-width="2"/>`;
}

function renderTrends(data) {
  const years = data.flow_by_year || [];
  const sfr = data.flow_sfr_condo || [];
  const hist = data.history || [];
  const flow = data.flow || {};
  const priv = flow.private_residential || {};
  const info = flow.sfr_condo || {};
  setText(
    "trend-lede",
    `Arm’s-length residential sales with an entity buyer, recorded years 2003–2025. Citywide sale share ${pct(priv.sale_share)}; unit-weighted ${pct(priv.unit_share)}. 1–4 family + condo sale share ${pct(info.sale_share)}.`,
  );
  const allSvg = $("#chart-all");
  const sfrSvg = $("#chart-sfr");
  if (allSvg && years.length) lineChart(allSvg, years);
  if (sfrSvg && sfr.length) lineChart(sfrSvg, sfr);
  const tbody = $("#trend-body");
  if (tbody) {
    tbody.innerHTML = years
      .map((row) => {
        const histRow = hist.find((item) => Number(item.year) === Number(row.year)) || {};
        return `<tr>
          <td>${row.year}</td>
          <td class="num">${num(row.sales)}</td>
          <td class="num">${pct(row.sale_share)}</td>
          <td class="num">${pct(row.unit_share)}</td>
          <td class="num">${histRow.unit_share != null ? pct(histRow.unit_share) : "—"}</td>
        </tr>`;
      })
      .join("");
  }
}

function typeLabel(code) {
  return (
    {
      sfr_1_4: "1–4 family",
      condo_unit: "Condo (billing lot)",
      small_mf: "Small multifamily (5–19)",
      large_mf: "Large multifamily (20+)",
      mixed_use_res: "Mixed-use residential",
      coop_building: "Co-op building",
      other_res: "Other residential",
    }[code] || code
  );
}

function entityShareForType(rows, buildingType) {
  const subset = rows.filter((row) => row.building_type === buildingType);
  if (!subset.length) return null;
  const units = Number(subset[0].units);
  const entity = subset
    .filter((row) => ["llc", "corp", "partnership"].includes(row.owner_class))
    .reduce((sum, row) => sum + Number(row.class_units), 0);
  return units ? entity / units : null;
}

function renderBuildings(data) {
  const types = data.stock_by_type || [];
  const host = $("#type-bars");
  const codes = [...new Set(types.map((row) => row.building_type))];
  if (host) {
    host.innerHTML = codes
      .map((code) => {
        const share = entityShareForType(types, code);
        const width = share == null ? 0 : Math.min(100, 100 * share);
        return `<div class="bar-row">
          <div>${typeLabel(code)}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${width.toFixed(1)}%"></div></div>
          <div class="num">${pct(share)}</div>
        </div>`;
      })
      .join("");
  }
  const tbody = $("#opacity-body");
  const opacity = data.opacity_by_type || [];
  if (tbody) {
    const grouped = {};
    for (const row of opacity) {
      grouped[row.building_type] = grouped[row.building_type] || {};
      grouped[row.building_type][row.opacity_tier] = row;
    }
    tbody.innerHTML = Object.keys(grouped)
      .sort()
      .map((code) => {
        const tiers = grouped[code];
        return `<tr>
          <td>${typeLabel(code)}</td>
          <td class="num">${pct(tiers.O1 && tiers.O1.unit_share)}</td>
          <td class="num">${pct(tiers.O2 && tiers.O2.unit_share)}</td>
          <td class="num">${pct(tiers.O3 && tiers.O3.unit_share)}</td>
          <td class="num">${pct(tiers.O4 && tiers.O4.unit_share)}</td>
        </tr>`;
      })
      .join("");
  }
}

function renderFreshness(data) {
  const fresh = data.freshness || {};
  const stock = fresh.stock || {};
  const reused = data.reused || fresh.reused || {};
  setText("fresh-generated", fresh.generated_at || "—");
  setText("fresh-rules", stock.rules_version || "—");
  setText("fresh-pluto", (stock.source_versions && stock.source_versions.pluto) || "—");
  setText("fresh-stock-time", stock.finished_at || "—");
  const reusedNames = Object.keys(reused);
  setText(
    "fresh-reused",
    reusedNames.length
      ? `Reused from last full run: ${reusedNames.join(", ")}`
      : "This publish used derived flow and opacity files (full local run).",
  );
  setText(
    "fresh-flow",
    fresh.flow_present
      ? "Flow / history aggregates are present."
      : "Flow aggregates are missing. GitHub-hosted refresh does not pull ACRIS (ADR 0009).",
  );
  setText(
    "fresh-opacity",
    fresh.opacity_present
      ? "Opacity aggregates are present."
      : "Opacity aggregates are missing. GitHub-hosted refresh does not pull NY DOS.",
  );
}

document.addEventListener("DOMContentLoaded", async () => {
  const page = document.body.dataset.page;
  if (!page) return;
  try {
    const data = await loadSite();
    if (page === "headlines") renderHeadlines(data);
    if (page === "neighborhoods") renderNeighborhoods(data);
    if (page === "trends") renderTrends(data);
    if (page === "buildings") renderBuildings(data);
    if (page === "freshness") renderFreshness(data);
  } catch (err) {
    showError(err);
  }
});
