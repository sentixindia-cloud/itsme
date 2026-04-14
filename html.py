import os, re
import glob

BASE_DIR = "/home/ivps/netapp"
DIFF_DIR = os.path.join(BASE_DIR, "output_diff")
HTML_DIR = os.path.join(BASE_DIR, "output_html")

os.makedirs(HTML_DIR, exist_ok=True)

# -----------------------------
# Find latest diff file
# -----------------------------
files = sorted(
    glob.glob(os.path.join(DIFF_DIR, "diff_output_*.txt")),
    key=os.path.getmtime
)

if not files:
    raise Exception("No diff files found")

INPUT_FILE = files[-1]

# extract timestamp from filename
filename = os.path.basename(INPUT_FILE)
timestamp = filename.replace("diff_output_", "").replace(".txt", "")

OUTPUT_FILE = os.path.join(HTML_DIR, f"report_{timestamp}.html")

def parse_file(filepath):
    with open(filepath) as f:
        lines = [l.rstrip("\n") for l in f]

    blocks = []
    current_block = None
    current_section = None

    for line in lines:
        if line.startswith("#### NETAPP"):
            current_block = {
                "title": line.strip(),
                "sections": []
            }
            blocks.append(current_block)

        elif line.startswith("SECTION:"):
            current_section = {
                "name": line.replace("SECTION:", "").strip(),
                "table": []
            }
            current_block["sections"].append(current_section)

        elif current_section and line.strip():
            current_section["table"].append(line)

    return blocks


def parse_table(lines):
    if not lines:
        return [], []

    headers = re.split(r'\s{2,}', lines[0].strip())
    rows = []

    for line in lines[2:]:  # skip dashed line
        cols = re.split(r'\s{2,}', line.strip())
        if len(cols) == len(headers):
            rows.append(cols)

    return headers, rows


def build_html(blocks):
    html = []

    html.append("""
<html>
<body style="font-family: Arial, sans-serif; font-size: 13px;">
""")

    for block in blocks:
        # Extract FQDN and IP
        match = re.search(r'NETAPP\s*::\s*(.*?)\s*::\s*([\d\.]+)', block['title'])

        if match:
            fqdn = match.group(1).strip()
            ip = match.group(2).strip()
            clean_title = f"{fqdn.upper()} ({ip})"
        else:
            clean_title = block['title']

        html.append(f"""
        <h2 style="background:#f2f2f2;padding:8px;border:1px solid #ccc;">
        {clean_title}
        </h2>
        """)

        for section in block["sections"]:
            headers, rows = parse_table(section["table"])

            if not headers:
                continue

            html.append(f"""
<h3 style="margin-top:15px;">{section['name']}</h3>
<table style="border-collapse: collapse; width:100%; margin-bottom:15px;">
<tr>
""")

            # header row
            for h in headers:
                html.append(f"""
<th style="border:1px solid #ccc; padding:6px; background:#e6e6e6;">
{h}
</th>
""")

            html.append("</tr>")

            # data rows
            for row in rows:
                html.append("<tr>")
                for cell in row:
                    html.append(f"""
<td style="border:1px solid #ccc; padding:6px;">
{cell}
</td>
""")
                html.append("</tr>")

            html.append("</table>")

    html.append("</body></html>")

    return "".join(html)


def main():
    blocks = parse_file(INPUT_FILE)
    html = build_html(blocks)

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"HTML report saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
