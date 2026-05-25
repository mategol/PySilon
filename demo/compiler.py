import json
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CFG_DIR = ROOT / "cfg"
OUTPUT_DIR = ROOT / "output"
BUILD_DIR = ROOT / "build"


class Compiler:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.cfg_dir = self.root / "cfg"
        self.output_dir = self.root / "output"
        self.build_dir = self.root / "build"

    def load_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def extract_block(self, path, block_name):
        lines = (self.root / path).read_text(encoding="utf-8").splitlines(keepends=True)
        start_marker = f"#<{block_name}>"
        end_marker = f"#</{block_name}>"
        inside = False
        extracted = []

        for line in lines:
            stripped = line.strip()
            if stripped == start_marker:
                inside = True
                continue
            if stripped == end_marker:
                break
            if inside:
                extracted.append(line)

        return extracted

    def collect_sections(self, config, compiler_config):
        sections = {
            "feature_imports": [],
            "handler_defs": [],
            "handler_registry": [],
        }

        enabled_features = config.get("features", {})
        for section_name, entries in compiler_config.items():
            for feature_name, feature_path, block_name in entries:
                if not enabled_features.get(feature_name, False):
                    continue
                sections[section_name].extend(self.extract_block(feature_path, block_name))

        sections["feature_imports"] = self.dedupe_lines(sections["feature_imports"])
        return sections

    def dedupe_lines(self, lines):
        seen = set()
        deduped = []
        for line in lines:
            if line in seen:
                continue
            seen.add(line)
            deduped.append(line)
        return deduped

    def marker_name_and_indent(self, stripped_line):
        marker = stripped_line[2:]
        name, _, rest = marker.partition(".indentation=")
        return name, int(rest or "0")

    def compile_source(self):
        config = self.load_json(self.cfg_dir / "configuration.json")
        compiler_config = self.load_json(self.cfg_dir / "compiler_configuration.json")
        sections = self.collect_sections(config, compiler_config)

        source_template = (self.root / "source.py").read_text(encoding="utf-8").splitlines(keepends=True)
        rendered = []

        for line in source_template:
            stripped = line.strip()
            if stripped.startswith("#!"):
                name, indentation = self.marker_name_and_indent(stripped)
                indent = "    " * indentation
                for section_line in sections.get(name, []):
                    rendered.append(indent + section_line)
                continue

            rendered.append(line.replace("__CONFIG_JSON__", json.dumps(config, indent=4)))

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_source = self.output_dir / "source.py"
        output_source.write_text("".join(rendered), encoding="utf-8")
        return output_source

    def build_exe(self, output_source):
        config = self.load_json(self.cfg_dir / "configuration.json")
        executable_name = config.get("executable_name") or "client"

        if shutil.which("pyinstaller") is None and importlib.util.find_spec("PyInstaller") is None:
            return {
                "ok": False,
                "reason": "PyInstaller is not installed. The Python client was generated, but no exe was built.",
                "source": str(output_source),
            }

        self.build_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--clean",
            "--name",
            executable_name,
            "--distpath",
            str(self.output_dir),
            "--workpath",
            str(self.build_dir / "pyinstaller"),
            "--specpath",
            str(self.build_dir),
            str(output_source),
        ]
        subprocess.run(command, cwd=self.root, check=True)

        return {
            "ok": True,
            "exe": str(self.output_dir / f"{executable_name}.exe"),
            "source": str(output_source),
        }

    def build(self, build_exe=True):
        output_source = self.compile_source()
        if not build_exe:
            return {"ok": True, "source": str(output_source)}
        return self.build_exe(output_source)


def build(build_exe=True):
    return Compiler().build(build_exe=build_exe)


if __name__ == "__main__":
    result = build(build_exe="--no-exe" not in sys.argv)
    print(json.dumps(result, indent=2))
