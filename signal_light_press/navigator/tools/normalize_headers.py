from pathlib import Path

ROOTS = [
    "signal_light_press/codex",
    "signal_light_press/editions",
    "signal_light_press/contracts",
    "signal_light_press/manifests",
    "signal_light_press/registers",
]

REQUIRED_FIELDS = {
    "canon": [
        "Authority",
        "Classification",
        "Scope",
        "Status",
        "Amendment Rule",
        "Effective Date",
    ],
    "doctrine": [
        "Authority",
        "Classification",
        "Scope",
        "Status",
    ],
    "policy": [
        "Authority",
        "Classification",
        "Scope",
        "Status",
    ],
    "guide": [
        "Authority",
        "Classification",
        "Scope",
        "Status",
    ],
    "reference": [
        "Authority",
        "Classification",
        "Scope",
        "Status",
    ],
    "default": [
        "Authority",
        "Status",
    ],
}

DEFAULT_VALUES = {
    "Authority": "Signal Light Press",
    "Status": "DRAFT",
    "Scope": "TBD",
    "Classification": "TBD",
    "Amendment Rule": "TBD",
    "Effective Date": "TBD",
}

def classify(path: Path) -> str:
    p = str(path).replace("\\", "/")
    if "/canon/" in p:
        return "canon"
    if "/doctrine/" in p:
        return "doctrine"
    if "/policy/" in p:
        return "policy"
    if "/guides/" in p:
        return "guide"
    if "/references/" in p:
        return "reference"
    return "default"

def parse_header(lines):
    header = {}
    body_start = 0
    for i, line in enumerate(lines):
        if ":" in line:
            k, v = line.split(":", 1)
            header[k.strip()] = v.strip()
        else:
            body_start = i
            break
    return header, body_start

def normalize_file(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    header, body_start = parse_header(lines)

    doc_class = classify(path)
    required = REQUIRED_FIELDS[doc_class]

    missing = [f for f in required if f not in header]
    if not missing:
        return False

    new_header = header.copy()
    for f in missing:
        new_header[f] = DEFAULT_VALUES.get(f, "TBD")

    header_lines = [f"{k}: {v}" for k, v in new_header.items()]
    new_lines = header_lines + [""] + lines[body_start:]

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True

def run():
    modified = 0
    for root in ROOTS:
        for path in Path(root).rglob("*"):
            if path.suffix.lower() in [".md", ".txt", ".yaml", ".yml"]:
                if normalize_file(path):
                    modified += 1
    print(f"Normalization complete. Files modified: {modified}")

if __name__ == "__main__":
    run()
