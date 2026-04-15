import os
import re
import glob
from datetime import datetime

BASE_DIR = "/home/ivps/netapp"
DIFF_DIR = os.path.join(BASE_DIR, "output_diff")
HTML_DIR = os.path.join(BASE_DIR, "output_html")

os.makedirs(HTML_DIR, exist_ok=True)

# -----------------------------
# Get latest diff file
# -----------------------------
files = sorted(glob.glob(f"{DIFF_DIR}/diff_output_*.txt"), key=os.path.getmtime)

if not files:
    raise Exception("No diff files found")

INPUT_FILE = files[-1]
timestamp = os.path.basename(INPUT_FILE).replace("diff_output_", "").replace(".txt", "")
OUTPUT_FILE = f"{HTML_DIR}/report_{timestamp}.html"

# -----------------------------
# Parse file into structure
# -----------------------------
def parse():
    with open(INPUT_FILE) as f:
        lines = [l.rstrip() for l in f]

    blocks = []
    block = None
    section = None

    for line in lines:
        if line.startswith("#### NETAPP"):
            block = {"title": line.strip(), "sections": []}
            blocks.append(block)

        elif line.startswith("SECTION"):
            section = {"name": line.replace("SECTION:", "").strip(), "rows": []}
            block["sections"].append(section)

        elif section:
            section["rows"].append(line)

    return blocks

# -----------------------------
# Extract clean rows (skip header)
# -----------------------------
def extract_data_rows(lines):
    data_rows = []
    header_found = False

    for line in lines:
        lower = line.lower().strip()

        # detect header row
        if "changed field" in lower and "column" in lower:
            header_found = True
            continue

        # skip dashed line
        if header_found and re.match(r'^[-\s]+$', line):
            continue

        # collect actual data
        if header_found and line.strip():
            data_rows.append(line)

    return data_rows

# -----------------------------
# Split row into columns
# -----------------------------
def split_row(row):
    return re.split(r'\s{2,}', row.strip())

# -----------------------------
# Format block title
# -----------------------------
def format_block_title(raw):
    m = re.search(r'NETAPP\s*::\s*(.*?)\s*::\s*([\d\.]+)', raw)
    if m:
        fqdn = m.group(1).upper()
        ip = m.group(2)
        return f"{fqdn} (IP : {ip})"
    return raw

# -----------------------------
# HTML builder
# -----------------------------
def build_html(blocks):

    html = []

    html.append("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>NetApp Config Difference Report</title>
</head>

<body style="font-family:Segoe UI, Arial, sans-serif; margin:0; padding:0;">

<table align="center" width="900" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr><td style="padding:20px;">

<h2 style="color:#3f51b5; text-align:center;">
NetApp Config Difference Report
</h2>
<br />
""")

    for block in blocks:

        title = format_block_title(block["title"])

        # Block Header
        html.append(f"""
<table width="100%" cellpadding="6" cellspacing="0">
<tr>
<td style="background:#5768c4;color:#fff;font-weight:bold;text-align:center;text-transform:uppercase;">
{title}
</td>
</tr>
</table>

<table width="100%"><tr><td height="8"></td></tr></table>
""")

        for sec in block["sections"]:

            clean_rows = extract_data_rows(sec["rows"])
            if not clean_rows:
                continue

            # Section Header
            html.append(f"""
<table width="80%">
<tr>
<td style="color:#3f51b5;font-weight:bold;text-transform:uppercase;">
{sec['name']}
</td>
</tr>
</table>

<table width="100%"><tr><td height="8"></td></tr></table>
""")

            # Group by key (changed field)
            grouped = {}

            for row in clean_rows:
                parts = split_row(row)
                if len(parts) < 5:
                    continue

                key = parts[0]
                grouped.setdefault(key, []).append(parts)

            for key, rows in grouped.items():

                # Key Header
                html.append(f"""
<table width="60%">
<tr>
<td style="font-weight:bold;">
Changed Field: {key}
</td>
</tr>
</table>

<table width="100%"><tr><td height="8"></td></tr></table>
""")

                # Table
                html.append("""
<table width="100%" cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;">
<tr style="background:#e6e6e6;font-weight:bold;">
<th>Column</th>
<th>Old Value</th>
<th>New Value</th>
<th>Change</th>
</tr>
""")

                for r in rows:
                    col, old, new, typ = r[1], r[2], r[3], r[4]

                    color = {
                        "changed": "orange",
                        "added": "green",
                        "removed": "red"
                    }.get(typ.lower(), "black")

                    html.append(f"""
<tr>
<td>{col}</td>
<td>{old}</td>
<td>{new}</td>
<td style="color:{color}; font-weight:bold;">{typ.upper()}</td>
</tr>
""")

                html.append("</table><br/>")

    # Footer
    html.append(f"""
<p style="text-align:center; font-weight:bold;">
END OF REPORT
</p>

<p style="text-align:center; font-size:13px;">
Generated at {datetime.now().strftime("%I:%M %p %d-%b-%Y IST")}
</p>

</td></tr></table>
</body>
</html>
""")

    return "".join(html)

# -----------------------------
# Run
# -----------------------------
blocks = parse()
html = build_html(blocks)

with open(OUTPUT_FILE, "w") as f:
    f.write(html)

print("HTML report saved to:", OUTPUT_FILE)