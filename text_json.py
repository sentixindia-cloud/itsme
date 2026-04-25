import re
import json
import socket
import subprocess
from pathlib import Path

INPUT_FILE = "discovery_result.txt"
OUTPUT_FILE = "parsed_output.json"


# ---------------- UTIL ----------------

def safe_split(line):
    if "=" in line:
        k, v = line.split("=", 1)
        return k.strip(), v.strip()
    return None, None


def resolve_ip(hostname):
    candidates = [
        hostname,
        hostname.split(".")[0],
        hostname.lower(),
        hostname.split(".")[0].lower()
    ]

    for host in candidates:
        try:
            return socket.gethostbyname(host)
        except:
            continue

    for host in candidates:
        try:
            out = subprocess.check_output(["nslookup", host], text=True)
            match = re.search(r"Address:\s+([0-9.]+)", out)
            if match:
                return match.group(1)
        except:
            continue

    return None


def get_region(fqdn):
    fqdn = fqdn.lower()
    if "am.munichre.com" in fqdn:
        return "AMER"
    if "eu.munichre.com" in fqdn:
        return "EMEA"
    if "as.munichre.com" in fqdn:
        return "APAC"
    if "munich.munichre.com" in fqdn:
        return "EMEA"
    return "UNKNOWN"


def extract_tb(value):
    m = re.search(r"\(([\d.]+)T\)", value)
    return float(m.group(1)) if m else None

# ---------------- CLI ROW NORMALIZER ----------------

def read_full_row(lines, i):
    """
    Combines wrapped CLI lines into one logical row.
    A row starts with non-indented text and may continue
    on following indented lines.
    """
    line = lines[i]

    # skip header separators or empty lines
    if not line.strip() or line.strip().startswith("-"):
        return line.strip(), i

    full = line.rstrip()

    j = i + 1
    while j < len(lines):
        nxt = lines[j]

        # continuation lines are indented
        if nxt.startswith(" ") and nxt.strip():
            full += " " + nxt.strip()
            j += 1
        else:
            break

    return full.strip(), j - 1

# =========================
# UNITY PARSER (STRUCTURED)
# =========================

def parse_unity(content, summary, unity_arrays):

    blocks = re.findall(r"### UNITY :: (.*?) ###(.*?)(?=### UNITY|### NETAPP|$)", content, re.S)

    for fqdn, block in blocks:

        fqdn = fqdn.strip()
        name = fqdn.split(".")[0]

        model = serial = version = None

        unity_obj = {
            "array_name": name,
            "capacity": [],
            "nas": [],
            "replication": []
        }

        section = None
        current_nas = None
        current_rep = None

        total = remaining = pool_name = None

        lines = block.splitlines()

        for i, raw in enumerate(lines):
            line = raw.strip()
            if not line:
                continue

            # ---- SECTION SWITCH ----
            if line.startswith("System Information"):
                section = "system"
                continue
            elif line.startswith("Software Version"):
                section = "software"
                continue
            elif line.startswith("Storage Pool Capacity"):
                section = "capacity"
                continue
            elif line.startswith("NAS Servers"):
                section = "nas"
                continue
            elif line.startswith("Replication Details"):
                section = "replication"
                continue

            k, v = safe_split(line)

            # ---- SYSTEM ----
            if section == "system" and k:
                if k == "Model":
                    model = v
                elif k == "Product serial number":
                    serial = v

            # ---- SOFTWARE ----
            elif section == "software" and k == "Version":
                version = v

            # ---- CAPACITY ----
            elif section == "capacity" and k:
                if k == "Name":
                    pool_name = v

                elif k == "Total space":
                    total = extract_tb(v)

                elif k == "Remaining space":
                    remaining = extract_tb(v)

                    if total and remaining:
                        used = round((1 - remaining / total) * 100, 1)

                        unity_obj["capacity"].append({
                            "name": pool_name,
                            "total_tb": total,
                            "used_percent": used,
                            "remaining_tb": remaining
                        })

            # ---- NAS ----
            elif section == "nas" and k:

                if k == "Name":
                    if current_nas:
                        unity_obj["nas"].append(current_nas)

                    current_nas = {"name": v}

                elif current_nas:
                    if "NFSv3" in k:
                        current_nas["nfs3"] = v
                    elif "NFSv4" in k:
                        current_nas["nfs4"] = v
                    elif "CIFS" in k:
                        current_nas["cifs"] = v
                    elif "Multiprotocol" in k:
                        current_nas["multiprotocol"] = v

            # ---- REPLICATION ----
            elif section == "replication" and k:

                if k == "Name":
                    if current_rep and "local" not in current_rep.get("model", "").lower():
                        unity_obj["replication"].append(current_rep)

                    current_rep = {"name": v}

                elif current_rep:
                    if k == "Model":
                        current_rep["model"] = v
                    elif "Connection" in k:
                        current_rep["connection"] = v

        # flush
        if current_nas:
            unity_obj["nas"].append(current_nas)

        if current_rep and "local" not in current_rep.get("model", "").lower():
            unity_obj["replication"].append(current_rep)

        # ---- SUMMARY ----
        summary.append({
            "array_name": name,
            "storage_type": "Unity",
            "model": model,
            "ip": resolve_ip(fqdn),
            "serial_number": serial,
            "region": get_region(fqdn),
            "firmware": version
        })

        unity_arrays.append(unity_obj)


# =========================
# NETAPP PARSER (STRUCTURED)
# =========================

def parse_netapp(content, summary, netapp_arrays):

    # -------- helper: safely merge wrapped CLI rows --------
    def read_full_row(lines, i):
        full = lines[i].rstrip()
        j = i + 1

        while j < len(lines):
            nxt = lines[j]

            # continuation lines are indented
            if nxt.startswith(" ") and nxt.strip():
                full += " " + nxt.strip()
                j += 1
            else:
                break

        return full.strip(), j   # IMPORTANT: return next index


    blocks = re.findall(r"### NETAPP :: (.*?) ###(.*?)(?=### NETAPP|=====|$)", content, re.S)

    for fqdn, block in blocks:

        fqdn = fqdn.strip()
        base = fqdn.split(".")[0]

        netapp_obj = {
            "array_name": base,
            "aggregates": [],
            "vservers": []
        }

        lines = block.splitlines()

        ip_map = {}
        model_map = {}
        version_map = {}
        nodes = []

        section = None
        i = 0

        while i < len(lines):

            line = lines[i].strip()
            next_i = i + 1   # default movement

            # -------- SECTION DETECTION --------
            if "network interface show" in line:
                section = "network"

            elif "vserver show" in line:
                section = "vserver"

            elif "storage aggregate show" in line:
                section = "aggregate"

            # -------- NETWORK --------
            elif section == "network" and re.search(r"\d+\.\d+\.\d+\.\d+", line):
                parts = line.split()
                if len(parts) >= 5:
                    ip = parts[2].split("/")[0]
                    node = parts[3]
                    ip_map[node] = ip

            # -------- VERSION --------
            elif line.endswith(":") and "-" in line:
                node = line.replace(":", "").strip()
                if i + 1 < len(lines) and "NetApp Release" in lines[i + 1]:
                    version_map[node] = lines[i + 1].strip()

            # -------- CONTROLLER --------
            elif re.match(r"^\w+-\d+\s+\d+", line):
                parts = line.split()
                node = parts[0]
                serial = parts[2]
                model = parts[3]

                model_map[node] = (model, serial)
                nodes.append(node)

            # -------- AGGREGATES (FIXED) --------
            elif section == "aggregate" and re.match(r"^\w", line) and "Aggregate" not in line:

                full_line, next_i = read_full_row(lines, i)
                parts = full_line.split()

                if len(parts) >= 5:
                    netapp_obj["aggregates"].append({
                        "name": parts[0],
                        "size": parts[1],
                        "available": parts[2],
                        "used_percent": parts[3],
                        "state": parts[4]
                    })

            # -------- VSERVER (FIXED) --------
            elif section == "vserver":

                # detect header separator line
                if re.match(r"^-+\s+-+", line):
                    # compute column spans from separator
                    spans = [(m.start(), m.end()) for m in re.finditer(r"-+", line)]
                    i += 1
                    continue

                # skip header lines
                if "Vserver" in line or "Admin" in line:
                    i += 1
                    continue

                # skip empty
                if not line.strip():
                    i += 1
                    continue

                # --- START ROW CAPTURE ---
                row_lines = [line]

                j = i + 1

                # capture continuation lines (indented lines)
                while j < len(lines):
                    nxt = lines[j]

                    # stop conditions
                    if not nxt.strip():
                        break
                    if re.match(r"^\w", nxt):  # new row starts
                        break
                    if "aggregate show" in nxt.lower():
                        break

                    row_lines.append(nxt)
                    j += 1

                # merge lines using column spans
                merged = [""] * len(spans)

                for rl in row_lines:
                    for idx, (s, e) in enumerate(spans):
                        part = rl[s:e].strip()
                        if part:
                            merged[idx] += part

                # now safely map columns
                if len(merged) >= 7:
                    netapp_obj["vservers"].append({
                        "name": merged[0],
                        "type": merged[1],
                        "operational_state": merged[4],
                        "root_volume": merged[5],
                        "aggregate": merged[6]
                    })

                i = j
                continue

            # -------- MOVE POINTER --------
            i = next_i


        # -------- SUMMARY PER NODE --------
        for node in nodes:
            summary.append({
                "array_name": node.upper(),
                "storage_type": "NetApp",
                "model": model_map.get(node, ("", ""))[0],
                "ip": ip_map.get(node) or resolve_ip(node),
                "serial_number": model_map.get(node, ("", ""))[1],
                "region": get_region(fqdn),
                "firmware": version_map.get(node)
            })

        netapp_arrays.append(netapp_obj)


# =========================
# MAIN
# =========================

def main():

    content = Path(INPUT_FILE).read_text()

    summary = []
    unity = []
    netapp = []

    parse_unity(content, summary, unity)
    parse_netapp(content, summary, netapp)

    output = {
        "summary": summary,
        "unity": unity,
        "netapp": netapp
    }

    Path(OUTPUT_FILE).write_text(json.dumps(output, indent=2))
    print(f"JSON generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()