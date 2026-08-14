const STATUS_LABELS = {
  "": "Not contacted",
  contacted: "Contacted",
  declined: "Declined",
  accepted: "Accepted",
};

const NUMERIC_COLUMNS = ["score", "rating", "review_count"];

const state = {
  file: null,
  rows: [],
  sortColumn: "score",
  sortAscending: false,
};

const elements = {
  form: document.getElementById("search-form"),
  query: document.getElementById("query"),
  limit: document.getElementById("limit"),
  searchButton: document.getElementById("search-button"),
  searchStatus: document.getElementById("search-status"),
  fileSelect: document.getElementById("file-select"),
  onlyNoWebsite: document.getElementById("only-no-website"),
  minRating: document.getElementById("min-rating"),
  minReviews: document.getElementById("min-reviews"),
  exportButton: document.getElementById("export-button"),
  resultCount: document.getElementById("result-count"),
  body: document.getElementById("leads-body"),
  empty: document.getElementById("empty-message"),
  usage: document.getElementById("usage"),
  overlay: document.getElementById("overlay"),
};

function setMessage(text, isError) {
  elements.searchStatus.textContent = text || "";
  elements.searchStatus.classList.toggle("error", Boolean(isError));
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

async function loadUsage() {
  try {
    const data = await requestJson("/api/usage");
    const source = data.has_google_key ? "Google Places" : "OpenStreetMap (no key)";
    elements.usage.innerHTML =
      "Source: <strong>" + source + "</strong><br>" +
      "Searches this month: <strong>" + data.used + "</strong> of " + data.limit;
  } catch (error) {
    elements.usage.textContent = "";
  }
}

async function loadFiles(preferred) {
  const data = await requestJson("/api/files");
  elements.fileSelect.innerHTML = "";

  if (!data.files.length) {
    const option = document.createElement("option");
    option.textContent = "no saved searches";
    elements.fileSelect.append(option);
    elements.fileSelect.disabled = true;
    return;
  }

  elements.fileSelect.disabled = false;
  data.files.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name.replace(/^leads_/, "").replace(/\.csv$/, "");
    elements.fileSelect.append(option);
  });

  const chosen = preferred && data.files.includes(preferred) ? preferred : data.files[0];
  elements.fileSelect.value = chosen;
  await loadLeads(chosen);
}

async function loadLeads(file) {
  const data = await requestJson("/api/leads?file=" + encodeURIComponent(file));
  state.file = data.file;
  state.rows = data.rows;
  render();
}

function toNumber(value) {
  const parsed = parseFloat(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function visibleRows() {
  const minRating = toNumber(elements.minRating.value);
  const minReviews = toNumber(elements.minReviews.value);

  let rows = state.rows.filter((row) => {
    if (elements.onlyNoWebsite.checked && (row.website || "").trim()) {
      return false;
    }
    if (minRating !== null && (toNumber(row.rating) === null || toNumber(row.rating) < minRating)) {
      return false;
    }
    if (minReviews !== null && (toNumber(row.review_count) === null || toNumber(row.review_count) < minReviews)) {
      return false;
    }
    return true;
  });

  const column = state.sortColumn;
  const direction = state.sortAscending ? 1 : -1;

  rows.sort((left, right) => {
    if (NUMERIC_COLUMNS.includes(column)) {
      const a = toNumber(left[column]);
      const b = toNumber(right[column]);
      if (a === null && b === null) return 0;
      if (a === null) return 1;
      if (b === null) return -1;
      return (a - b) * direction;
    }
    return String(left[column] || "").localeCompare(String(right[column] || "")) * direction;
  });

  return rows;
}

function linkElement(href, label) {
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  anchor.textContent = label;
  return anchor;
}

function statusSelect(row) {
  const select = document.createElement("select");
  Object.entries(STATUS_LABELS).forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.append(option);
  });
  select.value = row.status || "";

  select.addEventListener("change", async () => {
    try {
      await requestJson("/api/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file: state.file, place_id: row.place_id, status: select.value }),
      });
      row.status = select.value;
      select.classList.add("saved");
      setTimeout(() => select.classList.remove("saved"), 1200);
    } catch (error) {
      setMessage(error.message, true);
      select.value = row.status || "";
    }
  });

  return select;
}

function buildRow(row) {
  const tr = document.createElement("tr");

  const score = document.createElement("td");
  score.className = "score";
  score.textContent = row.score;
  tr.append(score);

  const name = document.createElement("td");
  name.className = "name";
  name.textContent = row.name;
  tr.append(name);

  const address = document.createElement("td");
  address.className = "address";
  address.textContent = row.address || "—";
  tr.append(address);

  const rating = document.createElement("td");
  rating.className = "numeric";
  rating.textContent = row.rating || "—";
  tr.append(rating);

  const reviews = document.createElement("td");
  reviews.className = "numeric";
  reviews.textContent = row.review_count || "—";
  tr.append(reviews);

  const website = document.createElement("td");
  const badge = document.createElement("span");
  const hasWebsite = Boolean((row.website || "").trim());
  badge.className = "badge " + (hasWebsite ? "has-site" : "no-site");
  badge.textContent = hasWebsite ? "has site" : "no site";
  website.append(badge);
  tr.append(website);

  const phone = document.createElement("td");
  phone.textContent = row.phone || "—";
  tr.append(phone);

  const links = document.createElement("td");
  links.className = "links";
  if (row.google_maps_link) {
    links.append(linkElement(row.google_maps_link, "maps"));
  }
  if (hasWebsite) {
    links.append(linkElement(row.website, "site"));
  }
  if (row.contact_search) {
    links.append(linkElement(row.contact_search, "contact"));
  }
  tr.append(links);

  const status = document.createElement("td");
  status.append(statusSelect(row));
  tr.append(status);

  const brief = document.createElement("td");
  const briefButton = document.createElement("button");
  briefButton.type = "button";
  briefButton.className = "secondary";
  briefButton.textContent = "Create brief";
  briefButton.disabled = true;
  briefButton.title = "Available from phase 5";
  brief.append(briefButton);
  tr.append(brief);

  return tr;
}

function render() {
  const rows = visibleRows();
  elements.body.innerHTML = "";
  rows.forEach((row) => elements.body.append(buildRow(row)));

  const withoutWebsite = rows.filter((row) => !(row.website || "").trim()).length;
  elements.resultCount.textContent = state.file
    ? rows.length + " of " + state.rows.length + " shown · " + withoutWebsite + " without a website"
    : "";

  elements.empty.hidden = rows.length > 0;
  if (!rows.length) {
    elements.empty.textContent = state.rows.length
      ? "No business matches these filters."
      : "No search loaded yet.";
  }

  document.querySelectorAll("th.sortable").forEach((header) => {
    header.classList.remove("sorted-asc", "sorted-desc");
    if (header.dataset.sort === state.sortColumn) {
      header.classList.add(state.sortAscending ? "sorted-asc" : "sorted-desc");
    }
  });
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = elements.query.value.trim();
  if (!query) {
    setMessage("Enter a search first.", true);
    return;
  }

  elements.overlay.hidden = false;
  elements.searchButton.disabled = true;
  setMessage("");

  try {
    const body = { query };
    if (elements.limit.value) {
      body.limit = parseInt(elements.limit.value, 10);
    }
    const data = await requestJson("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    let message =
      "Found " + data.found + " businesses, " + data.without_website + " without a website. " +
      "Source: " + data.source + ".";
    if (data.merged_with) {
      message += " Merged with the earlier file, your statuses were kept.";
    }
    setMessage(message);

    await loadFiles(data.file);
    await loadUsage();
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    elements.overlay.hidden = true;
    elements.searchButton.disabled = false;
  }
});

elements.fileSelect.addEventListener("change", async () => {
  try {
    await loadLeads(elements.fileSelect.value);
    setMessage("");
  } catch (error) {
    setMessage(error.message, true);
  }
});

[elements.onlyNoWebsite, elements.minRating, elements.minReviews].forEach((control) => {
  control.addEventListener("input", render);
});

document.querySelectorAll("th.sortable").forEach((header) => {
  header.addEventListener("click", () => {
    const column = header.dataset.sort;
    if (state.sortColumn === column) {
      state.sortAscending = !state.sortAscending;
    } else {
      state.sortColumn = column;
      state.sortAscending = !NUMERIC_COLUMNS.includes(column);
    }
    render();
  });
});

elements.exportButton.addEventListener("click", () => {
  if (state.file) {
    window.location.href = "/api/export?file=" + encodeURIComponent(state.file);
  }
});

loadUsage();
loadFiles().catch((error) => setMessage(error.message, true));
