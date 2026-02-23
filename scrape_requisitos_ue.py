#!/usr/bin/env python3
"""Extrae requisitos de importación de Access2Markets por subpartida UE.

Uso rápido:
  python scrape_requisitos_ue.py --input subpartidas_ue.csv --output matriz_requisitos.csv --details requisitos_detalle.csv

Requiere:
  pip install playwright
  playwright install chromium
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from playwright.async_api import async_playwright


API_BASE = "https://trade.ec.europa.eu/access-to-markets/api/v2/document"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


@dataclass
class Requirement:
    code: str
    req_type: str
    label: str
    title: str
    content_text: str


def html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def load_codes(input_file: Path) -> list[str]:
    with input_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "subpartida_ue" not in reader.fieldnames:
            raise ValueError("El CSV de entrada debe tener la columna 'subpartida_ue'.")
        codes = [row["subpartida_ue"].strip() for row in reader if row.get("subpartida_ue", "").strip()]
    if not codes:
        raise ValueError("No se encontraron subpartidas en el archivo de entrada.")
    return codes


async def fetch_json(context, url: str):
    response = await context.request.get(url)
    response.raise_for_status()
    return await response.json()


async def fetch_text(context, url: str) -> str:
    response = await context.request.get(url)
    response.raise_for_status()
    return await response.text()


async def fetch_requirements_for_code(context, code: str, origin: str, destination: str, lang: str, include_content: bool) -> list[Requirement]:
    list_url = (
        f"{API_BASE}/list?destinationCountry={destination}&originCountry={origin}&product={code}&lang={lang}"
    )
    docs = await fetch_json(context, list_url)

    requirements: list[Requirement] = []
    for item in docs:
        doc_code = item.get("code", "")
        req_type = item.get("type", "")
        label = item.get("label", "")

        # overview no es requisito documental.
        if req_type == "o" or not doc_code:
            continue

        title_url = f"{API_BASE}/title?destinationCountry={destination}&code={doc_code}&locale={lang}"
        title = await fetch_text(context, title_url)

        content_text = ""
        if include_content:
            content_url = f"{API_BASE}/content?destinationCountry={destination}&code={doc_code}&locale={lang}&product={code}"
            content_html = await fetch_text(context, content_url)
            content_text = html_to_text(content_html)

        requirements.append(
            Requirement(
                code=doc_code,
                req_type=req_type,
                label=label or title,
                title=title,
                content_text=content_text,
            )
        )

    return requirements


def write_matrix(output_file: Path, rows: Iterable[dict[str, str]]) -> None:
    fieldnames = [
        "subpartida_ue",
        "origen",
        "destino",
        "requisitos_generales_count",
        "requisitos_especificos_count",
        "requisitos_generales",
        "requisitos_especificos",
    ]
    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_details(details_file: Path, rows: Iterable[dict[str, str]]) -> None:
    fieldnames = [
        "subpartida_ue",
        "origen",
        "destino",
        "tipo",
        "codigo_requisito",
        "etiqueta",
        "titulo",
        "detalle_texto",
    ]
    with details_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def run(args: argparse.Namespace) -> None:
    codes = load_codes(Path(args.input))

    matrix_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for idx, code in enumerate(codes, start=1):
            print(f"[{idx}/{len(codes)}] Consultando subpartida {code}...")
            requirements = await fetch_requirements_for_code(
                context=context,
                code=code,
                origin=args.origin,
                destination=args.destination,
                lang=args.lang,
                include_content=args.include_content,
            )

            generales = [r.title for r in requirements if r.req_type == "g"]
            especificos = [r.title for r in requirements if r.req_type == "s"]

            matrix_rows.append(
                {
                    "subpartida_ue": code,
                    "origen": args.origin,
                    "destino": args.destination,
                    "requisitos_generales_count": str(len(generales)),
                    "requisitos_especificos_count": str(len(especificos)),
                    "requisitos_generales": " | ".join(generales),
                    "requisitos_especificos": " | ".join(especificos),
                }
            )

            for req in requirements:
                detail_rows.append(
                    {
                        "subpartida_ue": code,
                        "origen": args.origin,
                        "destino": args.destination,
                        "tipo": "general" if req.req_type == "g" else "especifico",
                        "codigo_requisito": req.code,
                        "etiqueta": req.label,
                        "titulo": req.title,
                        "detalle_texto": req.content_text,
                    }
                )

        await browser.close()

    write_matrix(Path(args.output), matrix_rows)
    write_details(Path(args.details), detail_rows)

    print(f"\nOK: matriz guardada en {args.output}")
    print(f"OK: detalle guardado en {args.details}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scraping de requisitos de importación UE por subpartida.")
    parser.add_argument("--input", default="subpartidas_ue.csv", help="CSV de entrada con columna subpartida_ue")
    parser.add_argument("--output", default="matriz_requisitos.csv", help="CSV de salida resumido")
    parser.add_argument("--details", default="requisitos_detalle.csv", help="CSV de salida detallado")
    parser.add_argument("--origin", default="CO", help="País de origen (ISO2), por defecto CO")
    parser.add_argument("--destination", default="FR", help="País destino (ISO2), por defecto FR")
    parser.add_argument("--lang", default="EN", help="Idioma API (EN/ES/FR...), por defecto EN")
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Si se indica, consulta y limpia el contenido HTML de cada requisito (más lento).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
