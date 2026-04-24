import re, json
from pathlib import Path
from datetime import datetime

INPUT_JSON = Path("parsed_output.json")
OUTPUT_HTML = Path("discovery_portal.html")


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
<title>Storage Discovery Portal</title>

<link rel="stylesheet" href="styles.css">

</head>

<body>

<div class="container">

<input id="search" class="search" placeholder="Search anything...">

<div id="app"></div>

<p class="footer">
Generated at __TIME__
</p>

</div>

<script>
const DATA = __DATA__;
</script>

<script src="app.js"></script>

</body>
</html>
"""

    css = """
body {
    font-family: Segoe UI, Arial, sans-serif;
    background: white;
    margin: 0;
    padding: 20px;
    color: #000;
}

.container {
    width: 75%;
    margin: 0 auto;
}

.block-header {
    background: #5c6bc0;
    color: white;
    padding: 10px;
    font-weight: bold;
    text-align: center;
    margin-top: 30px;
}

.table-title {
    margin-top: 20px;
    margin-bottom: 5px;
    font-weight: bold;
    color: #3f51b5;
    text-transform: uppercase;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
}

th {
    background: #d3d6ea;
}

td, th {
    border: 1px solid #999;
    padding: 8px;
}

.search {
    width: 100%;
    padding: 8px;
    border: 1px solid #999;
    margin-bottom: 20px;
}

tr:hover {
    background: #f5f7ff;
}

.footer {
    text-align:center;
    font-size:12px;
    margin-top:30px;
}
"""

    js = """
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
    if (val === "yes") return `<span style="background:#c8e6c9;padding:2px 6px;">YES</span>`;
    if (val === "no") return `<span style="background:#ffcdd2;padding:2px 6px;">NO</span>`;
    return val ?? "";
}

function createTable(title, headers, rows) {
    if (!rows.length) return "";

    let html = `<div class="table-title">${title}</div><table><tr>`;
    headers.forEach(h => html += `<th>${h}</th>`);
    html += "</tr>";

    rows.forEach(r => {
        html += "<tr>";
        r.forEach(c => html += `<td>${c ?? ""}</td>`);
        html += "</tr>";
    });

    html += "</table>";
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


// =====================
// SUMMARY
// =====================

function Summary() {

    const keywordHit = textMatch("summary");

    const rows = state.data.summary
        .filter(r => keywordHit || match(r))
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

    return createTable(
        "Summary",
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

        const capacity = u.capacity.filter(r => arrayHit || match(r));
        const nas = u.nas.filter(r => arrayHit || match(r));
        const repl = u.replication.filter(r => arrayHit || match(r));

        if (!capacity.length && !nas.length && !repl.length) return "";

        return `
        ${header(u.array_name)}

        ${createTable("Capacity",
            ["Pool Name","Total TB","Used %","Remaining TB"],
            capacity.map(c => [
                (c.name || "").toUpperCase(),
                c.total_tb,
                c.used_percent,
                c.remaining_tb
            ])
        )}

        ${createTable("NAS Servers",
            ["Name","NFSv3","NFSv4","CIFS","Multiprotocol"],
            nas.map(n => [
                n.name,
                badge(n.nfs3),
                badge(n.nfs4),
                badge(n.cifs),
                badge(n.multiprotocol)
            ])
        )}

        ${createTable("Replication",
            ["Target Array Name","Model","Replication Type"],
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

        const aggr = n.aggregates.filter(r => arrayHit || match(r));
        const vs = n.vservers.filter(r => arrayHit || match(r));

        if (!aggr.length && !vs.length) return "";

        return `
        ${header(n.array_name)}

        ${createTable("Aggregates",
            ["Name","Size","Available","Used %","State"],
            aggr.map(a => [
                a.name, a.size, a.available, a.used_percent, a.state
            ])
        )}

        ${createTable("VServers",
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
        html || `<div style="padding:20px;color:#777;">No results found</div>`;
}


// =====================
// DEBOUNCE
// =====================

function debounce(fn, delay) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
    };
}


// =====================
// EVENTS
// =====================

document.getElementById("search").addEventListener("keyup",
    debounce(e => {
        state.search = e.target.value.toLowerCase();
        render();
    }, 250)
);


// INIT
render();
"""

    # inject data
    html = html.replace("__DATA__", json.dumps(data))
    html = html.replace("__TIME__", datetime.now().strftime("%d-%b-%Y %H:%M"))

    # write files
    Path("discovery_portal.html").write_text(html)
    Path("styles.css").write_text(css)
    Path("app.js").write_text(js)

    print("✅ Generated: HTML + CSS + JS (modular)")


def main():
    data = json.loads(INPUT_JSON.read_text())

    for s in data.get("summary", []):
        s["firmware"] = clean_version(s.get("firmware"))

    generate_files(data)


if __name__ == "__main__":
    main()