"""Extrai do sketch.ino a lógica da porta e dos comandos IR, compila com os testes e os roda."""

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


def run_test(build: Path, name: str, includes: dict[str, str]) -> int:
    for filename, code in includes.items():
        (build / filename).write_text(code, encoding="utf-8")
    binary = build / name
    command = [*compiler(), "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{build}"]
    subprocess.run([*command, str(HERE / f"{name}.cpp"), "-o", str(binary)], check=True)
    return subprocess.run([str(binary)]).returncode


def main() -> int:
    text = SKETCH.read_text(encoding="utf-8")
    porta = {
        "porta_globais.inc": extract(
            text, "enum EstadoPorta", "unsigned long desdeA = 0, desdeB = 0;"
        ),
        "porta_funcoes.inc": extract(text, "// Aceita a leitura do pino", "  return 0;") + "}\n",
    }
    ir = {
        "ir_globais.inc": extract(
            text, "// ── Pulsos IR (LED)", "int  alvoEnviado   = (int)TEMP_CONFORTO_BASE;"
        ),
        "ir_funcoes.inc": extract(
            text,
            "// Regra do circuito combinacional",
            "  return subir ? PULSO_SUBIR : PULSO_BAIXAR;",
        )
        + "}\n",
    }
    with tempfile.TemporaryDirectory() as tmp:
        build = Path(tmp)
        return run_test(build, "teste_porta", porta) or run_test(build, "teste_ir", ir)


if __name__ == "__main__":
    raise SystemExit(main())
