import re
import tempfile
import unicodedata
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException

APP_DIRECTORY = Path(__file__).resolve().parent
STORE_CATALOG_FILENAME = "base de lojas de PSP.xlsx"

STORE_FIELDS = {
    "people": ("people",),
    "name": ("lojas",),
    "address": ("endereço",),
    "district": ("bairro",),
    "state": ("estado", "estado/uf", "uf"),
    "email": ("e-mail da loja", "email da loja", "e-mail", "email"),
}
STORE_FIELD_LABELS = {
    "people": "people",
    "name": "lojas",
    "address": "endereço",
    "district": "bairro",
    "state": "estado (ou Estado/UF)",
    "email": "e-mail da loja",
}


def normalize_header(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", normalized.casefold()).split())


def read_store_catalog(file_content):
    try:
        catalog = pd.read_excel(
            BytesIO(file_content),
            dtype=str,
            engine="openpyxl",
        ).fillna("")
    except (ImportError, InvalidFileException, OSError, ValueError, zipfile.BadZipFile) as error:
        raise ValueError("Não foi possível ler a planilha .xlsx enviada.") from error

    headers = {}
    for column in catalog.columns:
        headers.setdefault(normalize_header(column), column)

    columns = {}
    for field, aliases in STORE_FIELDS.items():
        for alias in aliases:
            column = headers.get(normalize_header(alias))
            if column is not None:
                columns[field] = column
                break

    missing_fields = [
        STORE_FIELD_LABELS[field]
        for field in STORE_FIELDS
        if field not in columns
    ]
    if missing_fields:
        raise ValueError(
            "A planilha precisa conter os cabeçalhos da Linha 1: "
            + ", ".join(missing_fields)
            + "."
        )

    return catalog, columns


def find_store(catalog, columns, unit_code):
    normalized_code = str(unit_code).strip().casefold()
    if not normalized_code:
        return None

    codes = catalog[columns["people"]].astype(str).str.strip().str.casefold()
    matches = catalog.loc[codes == normalized_code]
    if matches.empty:
        return None

    row = matches.iloc[0]
    return {
        field: str(row[column]).strip()
        for field, column in columns.items()
        if field != "people"
    }


def find_store_catalog_path():
    personal_directory = (
        Path.home() / "Documents" / "Pessoais" / "Projeto DPSP"
    )
    candidates = (
        APP_DIRECTORY / STORE_CATALOG_FILENAME,
        APP_DIRECTORY / "Base de lojas DPSP.xlsx",
        personal_directory / STORE_CATALOG_FILENAME,
        personal_directory / "Base de lojas DPSP.xlsx",
    )
    return next((path for path in candidates if path.is_file()), None)


def save_store_catalog(file_content):
    read_store_catalog(file_content)
    destination = APP_DIRECTORY / STORE_CATALOG_FILENAME
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=APP_DIRECTORY,
            prefix=".store-catalog-",
            suffix=".xlsx",
            delete=False,
        ) as temporary_file:
            temporary_file.write(file_content)
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(destination)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
