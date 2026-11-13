"""Gera sinais candidatos Samsung com a biblioteca oficial, sem acionar hardware."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path, help="Checkout de IRremoteESP8266 v2.9.0")
    args = parser.parse_args()
    library = args.library.resolve()
    if "version=2.9.0" not in (library / "library.properties").read_text().splitlines():
        parser.error("Use o código oficial da versão 2.9.0 para reproduzir estes sinais")
    here = Path(__file__).resolve().parent
    sources = [
        "ir_Samsung.cpp",
        "IRsend.cpp",
        "IRrecv.cpp",
        "IRutils.cpp",
        "IRtimer.cpp",
        "IRtext.cpp",
        "IRac.cpp",
    ]
    compiler = next((path for name in ("g++", "clang++") if (path := shutil.which(name))), None)
    command = [compiler] if compiler else [sys.executable, "-m", "ziglang", "c++"]
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / ("export_samsung.exe" if os.name == "nt" else "export_samsung")
        subprocess.run(
            [
                *command,
                "-std=c++17",
                "-DUNIT_TEST",
                "-D_IR_ENABLE_DEFAULT_=false",
                "-DSEND_SAMSUNG_AC=true",
                "-DDECODE_SAMSUNG_AC=true",
                f"-I{library / 'src'}",
                f"-I{library / 'test'}",
                str(here / "export_samsung.cpp"),
                *(str(library / "src" / name) for name in sources),
                "-o",
                str(binary),
            ],
            check=True,
        )
        signals = json.loads(subprocess.check_output([str(binary)], text=True))
    (here / "signals.samsung-candidate.json").write_text(
        json.dumps(signals, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    lines = [
        "Filetype: IR signals file",
        "Version: 1",
        "#",
        "# CANDIDATO SAMSUNG_AC - validar no aparelho real",
        "#",
    ]
    for name, signal in signals.items():
        lines.extend(
            [
                f"name: {name}",
                "type: raw",
                f"frequency: {signal['frequency']}",
                f"duty_cycle: {signal['duty_cycle']:.6f}",
                "data: " + " ".join(map(str, signal["pattern"])),
                "#",
            ]
        )
    (here / "samsung-candidate.ir").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {len(signals)} estados candidatos gerados e decodificados, com checksum validado")


if __name__ == "__main__":
    main()
