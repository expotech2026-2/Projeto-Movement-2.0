"""Converte a tabela PBE de condicionadores de ar do Inmetro (PDF) no catálogo CSV do Movement."""

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path

SOURCE_PAGE = (
    "https://www.gov.br/inmetro/pt-br/assuntos/regulamentacao/avaliacao-da-conformidade/"
    "programa-brasileiro-de-etiquetagem/tabelas-de-eficiencia-energetica/condicionadores-de-ar"
)
KINDS = {
    "Split Hi-Wall": "split",
    "Split Cassete": "cassete",
    "Split Piso-teto": "piso_teto",
    "Janela": "janela",
}
FUNCTIONS = {"Frio": "frio", "Quente/Frio": "quente_frio"}
FIELDS = [
    "brand",
    "model",
    "kind",
    "indoor_unit",
    "outdoor_unit",
    "function",
    "voltage",
    "inverter",
    "refrigerant",
    "capacity_btu",
    "idrs",
    "annual_kwh",
    "energy_class",
    "registration",
    "corrected",
]


def join_wrapped(cell: str) -> str:
    # Quebras após hífen colado pertencem ao mesmo código; as demais viram espaço.
    parts = [part.strip() for part in cell.split("\n")]
    text = parts[0]
    for part in parts[1:]:
        glued = text.endswith("-") and len(text) > 1 and text[-2] != " "
        text = f"{text}{part}" if glued else f"{text} {part}"
    return re.sub(r"\s+", " ", text).strip()


def voltage(cell: str) -> str:
    text = cell.replace("\n", "")
    number = re.match(r"\s*(\d+(?:-\d+)?)", text)
    if not number:
        raise ValueError(f"Tensão não reconhecida: {cell!r}")
    if "trif" in text:
        phase = "trifásico"
    elif "bif" in text:
        phase = "monofásico/bifásico"
    else:
        phase = "monofásico"
    return f"{number.group(1).replace('-', '/')} V ({phase})"


def capacity(btu_cell: str, watts_cell: str) -> tuple[int, bool]:
    btu = float(btu_cell)
    watts = float(watts_cell or 0)
    if btu < 1000 and watts:
        # Valor publicado sem os milhares; recalculado pela capacidade em watts.
        return round(watts * 3.412 / 1000) * 1000, True
    if watts and abs(watts / btu - 3.412) < 0.15:
        # Colunas BTU/h e W publicadas invertidas.
        return round(watts), True
    return round(btu), False


def convert(rows: list[list[str]]) -> list[dict]:
    catalog = {}
    for cells in rows:
        btu, corrected = capacity(cells[12], cells[13])
        item = {
            "brand": join_wrapped(cells[0]).upper(),
            "model": join_wrapped(cells[1]),
            "kind": KINDS[join_wrapped(cells[3])],
            "indoor_unit": join_wrapped(cells[4]),
            "outdoor_unit": join_wrapped(cells[5]),
            "function": FUNCTIONS[join_wrapped(cells[6])],
            "voltage": voltage(cells[7]),
            "inverter": "1" if "Vari" in cells[8] else "0",
            "refrigerant": join_wrapped(cells[10]) or join_wrapped(cells[9]),
            "capacity_btu": str(btu),
            "idrs": cells[23].strip(),
            "annual_kwh": cells[24].strip(),
            "energy_class": cells[25].strip(),
            "registration": cells[27].strip(),
            "corrected": "1" if corrected else "0",
        }
        catalog[tuple(item.values())] = item
    return sorted(
        catalog.values(),
        key=lambda item: (item["brand"], item["kind"], int(item["capacity_btu"]), item["model"]),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Tabela do Inmetro em PDF, com 28 colunas")
    parser.add_argument("csv", type=Path, help="Arquivo CSV de saída")
    args = parser.parse_args()
    try:
        import pdfplumber
    except ImportError:
        parser.exit(1, "Instale o pdfplumber para converter a tabela: pip install pdfplumber\n")
    rows, updated_at = [], None
    with pdfplumber.open(args.pdf) as pdf:
        found = re.search(r"Atualiza\S*\s*:\s*(\d{2}/\d{2}/\d{4})", pdf.pages[0].extract_text())
        if found:
            updated_at = datetime.strptime(found.group(1), "%d/%m/%Y").date().isoformat()
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = [(cell or "").strip() for cell in row]
                    if len(cells) == 28 and cells[0] != "Marca":
                        rows.append(cells)
    if not rows:
        parser.exit(1, "Nenhuma linha de 28 colunas encontrada; confira o arquivo do Inmetro.\n")
    catalog = convert(rows)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(catalog)
    metadata = {
        "source": SOURCE_PAGE,
        "updated_at": updated_at,
        "models": len(catalog),
        "brands": len({item["brand"] for item in catalog}),
        "corrected": sum(item["corrected"] == "1" for item in catalog),
    }
    args.csv.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
