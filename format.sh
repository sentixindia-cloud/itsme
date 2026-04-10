#!/bin/bash
# ---------------------------------------------------------
# NetApp Security Automation - Block + Section Framework
# ---------------------------------------------------------

BASE_DIR="/home/ivps/netapp"
RAW_DIR="$BASE_DIR/output_raw"
CLEAN_DIR="$BASE_DIR/output_cleaned"

mkdir -p "$CLEAN_DIR"

LATEST_FILE=$(ls -t "$RAW_DIR"/*.txt 2>/dev/null | head -n 1)
[[ ! -f "$LATEST_FILE" ]] && { echo "No input files found"; exit 1; }

TS=$(date +"%Y%m%d_%H%M%S")
OUTPUT_FILE="$CLEAN_DIR/cleaned_output_$TS.txt"

SEP="========================================================="

# ---------------------------------------------------------
# Pre-process file → collapse multiple blank lines
# ---------------------------------------------------------
TEMPFILE=$(mktemp)
sed '/^$/N;/^\n$/D' "$LATEST_FILE" > "$TEMPFILE"

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
process_storage_aggr() {
    local section="$1"

    echo "SECTION: AGGREGATE KEY ENCRYPTION"
    echo ""

    echo "$section" | awk '
        BEGIN { in_table = 0 }

        /::> storage aggregate show -fields encrypt-with-aggr-key/ {
            in_table=1
            next
        }

        /entries were displayed/ {
            in_table=0
            next
        }

        in_table==1 {

            if ($0 ~ /^$/) next
            if ($0 ~ /^-+/) { print; next }

            if (NF == 2) {
                printf "%-25s %-21s\n", $1, $2
            } else {
                print
            }
        }
    '
}

process_volume_encryption() {
    local section="$1"

    echo "SECTION: VOLUME ENCRYPTION STATUS"
    echo ""

    echo "$section" | awk '
        BEGIN {
            FS = "[ \t]+"
            in_table = 0
            row = 0
        }

        # Skip CLI line
        /::> vol show/ { next }

        # Detect header
        /^[ \t]*vserver[ \t]+volume[ \t]+encrypt[ \t]+is-encrypted/ {
            in_table = 1
            next
        }

        # Skip separator
        $1 ~ /^-+$/ { next }

        # End of table
        /entries were displayed/ { in_table = 0; next }

        # Process rows
        in_table {
            if (NF < 4) next

            vserver = $1
            volume  = $2
            encrypt = $3
            isenc   = $4

            data[row,1] = vserver
            data[row,2] = volume
            data[row,3] = encrypt
            data[row,4] = isenc

            # Track max width
            if (length(vserver) > w1) w1 = length(vserver)
            if (length(volume)  > w2) w2 = length(volume)
            if (length(encrypt) > w3) w3 = length(encrypt)
            if (length(isenc)   > w4) w4 = length(isenc)

            row++
        }

        END {
            if (row == 0) exit

            h1="vserver"; h2="volume"; h3="encrypt"; h4="is-encrypted"

            if (length(h1)>w1) w1=length(h1)
            if (length(h2)>w2) w2=length(h2)
            if (length(h3)>w3) w3=length(h3)
            if (length(h4)>w4) w4=length(h4)

            # Header
            printf "%-*s  %-*s  %-*s  %-*s\n", w1,h1, w2,h2, w3,h3, w4,h4

            # Separator
            for (i=1;i<=w1;i++) printf "-"
            printf "  "
            for (i=1;i<=w2;i++) printf "-"
            printf "  "
            for (i=1;i<=w3;i++) printf "-"
            printf "  "
            for (i=1;i<=w4;i++) printf "-"
            printf "\n"

            # Rows
            for (r=0; r<row; r++) {
                printf "%-*s  %-*s  %-*s  %-*s\n",
                    w1,data[r,1],
                    w2,data[r,2],
                    w3,data[r,3],
                    w4,data[r,4]
            }
        }
    '
}

process_log_forwarding() {
    local section="$1"

    echo "SECTION: CLUSTER LOG FORWARDING STATUS"
    echo ""

    echo "$section" | awk '
    BEGIN {
        FS="[ \t]+"
    }

    # --- Pre-clean stream (handle wrapped lines) ---
    {
        gsub(/\r/, "")
        if ($0 ~ /^[ \t]+IPspace:/) {
            lines[n++] = $0
        } else if ($0 ~ /^[ \t]+[A-Za-z0-9]/ && n > 0) {
            sub(/^[ \t]+/, "", $0)
            lines[n-1] = lines[n-1] $0
        } else {
            lines[n++] = $0
        }
    }

    END {
        in_table=0; row=-1

        for (i=0; i<n; i++) {
            line = lines[i]

            if (line ~ /::> cluster log-forwarding show/) continue
            if (line ~ /^[ \t]*Destination[ \t]+Host/) { in_table=1; continue }
            if (line ~ /^[ \t-]+$/) continue
            if (line ~ /entries were displayed/) break

            if (!in_table) continue

            # Continuation (IPspace)
            if (line ~ /^[ \t]*IPspace:/) {
                sub(/^[ \t]*IPspace:[ \t]*/, "", line)
                data[row,6]=line
                if (length(line)>w6) w6=length(line)
                continue
            }

            # Main row
            split(line,f,/[ \t]+/)
            if (length(f) != 5) continue

            row++
            data[row,1]=f[1]
            data[row,2]=f[2]
            data[row,3]=f[3]
            data[row,4]=f[4]
            data[row,5]=f[5]
            data[row,6]=""

            if (length(f[1])>w1) w1=length(f[1])
            if (length(f[2])>w2) w2=length(f[2])
            if (length(f[3])>w3) w3=length(f[3])
            if (length(f[4])>w4) w4=length(f[4])
            if (length(f[5])>w5) w5=length(f[5])
        }

        if (row < 0) exit

        h1="Destination Host"; h2="Port"; h3="Protocol"
        h4="Verify Server"; h5="Syslog Facility"; h6="IPspace"

        if (length(h1)>w1) w1=length(h1)
        if (length(h2)>w2) w2=length(h2)
        if (length(h3)>w3) w3=length(h3)
        if (length(h4)>w4) w4=length(h4)
        if (length(h5)>w5) w5=length(h5)
        if (length(h6)>w6) w6=length(h6)

        # Header
        printf "%-*s  %-*s  %-*s  %-*s  %-*s  %-*s\n",
            w1,h1,w2,h2,w3,h3,w4,h4,w5,h5,w6,h6

        # Separator
        for(i=1;i<=w1;i++)printf "-"; printf "  "
        for(i=1;i<=w2;i++)printf "-"; printf "  "
        for(i=1;i<=w3;i++)printf "-"; printf "  "
        for(i=1;i<=w4;i++)printf "-"; printf "  "
        for(i=1;i<=w5;i++)printf "-"; printf "  "
        for(i=1;i<=w6;i++)printf "-"
        printf "\n"

        # Rows
        for(r=0;r<=row;r++)
            printf "%-*s  %-*s  %-*s  %-*s  %-*s  %-*s\n",
                w1,data[r,1],w2,data[r,2],w3,data[r,3],
                w4,data[r,4],w5,data[r,5],w6,data[r,6]
    }'
}

process_event_notification() {
    local section="$1"

    echo "SECTION: EVENT NOTIFICATION DESTINATION"
    echo ""

    echo "$section" | awk '
    BEGIN {
        FS="[ \t]+"
    }

    # --- FIX WRAPPED LINES ---
    {
        gsub(/\r/, "")

        # If line starts with spaces and previous line exists → continuation
        if ($0 ~ /^[ \t]+[A-Za-z0-9]/ && n > 0) {
            sub(/^[ \t]+/, "", $0)
            lines[n-1] = lines[n-1] $0
        } else {
            lines[n++] = $0
        }
    }

    END {
        in_table=0; row=0

        for (i=0; i<n; i++) {
            line = lines[i]

            if (line ~ /::> event notification destination show/) continue
            if (line ~ /^[ \t]*Name[ \t]+Type[ \t]+Destination/) { in_table=1; continue }
            if (line ~ /^[ \t-]+$/) continue
            if (line ~ /entries were displayed/) break

            if (!in_table) continue

            split(line,f,/[ \t]+/)
            if (length(f) < 3) continue

            name = f[1]
            type = f[2]

            dest = f[3]
            for (j=4; j<=length(f); j++)
                dest = dest " " f[j]

            data[row,1]=name
            data[row,2]=type
            data[row,3]=dest

            if (length(name)>w1) w1=length(name)
            if (length(type)>w2) w2=length(type)
            if (length(dest)>w3) w3=length(dest)

            row++
        }

        if (row==0) exit

        h1="Name"; h2="Type"; h3="Destination"

        if (length(h1)>w1) w1=length(h1)
        if (length(h2)>w2) w2=length(h2)
        if (length(h3)>w3) w3=length(h3)

        # Header
        printf "%-*s  %-*s  %-*s\n", w1,h1, w2,h2, w3,h3

        # Separator
        for(i=1;i<=w1;i++)printf "-"; printf "  "
        for(i=1;i<=w2;i++)printf "-"; printf "  "
        for(i=1;i<=w3;i++)printf "-"
        printf "\n"

        # Rows
        for(r=0;r<row;r++)
            printf "%-*s  %-*s  %-*s\n",
                w1,data[r,1],
                w2,data[r,2],
                w3,data[r,3]
    }'
}

process_event_config() {
    local section="$1"

    echo "SECTION: EVENT CONFIGURATION"
    echo ""

    echo "$section" | awk '
    BEGIN {
        FS=":"
        col=0
    }

    {
        gsub(/\r/, "")

        # skip CLI + empty lines
        if ($0 ~ /::> event config show/) next
        if ($0 ~ /^[ \t]*$/) next

        key = $1
        val = substr($0, index($0, ":") + 1)

        # trim
        gsub(/^[ \t]+|[ \t]+$/, "", key)
        gsub(/^[ \t]+|[ \t]+$/, "", val)

        header[col] = key
        data[col]   = val

        if (length(key) > w[col]) w[col] = length(key)
        if (length(val) > w[col]) w[col] = length(val)

        col++
    }

    END {
        if (col == 0) exit

        # header row
        for (i=0; i<col; i++)
            printf "%-*s  ", w[i], header[i]
        printf "\n"

        # separator
        for (i=0; i<col; i++) {
            for (j=1; j<=w[i]; j++) printf "-"
            printf "  "
        }
        printf "\n"

        # value row
        for (i=0; i<col; i++)
            printf "%-*s  ", w[i], data[i]
        printf "\n"
    }'
}

process_http_proxy() {
    local section="$1"

    echo "SECTION: VSERVER HTTP PROXY"
    echo ""

    echo "$section" | awk '
    BEGIN { found=0 }

    {
        gsub(/\r/, "")

        # detect empty table
        if ($0 ~ /This table is currently empty/) {
            print "Status"
            print "---------"
            print "Not configured"
            found=1
            exit
        }
    }

    END {
        if (!found) {
            # fallback (in case future output changes)
            print "Status"
            print "---------"
            print "Configured"
        }
    }'
}

process_nfs() {
    local section="$1"

    echo "SECTION: NFS CONFIGURATION"
    echo ""

    echo "$section" | awk '
    BEGIN { FS=":" }

    {
        gsub(/\r/, "")

        if ($0 ~ /::> nfs show/) next
        if ($0 ~ /^[ \t]*$/) next
        if (index($0, ":") == 0) next

        key = $1
        val = substr($0, index($0, ":") + 1)

        gsub(/^[ \t]+|[ \t]+$/, "", key)
        gsub(/^[ \t]+|[ \t]+$/, "", val)

        # New block
        if (key == "Vserver") {
            if (curr_vserver != "") store_row()
            curr_vserver = val
            delete rowdata
            next
        }

        rowdata[key] = val

        # track headers (EXCLUDE Vserver)
        if (!(key in seen)) {
            headers[++hcount] = key
            seen[key] = 1
        }
    }

    function store_row() {
        rows[++rcount] = curr_vserver
        for (i=1; i<=hcount; i++) {
            k = headers[i]
            data[rcount,k] = rowdata[k]
        }
    }

    END {
        if (curr_vserver != "") store_row()
        if (rcount == 0) exit

        # --- WIDTH CALCULATION ---
        wv = length("Vserver")

        for (i=1; i<=hcount; i++) {
            k = headers[i]
            w[k] = length(k)
        }

        for (r=1; r<=rcount; r++) {
            if (length(rows[r]) > wv) wv = length(rows[r])

            for (i=1; i<=hcount; i++) {
                k = headers[i]
                if (length(data[r,k]) > w[k])
                    w[k] = length(data[r,k])
            }
        }

        # --- HEADER ---
        printf "%-*s  ", wv, "Vserver"
        for (i=1; i<=hcount; i++) {
            k = headers[i]
            printf "%-*s  ", w[k], k
        }
        printf "\n"

        # --- SEPARATOR ---
        for (i=1;i<=wv;i++) printf "-"; printf "  "
        for (i=1;i<=hcount;i++) {
            k=headers[i]
            for (j=1;j<=w[k];j++) printf "-"
            printf "  "
        }
        printf "\n"

        # --- ROWS ---
        for (r=1; r<=rcount; r++) {
            printf "%-*s  ", wv, rows[r]
            for (i=1; i<=hcount; i++) {
                k = headers[i]
                printf "%-*s  ", w[k], data[r,k]
            }
            printf "\n"
        }
    }'
}

process_cifs_options() {
    local section="$1"

    echo "SECTION: CIFS OPTIONS"
    echo ""

    echo "$section" | awk '
    BEGIN { FS=":" }

    {
        gsub(/\r/, "")

        if ($0 ~ /::> vserver cifs options show/) next
        if ($0 ~ /^[ \t]*$/) next
        if ($0 ~ /entries were displayed/) next
        if (index($0, ":") == 0) next

        key = $1
        val = substr($0, index($0, ":") + 1)

        gsub(/^[ \t]+|[ \t]+$/, "", key)
        gsub(/^[ \t]+|[ \t]+$/, "", val)

        # New block
        if (key == "Vserver") {
            if (curr_vserver != "") store_row()
            curr_vserver = val
            delete rowdata
            next
        }

        rowdata[key] = val

        # track headers (exclude Vserver)
        if (!(key in seen)) {
            headers[++hcount] = key
            seen[key] = 1
        }
    }

    function store_row() {
        rows[++rcount] = curr_vserver
        for (i=1; i<=hcount; i++) {
            k = headers[i]
            data[rcount,k] = rowdata[k]
        }
    }

    END {
        if (curr_vserver != "") store_row()
        if (rcount == 0) exit

        # --- WIDTH CALC ---
        wv = length("Vserver")

        for (i=1; i<=hcount; i++) {
            k = headers[i]
            w[k] = length(k)
        }

        for (r=1; r<=rcount; r++) {
            if (length(rows[r]) > wv) wv = length(rows[r])

            for (i=1; i<=hcount; i++) {
                k = headers[i]
                if (length(data[r,k]) > w[k])
                    w[k] = length(data[r,k])
            }
        }

        # --- HEADER ---
        printf "%-*s  ", wv, "Vserver"
        for (i=1; i<=hcount; i++) {
            k = headers[i]
            printf "%-*s  ", w[k], k
        }
        printf "\n"

        # --- SEPARATOR ---
        for (i=1;i<=wv;i++) printf "-"; printf "  "
        for (i=1;i<=hcount;i++) {
            k=headers[i]
            for (j=1;j<=w[k];j++) printf "-"
            printf "  "
        }
        printf "\n"

        # --- ROWS ---
        for (r=1; r<=rcount; r++) {
            printf "%-*s  ", wv, rows[r]
            for (i=1; i<=hcount; i++) {
                k = headers[i]
                printf "%-*s  ", w[k], data[r,k]
            }
            printf "\n"
        }
    }'
}

process_autosupport() {
    local section="$1"

    echo "SECTION: AUTOSUPPORT CONFIGURATION"
    echo ""

    echo "$section" | awk '
    BEGIN { FS=":" }

    {
        gsub(/\r/, "")

        if ($0 ~ /::> system node autosupport show/) next
        if ($0 ~ /^[ \t]*$/) next
        if ($0 ~ /entries were displayed/) next
        if (index($0, ":") == 0) next

        key = $1
        val = substr($0, index($0, ":") + 1)

        gsub(/^[ \t]+|[ \t]+$/, "", key)
        gsub(/^[ \t]+|[ \t]+$/, "", val)

        # New block
        if (key == "Node") {
            if (curr_node != "") store_row()
            curr_node = val
            delete rowdata
            next
        }

        # Filter + rename keys
        if (key == "Send AutoSupport Messages to Vendor Support") {
            key = "Autosupport call to Vendor"
        }
        else if (key == "Protocol to Contact Support") {
            key = "protocal"
        }
        else if (key == "Support Address") {
            key = "Support Address"
        } else {
            next
        }

        rowdata[key] = val

        if (!(key in seen)) {
            headers[++hcount] = key
            seen[key] = 1
        }
    }

    function store_row() {
        rows[++rcount] = curr_node
        for (i=1; i<=hcount; i++) {
            k = headers[i]
            data[rcount,k] = rowdata[k]
        }
    }

    END {
        if (curr_node != "") store_row()
        if (rcount == 0) exit

        wn = length("Node")
        for (i=1; i<=hcount; i++) {
            k = headers[i]
            w[k] = length(k)
        }

        for (r=1; r<=rcount; r++) {
            if (length(rows[r]) > wn) wn = length(rows[r])
            for (i=1; i<=hcount; i++) {
                k = headers[i]
                if (length(data[r,k]) > w[k])
                    w[k] = length(data[r,k])
            }
        }

        # header
        printf "%-*s  ", wn, "Node"
        for (i=1; i<=hcount; i++) {
            k=headers[i]
            printf "%-*s  ", w[k], k
        }
        printf "\n"

        # separator
        for (i=1;i<=wn;i++) printf "-"; printf "  "
        for (i=1;i<=hcount;i++) {
            k=headers[i]
            for (j=1;j<=w[k];j++) printf "-"
            printf "  "
        }
        printf "\n"

        # rows
        for (r=1; r<=rcount; r++) {
            printf "%-*s  ", wn, rows[r]
            for (i=1; i<=hcount; i++) {
                k = headers[i]
                printf "%-*s  ", w[k], data[r,k]
            }
            printf "\n"
        }
    }'
}

process_snmp() {
    local section="$1"

    echo "SECTION: SNMP CONFIGURATION"
    echo ""

    echo "$section" | awk '
    BEGIN {
        col=0
        current_key=""
    }

    {
        gsub(/\r/, "")

        if ($0 ~ /::> system snmp show/) next
        if ($0 ~ /^[ \t]*$/) next

        # Key line
        if ($0 ~ /:$/) {
            current_key = $0
            sub(/:$/, "", current_key)
            gsub(/^[ \t]+|[ \t]+$/, "", current_key)

            # initialize only if not traphosts
            if (current_key != "traphosts")
                value[current_key] = ""

            next
        }

        # Value lines
        if ($0 ~ /^[ \t]+/) {

            # completely ignore traphosts
            if (current_key == "traphosts")
                next

            val = $0
            gsub(/^[ \t]+|[ \t]+$/, "", val)

            if (value[current_key] == "")
                value[current_key] = val
            else
                value[current_key] = value[current_key] " | " val
        }
    }

    END {
        # build headers
        for (k in value) {
            header[col] = k
            data[col]   = value[k]

            if (length(k) > w[col]) w[col] = length(k)
            if (length(value[k]) > w[col]) w[col] = length(value[k])

            col++
        }

        if (col == 0) exit

        # header
        for (i=0; i<col; i++)
            printf "%-*s  ", w[i], header[i]
        printf "\n"

        # separator
        for (i=0; i<col; i++) {
            for (j=1; j<=w[i]; j++) printf "-"
            printf "  "
        }
        printf "\n"

        # row
        for (i=0; i<col; i++)
            printf "%-*s  ", w[i], data[i]
        printf "\n"
    }'
}

process_vscan() {
    local section="$1"

    echo "SECTION: VSCAN STATUS"
    echo ""

    echo "$section" | awk '
    BEGIN { row=0 }

    {
        gsub(/\r/, "")

        # skip CLI + footer + separator
        if ($0 ~ /::> vserver vscan show/) next
        if ($0 ~ /entries were displayed/) next
        if ($0 ~ /^[ \t-]+$/) next
        if ($0 ~ /^[ \t]*$/) next

        # header
        if ($0 ~ /^[ \t]*Vserver[ \t]+Vscan Status/) {
            gsub(/[ \t]+/, " ")
            split($0, header, " ")
            next
        }

        # data rows
        gsub(/[ \t]+/, " ")
        data[row] = $0
        row++
    }

    END {
        if (row == 0) exit

        # init widths from header
        w1 = length("Vserver")
        w2 = length("Vscan Status")

        # compute widths
        for (i=0; i<row; i++) {
            split(data[i], cols, " ")
            if (length(cols[1]) > w1) w1 = length(cols[1])
            if (length(cols[2]) > w2) w2 = length(cols[2])
        }

        # header
        printf "%-*s  %-*s\n", w1, "Vserver", w2, "Vscan Status"

        # separator
        for (i=1;i<=w1;i++) printf "-"; printf "  "
        for (i=1;i<=w2;i++) printf "-"
        printf "\n"

        # rows
        for (i=0; i<row; i++) {
            split(data[i], cols, " ")
            printf "%-*s  %-*s\n", w1, cols[1], w2, cols[2]
        }
    }'
}

# ---------------------------------------------------------
# BLOCK CLEANER
# ---------------------------------------------------------
awk -v sep="$SEP" -v outfile="$OUTPUT_FILE" '
BEGIN {
    block_started = 0
    writing = 0
    cli_count = 0
    skip_tail = 0
}

# Block boundary
/^=========================================================/{
    if (block_started == 1) {
        print "### BLOCK COMPLETED ###" >> outfile
        print "" >> outfile
    }

    block_started=1
    writing=0
    cli_count=0
    skip_tail=0
    ip=""
    fqdn=""
    next
}

# IP header
/^>>> PROCESSING NETAPP:/ {
    split($0,a,": ")
    ip=a[2]

    cmd="nslookup " ip " 2>/dev/null | awk \"/name =/ {print \\$4}\""
    cmd | getline fqdn
    close(cmd)
    gsub(/\.$/,"",fqdn)

    print "####  NETAPP  :: " fqdn " :: " ip " ####" >> outfile
    print "" >> outfile
    next
}

# Skip noise
/^Timestamp:/ { next }
/^Last login time:/ { next }

# Skip tail
/::> exit/ { skip_tail=1; next }

(skip_tail==1){
    if ($0 ~ /^Connection to .* closed/) skip_tail=0
    next
}

# Skip first two CLI prompts
/^[A-Za-z0-9_-]+::> / {
    cli_count++
    if (cli_count <= 2) next

    writing=1
    print $0 >> outfile
    next
}

(writing==0) { next }

{
    print $0 >> outfile
}

END {
    if (block_started == 1)
        print "### BLOCK COMPLETED ###" >> outfile
}
' "$TEMPFILE"

rm -f "$TEMPFILE"
# echo "Cleaned output created: $OUTPUT_FILE"

# ---------------------------------------------------------
# Load cleaned blocks into memory (BLOCKS array)
# ---------------------------------------------------------
declare -a BLOCKS
current_block=""

while IFS= read -r line; do
    if [[ "$line" == "### BLOCK COMPLETED ###" ]]; then
        BLOCKS+=("$current_block")
        current_block=""
        continue
    fi
    current_block+="$line"$'\n'

done < "$OUTPUT_FILE"

# echo "Total blocks: ${#BLOCKS[@]}"

# ---------------------------------------------------------
# Build final output (sections processed with helper)
# ---------------------------------------------------------
FINAL_OUT=$(mktemp)

for ((b=0; b<${#BLOCKS[@]}; b++)); do
    block="${BLOCKS[$b]}"

    declare -a SECTIONS=()
    section=""

    # Split block into sections
    while IFS= read -r line; do

        if [[ "$line" =~ ::\> ]]; then
            if [[ -n "$section" ]]; then
                SECTIONS+=("$section")
                section=""
            fi
        fi

        section+="$line"$'\n'

    done <<< "$block"

    [[ -n "$section" ]] && SECTIONS+=("$section")

    # Process each section
    for ((s=0; s<${#SECTIONS[@]}; s++)); do
        section="${SECTIONS[$s]}"

        # If helper exists → formatted output
        if [[ "$section" =~ "storage aggregate show -fields encrypt-with-aggr-key" ]]; then
            process_storage_aggr "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi
		
		if [[ "$section" =~ "vol show -fields is-encrypted,encrypt" ]]; then
			process_volume_encryption "$section" >> "$FINAL_OUT"
			echo "" >> "$FINAL_OUT"
			continue
		fi
		
		if [[ "$section" =~ "cluster log-forwarding show" ]]; then
			process_log_forwarding "$section" >> "$FINAL_OUT"
			echo "" >> "$FINAL_OUT"
			continue
		fi
		
		if [[ "$section" =~ "event notification destination show" ]]; then
			process_event_notification "$section" >> "$FINAL_OUT"
			echo "" >> "$FINAL_OUT"
			continue
		fi

        if [[ "$section" =~ "event config show" ]]; then
            process_event_config "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi

        if [[ "$section" =~ "vserver http-proxy show" ]]; then
            process_http_proxy "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi

        if [[ "$section" =~ "nfs show" ]]; then
            process_nfs "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi

        if [[ "$section" =~ "vserver cifs options show" ]]; then
            process_cifs_options "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi

        if [[ "$section" =~ "system node autosupport show" ]]; then
            process_autosupport "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi

        if [[ "$section" =~ "system snmp show" ]]; then
            process_snmp "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi

        if [[ "$section" =~ "vserver vscan show" ]]; then
            process_vscan "$section" >> "$FINAL_OUT"
            echo "" >> "$FINAL_OUT"
            continue
        fi

        # Otherwise → raw
        echo "$section" >> "$FINAL_OUT"
        echo "" >> "$FINAL_OUT"
    done

    echo "### BLOCK COMPLETED ###" >> "$FINAL_OUT"
    echo "" >> "$FINAL_OUT"
done

# Overwrite original cleaned output
mv "$FINAL_OUT" "$OUTPUT_FILE"

echo "CLEANED output saved: $OUTPUT_FILE"
exit 0
