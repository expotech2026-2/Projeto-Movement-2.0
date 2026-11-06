"""Gera as variáveis do Azure App Service a partir de backend/.env.supabase sem exibir valores."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Gerar variáveis do App Service (edição avançada)")
    parser.add_argument(
        "site", help="Endereço publicado, por exemplo https://movement.azurewebsites.net"
    )
    parser.add_argument("--source", default=".env.supabase")
    parser.add_argument("--target", default=".env.azure.json")
    args = parser.parse_args()
    site = urlparse(args.site)
    if site.scheme != "https" or not site.hostname:
        parser.error("Informe o endereço completo com https://")
    values = {key: value for key, value in dotenv_values(BACKEND / args.source).items() if value}
    if "MOVEMENT_DATABASE_URL" not in values:
        parser.error(f"backend/{args.source} não contém MOVEMENT_DATABASE_URL")
    values["MOVEMENT_CORS_ORIGINS"] = json.dumps([f"https://{site.hostname}"])
    values["WEBSITES_PORT"] = "8000"
    settings = [
        {"name": name, "value": value, "slotSetting": False}
        for name, value in sorted(values.items())
    ]
    (BACKEND / args.target).write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(
        f"{len(settings)} variáveis gravadas em backend/{args.target}: {', '.join(sorted(values))}"
    )


if __name__ == "__main__":
    main()
