"""Extrai a lógica da porta do sketch.ino, compila com teste_porta.cpp e roda os cenários."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKETCH = HERE.parents[1] / "firmware" / "climacontrol" / "sketch.ino"


def extract(text: str, start: str, end: str) -> str:
    """Trecho do firmware entre a linha que começa com start e a linha igual a end, inclusive."""
    lines = text.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith(start))
    last = next(i for i in range(first, len(lines)) if lines[i] == end)
    return "\n".join(lines[first : last + 1]) + "\n"


def compiler() -> list[str]:
    if os.environ.get("CXX"):
        return [os.environ["CXX"]]
    for name in ("g++", "clang++"):
        if shutil.which(name):
            return [name]
    return [sys.executable, "-m", "ziglang", "c++"]  # pip install ziglang


def main() -> int:
    text = SKETCH.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        build = Path(tmp)
        (build / "porta_globais.inc").write_text(
            extract(text, "enum EstadoPorta", "unsigned long desdeA = 0, desdeB = 0;"),
            encoding="utf-8",
        )
        (build / "porta_funcoes.inc").write_text(
            extract(text, "// Aceita a leitura do pino", "  return 0;") + "}\n", encoding="utf-8"
        )
        binary = build / "teste_porta"
        command = [*compiler(), "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{build}"]
        subprocess.run([*command, str(HERE / "teste_porta.cpp"), "-o", str(binary)], check=True)
        return subprocess.run([str(binary)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
