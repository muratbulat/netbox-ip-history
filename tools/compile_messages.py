"""
Python-native PO to MO compiler that does not require GNU gettext binaries.
"""
import ast
import os
import struct
import sys


def parse_po(po_filepath):
    """Parse a PO file and return a dictionary of msgid -> msgstr including the header."""
    messages = {}
    current_id_lines = []
    current_str_lines = []
    state = None  # 'msgid' or 'msgstr'

    with open(po_filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    def decode_po_string(lines_list):
        # Concatenate raw quoted strings and parse Python/C escapes safely
        combined = "".join(lines_list).strip()
        if not combined:
            return ""
        # Match all "quoted" strings
        res = []
        for line in lines_list:
            line = line.strip()
            if line.startswith('"') and line.endswith('"'):
                try:
                    res.append(ast.literal_eval(line))
                except Exception:
                    res.append(line[1:-1].replace('\\"', '"').replace('\\n', '\n'))
        return "".join(res)

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("msgid "):
            if state == "msgstr":
                msg_id = decode_po_string(current_id_lines)
                msg_str = decode_po_string(current_str_lines)
                messages[msg_id] = msg_str
                current_id_lines = []
                current_str_lines = []

            state = "msgid"
            current_id_lines.append(stripped[6:].strip())
        elif stripped.startswith("msgstr "):
            state = "msgstr"
            current_str_lines.append(stripped[7:].strip())
        elif stripped.startswith('"') and stripped.endswith('"'):
            if state == "msgid":
                current_id_lines.append(stripped)
            elif state == "msgstr":
                current_str_lines.append(stripped)

    if state == "msgstr":
        msg_id = decode_po_string(current_id_lines)
        msg_str = decode_po_string(current_str_lines)
        messages[msg_id] = msg_str

    return messages


def generate_mo(messages):
    """Generate binary MO file content from a messages dictionary."""
    # Ensure header is included
    if "" not in messages:
        messages[""] = "Content-Type: text/plain; charset=UTF-8\n"

    # Sort keys for binary search in gettext (msgid "" must come first)
    keys = sorted(messages.keys())

    offsets = []
    ids = b""
    strs = b""

    for k in keys:
        v = messages[k]
        k_bytes = k.encode("utf-8") + b"\x00"
        v_bytes = v.encode("utf-8") + b"\x00"
        offsets.append((len(ids), len(k_bytes) - 1, len(strs), len(v_bytes) - 1))
        ids += k_bytes
        strs += v_bytes

    count = len(keys)
    keystart = 7 * 4 + count * 8 * 2
    valuestart = keystart + len(ids)

    keyoffsets = []
    valueoffsets = []
    for o1, l1, o2, l2 in offsets:
        keyoffsets.append((l1, o1 + keystart))
        valueoffsets.append((l2, o2 + valuestart))

    header = struct.pack(
        "Iiiiiii",
        0x950412DE,  # Magic number
        0,           # Format version
        count,       # Number of strings
        7 * 4,       # Offset of table with original strings
        7 * 4 + count * 8,  # Offset of table with translation strings
        0,           # Size of hashing table
        0,           # Offset of hashing table
    )

    keytable = b"".join(struct.pack("ii", l, o) for l, o in keyoffsets)
    valuetable = b"".join(struct.pack("ii", l, o) for l, o in valueoffsets)

    return header + keytable + valuetable + ids + strs


def compile_po_to_mo(po_path, mo_path=None):
    if mo_path is None:
        mo_path = os.path.splitext(po_path)[0] + ".mo"
    messages = parse_po(po_path)
    mo_bytes = generate_mo(messages)
    os.makedirs(os.path.dirname(mo_path), exist_ok=True)
    with open(mo_path, "wb") as f:
        f.write(mo_bytes)
    return len(messages)


def compile_all_locales(locale_dir):
    compiled = 0
    for root, _, files in os.walk(locale_dir):
        for f in files:
            if f.endswith(".po"):
                po_path = os.path.join(root, f)
                mo_path = os.path.join(root, os.path.splitext(f)[0] + ".mo")
                count = compile_po_to_mo(po_path, mo_path)
                print(f"Compiled {po_path} -> {mo_path} ({count} messages)")
                compiled += 1
    return compiled


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    loc_dir = os.path.join(base, "netbox_ip_history", "locale")
    if len(sys.argv) > 1:
        loc_dir = sys.argv[1]
    count = compile_all_locales(loc_dir)
    print(f"Finished compiling {count} locale catalog(s).")
