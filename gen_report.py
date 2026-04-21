import re
import html
from pathlib import Path
from datetime import datetime
from typing import Optional

# --- CONFIGURATION ---
BASE_PATH = Path("/home/ivps/netapp/weekly")

PATHS = {
    "NetApp Security config": BASE_PATH / "netapp_security/",
    "Unity Security config": BASE_PATH / "unity_security/"
}

OUTPUT_DIR = BASE_PATH / "output"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = OUTPUT_DIR / f"security_report_{TIMESTAMP}.html"

# --- HTML TEMPLATE (EMAIL STYLE) ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Infrastructure Security Report</title>
</head>

<body style="font-family:Segoe UI, Arial, sans-serif; margin:0; padding:0;">

<table align="center" width="900" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr><td style="padding:20px;">

<h2 style="color:#3f51b5; text-align:center;">
Infrastructure Security Report
</h2>
<br />

{content}

<p style="text-align:center; font-size:13px;">
Generated at {date}
</p>

</td></tr></table>
</body>
</html>
"""

# --- UTIL ---
def safe(text: str) -> str:
    return html.escape((text or "").strip())

# --- RENDER HELPERS ---

def render_block_header(title):
    return f"""
    <table width="100%" cellpadding="6" cellspacing="0">
    <tr>
    <td style="background:#5768c4;color:#fff;font-weight:bold;text-align:center;text-transform:uppercase;">
    {safe(title)}
    </td>
    </tr>
    </table>
    <table width="100%"><tr><td height="8"></td></tr></table>
    """

def render_section_header(title):
    return f"""
    <table width="80%">
    <tr>
    <td style="color:#3f51b5;font-weight:bold;text-transform:uppercase;">
    {safe(title)}
    </td>
    </tr>
    </table>
    <table width="100%"><tr><td height="8"></td></tr></table>
    """

def render_horizontal_table(headers, rows):
    if not headers:
        return ""

    col_count = len(headers)

    normalized = [
        row[:col_count] + [""] * (col_count - len(row))
        for row in rows
    ]

    thead = "".join(f"<th>{safe(h)}</th>" for h in headers)

    tbody = ""
    for row in normalized:
        cells = "".join(f"<td>{safe(c)}</td>" for c in row)
        tbody += f"<tr>{cells}</tr>"

    return f"""
    <table width="100%" cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;">
    <tr style="background:#CBD0ED;font-weight:bold;">
    {thead}
    </tr>
    {tbody}
    </table>
    <br/>
    """

def render_vertical_table(pairs):
    if not pairs:
        return ""

    rows = ""
    for k, v in pairs:
        rows += f"""
        <tr>
        <td style="font-weight:bold; background:#CBD0ED; width:30%;">{safe(k)}</td>
        <td>{safe(v)}</td>
        </tr>
        """

    return f"""
    <table width="100%" cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;">
    {rows}
    </table>
    <br/>
    """

def render_status(text):
    return f"""
    <table width="60%">
    <tr>
    <td style="font-weight:bold;">
    {safe(text)}
    </td>
    </tr>
    </table>
    <table width="100%"><tr><td height="8"></td></tr></table>
    """

# --- NETAPP PARSER ---

def parse_netapp(content: str) -> str:
    lines = [l.rstrip() for l in content.splitlines()]
    i, n = 0, len(lines)
    html_chunks = []

    while i < n:
        line = lines[i].strip()

        # -------------------------------
        # BLOCK HEADER
        # -------------------------------
        if line.startswith("####"):
            title = re.sub(r"[#]+", "", line).strip()
            html_chunks.append(render_block_header(title))
            i += 1
            continue

        # -------------------------------
        # SKIP EMPTY / BLOCK END
        # -------------------------------
        if not line or "BLOCK COMPLETED" in line:
            i += 1
            continue

        # -------------------------------
        # SECTION HEADER
        # -------------------------------
        if line.startswith("SECTION:"):
            section = line.replace("SECTION:", "").strip()
            html_chunks.append(render_section_header(section))
            i += 1

            # detect empty section
            j = i
            while j < n and not lines[j].strip():
                j += 1

            if j >= n or lines[j].strip().startswith("SECTION:"):
                html_chunks.append(
                    render_vertical_table([("Status", "Not configured")])
                )
                i = j
                continue

            continue

        # -------------------------------
        # TABLE DETECTION
        # -------------------------------
        if i + 1 < n and re.match(r'^[-\s]{3,}$', lines[i + 1].strip()):
            header_line = lines[i]
            sep_line = lines[i + 1]

            # 🔴 FIX: detect single-column BEFORE span slicing
            if re.fullmatch(r'-+', sep_line.strip()):
                # single column → take full line, no slicing
                i += 2

                # skip blanks
                while i < n and not lines[i].strip():
                    i += 1

                value = ""
                if i < n:
                    value = lines[i].strip()
                    i += 1

                html_chunks.append(
                    render_vertical_table([("Status", value)])
                )
                continue

            # normal multi-column table
            spans = [(m.start(), m.end()) for m in re.finditer(r"-+", sep_line)]
            headers = [header_line[s:e].strip() for s, e in spans]

            i += 2
            rows = []

            while i < n:
                row_line = lines[i]

                if not row_line.strip():
                    break

                if row_line.startswith("SECTION:") or row_line.startswith("####"):
                    break

                row = [row_line[s:e].strip() for s, e in spans]
                rows.append(row)
                i += 1

            html_chunks.append(
                render_horizontal_table(headers, rows)
            )
            continue

        # -------------------------------
        # KEY-VALUE (rare)
        # -------------------------------
        if "=" in line:
            pairs = []
            while i < n and "=" in lines[i]:
                k, v = lines[i].split("=", 1)
                pairs.append((k.strip(), v.strip()))
                i += 1

            html_chunks.append(render_vertical_table(pairs))
            continue

        # -------------------------------
        # FALLBACK
        # -------------------------------
        html_chunks.append(
            render_vertical_table([("Status", line)])
        )
        i += 1

    return "".join(html_chunks)

# --- UNITY PARSER ---

def parse_unity(content: str) -> str:
    lines = [l.rstrip("\n") for l in content.splitlines()]
    i, n = 0, len(lines)
    html_chunks = []

    while i < n:
        line = lines[i].strip()

        # -------------------------------
        # BLOCK HEADER
        # -------------------------------
        if re.match(r'^[><]{10,}$', line):
            if i + 1 < n:
                candidate = lines[i + 1].strip()

                m = re.search(r'^(.*?)\s*\(IP\s*:\s*([^)]+)\)', candidate)
                if m:
                    hostname = m.group(1).strip()
                    ip = m.group(2).strip()
                    title = f"UNITY :: {hostname} :: {ip}"
                else:
                    title = f"UNITY :: {candidate}"

                html_chunks.append(render_block_header(title))

            i += 3
            continue

        # -------------------------------
        # SKIP EMPTY OR DECORATIVE =====
        # -------------------------------
        if not line or re.match(r'^[=]{5,}$', line):
            i += 1
            continue

        # -------------------------------
        # END OF REPORT (CENTERED)
        # -------------------------------
        if "END OF REPORT" in line.upper():
            html_chunks.append(
                '<p style="text-align:center; font-weight:bold;">END OF REPORT</p>'
            )
            break

        # -------------------------------
        # SECTION HEADER
        # -------------------------------
        if i + 1 < n and set(lines[i + 1].strip()) == {"="}:
            section = line
            html_chunks.append(render_section_header(section))
            i += 2

            # Handle single-line section (e.g. Not configured)
            j = i
            while j < n and not lines[j].strip():
                j += 1

            if j < n:
                next_line = lines[j].strip()

                if next_line and "=" not in next_line and not re.match(r'^[><]{10,}$', next_line):
                    if not (j + 1 < n and re.match(r'^[\-\s]{5,}$', lines[j + 1].strip())):
                        html_chunks.append(
                            render_vertical_table([("Status", next_line)])
                        )
                        i = j + 1
                        continue

            continue

        # -------------------------------
        # TABLE DETECTION
        # -------------------------------
        if i + 1 < n and re.match(r'^[\-\s]{5,}$', lines[i + 1].strip()):
            header_line = lines[i]
            sep_line = lines[i + 1]

            spans = [(m.start(), m.end()) for m in re.finditer(r"-+", sep_line)]
            headers = [header_line[s:e].strip() for s, e in spans]

            i += 2
            rows = []

            while i < n:
                row_line = lines[i].strip()

                # STOP CONDITIONS
                if not row_line:
                    i += 1
                    continue

                if re.match(r'^[><]{10,}$', row_line):
                    break

                if re.match(r'^[=]{5,}$', row_line):
                    break

                if "END OF REPORT" in row_line.upper():
                    break

                if i + 1 < n and set(lines[i + 1].strip()) == {"="}:
                    break

                raw_line = lines[i]
                row = [raw_line[s:e].strip() for s, e in spans]
                rows.append(row)
                i += 1

            html_chunks.append(render_horizontal_table(headers, rows))
            continue

        # -------------------------------
        # KEY-VALUE BLOCK
        # -------------------------------
        if "=" in line and not line.startswith("="):
            pairs = []

            while i < n:
                current = lines[i].strip()

                if not current or "=" not in current:
                    break

                if set(current) == {"="}:
                    break

                if "END OF REPORT" in current.upper():
                    break

                k, v = current.split("=", 1)
                pairs.append((k.strip(), v.strip()))
                i += 1

            html_chunks.append(render_vertical_table(pairs))
            continue

        # -------------------------------
        # STATUS / FALLBACK
        # -------------------------------
        html_chunks.append(render_status(line))
        i += 1

    return "".join(html_chunks)

# --- FILE HANDLING ---

def get_latest_file(directory: Path) -> Optional[Path]:
    try:
        return max(directory.iterdir(), key=lambda f: f.stat().st_mtime)
    except (ValueError, FileNotFoundError):
        return None

# --- MAIN ---

def generate_report():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report_body = []

    for label, path in PATHS.items():
        latest = get_latest_file(path)

        if not latest:
            report_body.append(render_status(f"No report found for {label}"))
            continue

        try:
            raw_data = latest.read_text(encoding="utf-8")

            if "NetApp" in label:
                report_body.append(parse_netapp(raw_data))
            else:
                report_body.append(parse_unity(raw_data))

        except Exception as e:
            report_body.append(render_status(f"Error parsing {label}: {e}"))

    full_html = HTML_TEMPLATE.format(
        content="".join(report_body),
        date=datetime.now().strftime("%I:%M %p %d-%b-%Y IST")
    )

    OUTPUT_FILE.write_text(full_html, encoding="utf-8")
    print(f"Report generated: {OUTPUT_FILE}")

# --- ENTRY POINT ---

if __name__ == "__main__":
    generate_report()