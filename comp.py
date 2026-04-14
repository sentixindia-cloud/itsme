import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime

BASE_DIR = "/home/ivps/netapp"
CLEAN_DIR = os.path.join(BASE_DIR, "output_cleaned")
DIFF_DIR = os.path.join(BASE_DIR, "output_diff")

os.makedirs(DIFF_DIR, exist_ok=True)

# -----------------------------
# Get latest 2 files
# -----------------------------
cmd = f"find {CLEAN_DIR} -type f -printf '%T@ %p\n' | sort -nr | head -2"
files = [line.split(" ", 1)[1] for line in subprocess.check_output(cmd, shell=True, text=True).splitlines()]

old_file, new_file = files[1], files[0]

# -----------------------------
# Parse file
# -----------------------------
def parse(filepath):
    with open(filepath) as f:
        lines = f.readlines()

    data = defaultdict(dict)

    block = None
    section = None
    buffer = []

    for line in lines:
        if "NETAPP" in line:
            block = line.strip()
            continue

        if line.startswith("SECTION:"):
            if section and buffer:
                data[block][section] = buffer

            section = line.strip().lower()
            buffer = []
            continue

        if section:
            if "BLOCK COMPLETED" in line:
                continue
            buffer.append(line.rstrip("\n"))

    if section and buffer:
        data[block][section] = buffer

    return data

# -----------------------------
# Parse table into structured form
# -----------------------------
def parse_table(lines):
    header_line = None
    dash_line = None
    rows = []

    for i, line in enumerate(lines):
        if re.match(r'^[- ]+$', line):
            dash_line = line
            header_line = lines[i-1]
            rows = lines[i+1:]
            break

    if not header_line:
        return None

    headers = re.split(r'\s{2,}', header_line.strip())

    parsed_rows = []
    for row in rows:
        if not row.strip():
            continue
        values = re.split(r'\s{2,}', row.strip())
        if len(values) != len(headers):
            continue
        parsed_rows.append(dict(zip(headers, values)))

    return headers, dash_line, parsed_rows

# -----------------------------
# Build key-based map
# -----------------------------
def build_map(headers, rows):
    lower_headers = [h.lower() for h in headers]

    if "vserver" in lower_headers and "volume" in lower_headers:
        key_col = headers[lower_headers.index("volume")]
    else:
        key_col = headers[0]

    result = {}
    for row in rows:
        key = row.get(key_col)
        if key:
            result[key] = row

    return key_col, result

# -----------------------------
# Compare
# -----------------------------
old_data = parse(old_file)
new_data = parse(new_file)

output = []

for block in sorted(set(old_data) | set(new_data)):

    block_printed = False

    old_sections = old_data.get(block, {})
    new_sections = new_data.get(block, {})

    for section in sorted(set(old_sections) | set(new_sections)):

        old_table = parse_table(old_sections.get(section, []))
        new_table = parse_table(new_sections.get(section, []))

        if not old_table and not new_table:
            continue

        headers = None
        dash = None

        if new_table:
            headers, dash, new_rows = new_table
        else:
            headers, dash, new_rows = old_table

        old_rows = old_table[2] if old_table else []
        new_rows = new_table[2] if new_table else []

        key_col, old_map = build_map(headers, old_rows)
        _, new_map = build_map(headers, new_rows)

        changes = []

        all_keys = set(old_map) | set(new_map)

        for key in all_keys:
            if key not in new_map:
                for col, val in old_map[key].items():
                    changes.append((col, val, "-", "removed"))

            elif key not in old_map:
                for col, val in new_map[key].items():
                    changes.append((col, "-", val, "added"))

            else:
                for col in headers:
                    old_val = old_map[key].get(col, "")
                    new_val = new_map[key].get(col, "")
                    if old_val != new_val:
                        changes.append((col, old_val, new_val, "changed"))

        if not changes:
            continue

        # Print block header only once
        if not block_printed:
            output.append(f"\n{block}\n\n")
            block_printed = True

        output.append(f"{section.upper()}\n\n")

        # Prepare rows (including header)
        table = [("column", "old value", "new value", "change type")] + changes

        # Calculate max width for each column
        col_widths = [0, 0, 0, 0]

        for row in table:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))

        # Helper to format row
        def format_row(row):
            return "  ".join(
                str(val).ljust(col_widths[i])
                for i, val in enumerate(row)
            )

        # Header
        output.append(format_row(table[0]) + "\n")

        # Separator (dynamic dashed line)
        separator = "  ".join("-" * w for w in col_widths)
        output.append(separator + "\n")

        # Data rows
        for row in table[1:]:
            output.append(format_row(row) + "\n")

        output.append("\n")

# -----------------------------
# Save
# -----------------------------
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out_file = os.path.join(DIFF_DIR, f"diff_output_{ts}.txt")

with open(out_file, "w") as f:
    f.writelines(output)

print("Diff saved to:", out_file)