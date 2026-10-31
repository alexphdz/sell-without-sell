"""Table extraction from CSV and XML sources."""

from __future__ import annotations

import csv
import io
from typing import Any

from lxml import etree

from kipu_pay.core.logging import get_logger
from kipu_pay.normalization.models import ExtractionContext, TableRecord

logger = get_logger(__name__)


class TableExtractor:
    """Extract canonical table records from CSV and XML resources."""

    def extract_csv(
        self,
        snapshot_id: str,
        resource_id: str,
        table_name: str,
        raw_bytes: bytes,
        encoding: str = "utf-8",
        delimiter: str = ",",
        primary_key: str = "id",
        id_prefix: str | None = None,
    ) -> tuple[list[TableRecord], list[ExtractionContext], list[dict[str, Any]]]:
        """Extract table records from CSV.

        Returns (records, contexts, errors).
        """
        records: list[TableRecord] = []
        contexts: list[ExtractionContext] = []
        errors: list[dict[str, Any]] = []

        try:
            text = raw_bytes.decode(encoding, errors="replace")
        except Exception as exc:
            errors.append({
                "resource_id": resource_id,
                "stage": "decode",
                "error": str(exc),
            })
            return records, contexts, errors

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        headers = reader.fieldnames or []

        if not headers:
            errors.append({
                "resource_id": resource_id,
                "stage": "parse",
                "error": "no_csv_headers",
            })
            return records, contexts, errors

        seen_ids: set[str] = set()

        for position, row in enumerate(reader):
            try:
                pk_val = row.get(primary_key, "").strip() if primary_key in row else ""
                if not pk_val:
                    errors.append({
                        "resource_id": resource_id,
                        "stage": "extract_row",
                        "position": position,
                        "error": "missing_primary_key",
                    })
                    continue

                record_id = f"{table_name}:{pk_val}" if id_prefix is None else f"{id_prefix}:{pk_val}"
                if record_id in seen_ids:
                    errors.append({
                        "resource_id": resource_id,
                        "stage": "extract_row",
                        "position": position,
                        "error": f"duplicate_primary_key:{record_id}",
                    })
                    continue
                seen_ids.add(record_id)

                # Preserve all values as strings (or None for empty)
                columns: dict[str, str | None] = {}
                for key, val in row.items():
                    if key is None:
                        continue
                    columns[key] = val if val is not None and val.strip() != "" else None

                record = TableRecord(
                    id=record_id,
                    table=table_name,
                    columns=columns,
                )
                records.append(record)

                context = ExtractionContext(
                    snapshot_id=snapshot_id,
                    source_resource_id=resource_id,
                    source_format="csv",
                    source_record_position=position,
                )
                contexts.append(context)
            except Exception as exc:
                errors.append({
                    "resource_id": resource_id,
                    "stage": "extract_row",
                    "position": position,
                    "error": str(exc),
                })

        return records, contexts, errors

    def extract_xml(
        self,
        snapshot_id: str,
        resource_id: str,
        table_name: str,
        raw_bytes: bytes,
        row_tag: str,
        primary_key_attr: str | None = None,
        primary_key_child: str | None = None,
        id_prefix: str | None = None,
    ) -> tuple[list[TableRecord], list[ExtractionContext], list[dict[str, Any]]]:
        """Extract table records from XML.

        Returns (records, contexts, errors).
        """
        records: list[TableRecord] = []
        contexts: list[ExtractionContext] = []
        errors: list[dict[str, Any]] = []

        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        try:
            root = etree.fromstring(raw_bytes, parser=parser)
        except etree.XMLSyntaxError as exc:
            errors.append({
                "resource_id": resource_id,
                "stage": "parse",
                "error": str(exc),
            })
            return records, contexts, errors

        seen_ids: set[str] = set()

        for position, elem in enumerate(root.findall(f".//{row_tag}")):
            try:
                # Determine primary key
                pk_val = ""
                if primary_key_attr:
                    pk_val = elem.get(primary_key_attr, "").strip()
                if not pk_val and primary_key_child:
                    child = elem.find(primary_key_child)
                    if child is not None and child.text:
                        pk_val = child.text.strip()

                if not pk_val:
                    errors.append({
                        "resource_id": resource_id,
                        "stage": "extract_row",
                        "position": position,
                        "error": "missing_primary_key",
                    })
                    continue

                record_id = f"{table_name}:{pk_val}" if id_prefix is None else f"{id_prefix}:{pk_val}"
                if record_id in seen_ids:
                    errors.append({
                        "resource_id": resource_id,
                        "stage": "extract_row",
                        "position": position,
                        "error": f"duplicate_primary_key:{record_id}",
                    })
                    continue
                seen_ids.add(record_id)

                # Build columns from attributes and child elements
                columns: dict[str, str | None] = {}

                # Attributes
                for attr_name, attr_val in elem.attrib.items():
                    columns[attr_name] = attr_val if attr_val.strip() != "" else None

                # Child elements
                for child in elem:
                    tag = child.tag
                    text = child.text.strip() if child.text else None
                    # Handle duplicate tags by appending
                    if tag in columns and columns[tag] is not None:
                        if text:
                            columns[tag] = columns[tag] + "\n" + text
                    else:
                        columns[tag] = text if text else None

                record = TableRecord(
                    id=record_id,
                    table=table_name,
                    columns=columns,
                )
                records.append(record)

                context = ExtractionContext(
                    snapshot_id=snapshot_id,
                    source_resource_id=resource_id,
                    source_format="xml",
                    source_record_position=position,
                )
                contexts.append(context)
            except Exception as exc:
                errors.append({
                    "resource_id": resource_id,
                    "stage": "extract_row",
                    "position": position,
                    "error": str(exc),
                })

        return records, contexts, errors
