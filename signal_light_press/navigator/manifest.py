from __future__ import annotations
from pathlib import Path
import json

class ManifestValidator:
    def __init__(self, root: Path):
        self.root = root
        self.expected_structure = {
            "kernel": ["wave.py", "codex.py", "exporter.py"],
            "command": ["daily_signal.py"],
            "data": ["audit.log"],
            "doctrine": ["silence_doctrine.yaml"],
            "renderers": ["posture_renderer.py"],
            "resonance": ["register.log", "entries/"],
            "snapshots": ["company_posture_snapshot.yaml"]
        }

    def validate(self) -> dict:
        issues = []
        actual_folders = {p.name for p in self.root.iterdir() if p.is_dir()}
        expected_folders = set(self.expected_structure.keys())
        missing = expected_folders - actual_folders
        extra = actual_folders - expected_folders
        if missing:
            issues.append(f"Missing folders: {', '.join(missing)}")
        if extra:
            issues.append(f"Extra folders: {', '.join(extra)}")
        for folder, expected in self.expected_structure.items():
            folder_path = self.root / folder
            if not folder_path.exists():
                continue
            actual_files = {p.name for p in folder_path.iterdir()}
            missing_files = set(expected) - actual_files
            if missing_files:
                issues.append(f"Missing in {folder}: {', '.join(missing_files)}")
        return {"valid": len(issues) == 0, "issues": issues}

    def print_report(self):
        result = self.validate()
        print("Manifest Validation Report")
        print("=" * 40)
        print("Valid:", result["valid"])
        if result["issues"]:
            print("Issues:")
            for issue in result["issues"]:
                print(f"- {issue}")
        else:
            print("No issues.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    validator = ManifestValidator(Path(args.root))
    validator.print_report()
