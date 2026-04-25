import re, json
from pathlib import Path
from datetime import datetime

INPUT_JSON = Path("parsed_output.json")
OUTPUT_HTML = Path("/home/ivps/webserver/kk/discovery_portal.html")


def clean_version(version):
    if not version:
        return None
    match = re.search(r'(\d+\.\d+\.\d+P\d+)', version)
    return match.group(1) if match else version


def generate_files(data):

    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Storage Discovery</title>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

<style>

/* ---------- BASE ---------- */
body {
    background: #ffffff;
    margin: 0;
    padding: 0;
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
}

/* ---------- LAYOUT ---------- */
.container-fluid {
    width: 75%;
    margin: 0 auto;
}

/* ---------- HEADER TITLE ---------- */
h3 {
    margin-top: 10px;
}

/* ---------- TOP BAR ---------- */
.top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;

    position: sticky;
    top: 0;
    z-index: 1000;

    background: white;
    padding: 16px 0;          /* space from top */
    margin-top: 10px;         /* gap from browser bar */
    margin-bottom: 10px;

}

/* ---------- TITLE ---------- */
.page-title {
    font-size: 32px;           /* bigger */
    font-weight: 700;
    color: #5c6bc0;            /* same as block header */
    letter-spacing: 0.4px;
}

/* ---------- SEARCH BOX ---------- */
.search-box {
    display: flex;
    align-items: center;

    background: transparent;
    border-radius: 30px;
    padding: 5px 12px;

    width: 25%;
    min-width: 260px;
    max-width: 400px;

    border: 1px solid #ccc;
    transition: all 0.2s ease;
}

.search-box:focus-within {
    border-color: #3f51b5;
}

.search-box input {
    border: none !important;
    outline: none !important;
    box-shadow: none !important;

    background: transparent;
    width: 100%;
    font-size: 14px;
    margin-left: 6px;
}

.search-icon {
    font-size: 14px;
    color: #777;
}

/* ---------- CLEAR BUTTON ---------- */
.clear-btn {
    cursor: pointer;
    font-size: 14px;
    color: #999;
    margin-left: 8px;
    display: none;
}

.clear-btn:hover {
    color: #333;
}

/* ---------- BLOCK HEADER ---------- */
.block-header {
    background: #5c6bc0;
    color: white;
    text-align: center;
    font-weight: 600;
    padding: 8px;
    margin-top: 30px;
    border-radius: 4px;
}

/* ---------- TABLE TITLES ---------- */
.table-title {
    margin-top: 18px;
    margin-bottom: 6px;
    font-weight: 600;
    color: #5c6bc0;
    letter-spacing: 0.3px;
    text-transform: uppercase; 
}

/* ---------- TABLE ---------- */
.table {
    margin-bottom: 20px;
}

/* FORCE header color */
.table thead th {
    background-color: #dee4f7 !important;
}

/* FORCE hover color */
.table tbody tr:hover td {
    background-color: #eef1fb !important;
}

/* ---------- FOOTER ---------- */
p.text-center {
    margin-top: 30px;
    font-size: 12px;
    color: #777;
}

.yes-text {
    color: #2e7d32;   /* green */
    font-weight: 600;
}

.no-text {
    color: #c62828;   /* red */
    font-weight: 600;
}

.data-table td {
    font-size: 13px;
}

.data-table th {
    font-size: 14px; /* keep header slightly larger */
}

</style>

</head>

<body>

<div class="container-fluid">

<div class="top-bar sticky-search">
    
    <div class="page-title">
        Storage Discovery
    </div>

    <div class="search-box">
        <span class="search-icon">🔍</span>
        <input id="search" type="text" placeholder="Search for anything...">
        <span id="clearBtn" class="clear-btn">✕</span>
    </div>

</div>

<div id="app"></div>

<p class="text-center text-muted mt-4" style="font-size:12px;">
Generated at __TIME__
</p>

</div>

<script>
const DATA = __DATA__;
</script>

<script>

// =====================
// STATE
// =====================

const state = {
    data: DATA,
    search: ""
};


// =====================
// HELPERS
// =====================

function badge(val) {
    if (val === "yes") return `<span class="yes-text">YES</span>`;
    if (val === "no") return `<span class="no-text">NO</span>`;
    return val ?? "";
}

function createTable(title, headers, rows) {
    if (!rows.length) return "";

    const colCount = headers.length;
    const width = (100 / colCount).toFixed(2) + "%";

    let html = `
        <div class="table-title">${title}</div>
        <div class="table-responsive">
        <table class="table table-bordered table-sm table-hover align-middle data-table">
        <thead class="table-light">
        <tr>
    `;

    headers.forEach(h => {
        html += `<th style="width:${width}">${h}</th>`;
    });

    html += "</tr></thead><tbody>";

    rows.forEach(r => {
        html += "<tr>";
        r.forEach(c => html += `<td>${c ?? ""}</td>`);
        html += "</tr>";
    });

    html += "</tbody></table></div>";

    return html;
}

function match(obj) {
    return JSON.stringify(obj).toLowerCase().includes(state.search);
}

function textMatch(text) {
    return (text || "").toLowerCase().includes(state.search);
}

function header(name) {
    return `<div class="block-header">${name}</div>`;
}

function createTableSummary(headers, rows) {
    if (!rows.length) return "";

    let html = `
        <div class="table-responsive">
        <table class="table table-bordered table-sm table-hover align-middle data-table">
        <thead class="table-light"><tr>
    `;

    headers.forEach(h => html += `<th>${h}</th>`);
    html += "</tr></thead><tbody>";

    rows.forEach(r => {
        html += "<tr>";
        r.forEach(c => html += `<td>${c ?? ""}</td>`);
        html += "</tr>";
    });

    html += "</tbody></table></div>";

    return html;
}


// =====================
// SUMMARY
// =====================

function Summary() {

    const rows = state.data.summary
        .filter(r => state.search === "" || match(r))
        .map(s => [
            s.array_name,
            s.storage_type,
            s.model,
            s.ip || "-",
            s.serial_number,
            s.region,
            s.firmware
        ]);

    if (!rows.length) return "";

    return createTableSummary(
        ["Array Name","Type","Model","IP","Serial","Region","Firmware"],
        rows
    );
}


// =====================
// UNITY
// =====================

function Unity() {

    return state.data.unity.map(u => {

        const arrayHit = textMatch(u.array_name);

        const capacityHit = textMatch("capacity");
        const nasHit = textMatch("nas") || textMatch("nas servers");
        const replHit = textMatch("replication");

        const capacity = u.capacity.filter(r =>
            arrayHit || capacityHit || match(r)
        );

        const nas = u.nas.filter(r =>
            arrayHit || nasHit || match(r)
        );

        const repl = u.replication.filter(r =>
            arrayHit || replHit || match(r)
        );

        if (!capacity.length && !nas.length && !repl.length) return "";

        return `
        ${header(u.array_name)}

        ${createTable(
            "Capacity",
            ["Pool Name","Total TB","Used %","Remaining TB"],
            capacity.map(c => [
                (c.name || "").toUpperCase(),
                c.total_tb,
                c.used_percent,
                c.remaining_tb
            ])
        )}

        ${createTable(
            "NAS Servers",
            ["Name","NFSv3","NFSv4","CIFS","Multiprotocol"],
            nas.map(n => [
                n.name,
                badge(n.nfs3),
                badge(n.nfs4),
                badge(n.cifs),
                badge(n.multiprotocol)
            ])
        )}

        ${createTable(
            "Replication",
            ["Remote Array","Model","Connection"],
            repl.map(r => [
                (r.name || "").toUpperCase(),
                r.model,
                r.connection
            ])
        )}
        `;
    }).join("");
}


// =====================
// NETAPP
// =====================

function NetApp() {

    return state.data.netapp.map(n => {

        const arrayHit = textMatch(n.array_name);

        const aggrHit = textMatch("aggregate");
        const vsHit = textMatch("vserver") || textMatch("v server");

        const aggr = n.aggregates.filter(r =>
            arrayHit || aggrHit || match(r)
        );

        const vs = n.vservers.filter(r =>
            arrayHit || vsHit || match(r)
        );

        if (!aggr.length && !vs.length) return "";

        return `
        ${header(n.array_name)}

        ${createTable(
            "Aggregates",
            ["Name","Size","Available","Used %","State"],
            aggr.map(a => [
                a.name,
                a.size,
                a.available,
                a.used_percent,
                a.state
            ])
        )}

        ${createTable(
            "VServers",
            ["Name","Type","State","Root Volume","Aggregate"],
            vs.map(v => [
                v.name,
                v.type,
                v.operational_state,
                v.root_volume,
                v.aggregate
            ])
        )}
        `;
    }).join("");
}


// =====================
// RENDER
// =====================

function render() {

    const html =
        Summary() +
        Unity() +
        NetApp();

    document.getElementById("app").innerHTML =
        html || `<div class="alert alert-secondary mt-4">No results found</div>`;
}


// =====================
// EVENTS
// =====================

const searchInput = document.getElementById("search");
const clearBtn = document.getElementById("clearBtn");

// ---- SEARCH INPUT ----
searchInput.addEventListener("keyup", function(e) {
    state.search = e.target.value.toLowerCase().trim();

    // show/hide clear button
    clearBtn.style.display = state.search ? "inline" : "none";

    render();
});

// ---- CLEAR BUTTON CLICK ----
clearBtn.addEventListener("click", function() {
    searchInput.value = "";
    state.search = "";
    clearBtn.style.display = "none";
    render();
    searchInput.focus();
});

// ---- ESC KEY SUPPORT ----
searchInput.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
        searchInput.value = "";
        state.search = "";
        clearBtn.style.display = "none";
        render();
    }
});


// INIT
render();

</script>

</body>
</html>
"""

    # SAFE INJECTION
    html = html.replace("__DATA__", json.dumps(data))
    html = html.replace("__TIME__", datetime.now().strftime("%d-%b-%Y %H:%M"))

    OUTPUT_HTML.write_text(html)
    print("Portal created & uploaded at:", OUTPUT_HTML)


def main():
    data = json.loads(INPUT_JSON.read_text())

    for s in data.get("summary", []):
        s["firmware"] = clean_version(s.get("firmware"))

    generate_files(data)


if __name__ == "__main__":
    main()