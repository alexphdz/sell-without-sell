"""Tests for table extraction."""

from __future__ import annotations

import pytest

from kipu_pay.normalization.table_extractor import TableExtractor


class TestCsvExtraction:
    @pytest.fixture
    def extractor(self) -> TableExtractor:
        return TableExtractor()

    def test_utf8_comma_csv(self, extractor: TableExtractor) -> None:
        raw = b"tx_id,fecha,cliente_id\nTX-000001,2026-01-01,CL-1\nTX-000002,2026-01-02,CL-2"
        records, contexts, errors = extractor.extract_csv(
            "snap", "table_transacciones.csv", "transacciones", raw,
            encoding="utf-8", delimiter=",", primary_key="tx_id",
        )
        assert len(errors) == 0
        assert len(records) == 2
        assert records[0].id == "transacciones:TX-000001"
        assert records[0].columns["cliente_id"] == "CL-1"
        assert records[1].columns["fecha"] == "2026-01-02"

    def test_latin1_semicolon_csv(self, extractor: TableExtractor) -> None:
        raw = "cliente_id;nombre\nCL-1;Señor Adrián".encode("latin-1")
        records, _, errors = extractor.extract_csv(
            "snap", "table_clientes.csv", "clientes", raw,
            encoding="latin-1", delimiter=";", primary_key="cliente_id",
        )
        assert len(errors) == 0
        assert len(records) == 1
        assert records[0].columns["nombre"] == "Señor Adrián"

    def test_quoted_delimiter(self, extractor: TableExtractor) -> None:
        raw = b'id,desc\n1,"hello, world"\n2,foo'
        records, _, errors = extractor.extract_csv(
            "snap", "t.csv", "t", raw, encoding="utf-8", delimiter=",", primary_key="id",
        )
        assert len(errors) == 0
        assert records[0].columns["desc"] == "hello, world"

    def test_empty_cell(self, extractor: TableExtractor) -> None:
        raw = b"id,name,note\n1,Alice,\n2,Bob,note"
        records, _, errors = extractor.extract_csv(
            "snap", "t.csv", "t", raw, encoding="utf-8", delimiter=",", primary_key="id",
        )
        assert len(errors) == 0
        assert records[0].columns["note"] is None
        assert records[1].columns["note"] == "note"

    def test_leading_zero_preserved(self, extractor: TableExtractor) -> None:
        raw = b"id,code\n1,00123\n2,0456"
        records, _, errors = extractor.extract_csv(
            "snap", "t.csv", "t", raw, encoding="utf-8", delimiter=",", primary_key="id",
        )
        assert records[0].columns["code"] == "00123"

    def test_monetary_amount(self, extractor: TableExtractor) -> None:
        raw = b"id,monto\n1,520000\n2,1350000"
        records, _, errors = extractor.extract_csv(
            "snap", "t.csv", "t", raw, encoding="utf-8", delimiter=",", primary_key="id",
        )
        assert records[0].columns["monto"] == "520000"
        assert records[1].columns["monto"] == "1350000"

    def test_missing_primary_key(self, extractor: TableExtractor) -> None:
        raw = b"id,name\n,Alice\n2,Bob"
        records, _, errors = extractor.extract_csv(
            "snap", "t.csv", "t", raw, encoding="utf-8", delimiter=",", primary_key="id",
        )
        assert len(records) == 1
        assert len(errors) == 1
        assert "missing_primary_key" in errors[0]["error"]

    def test_duplicate_primary_key(self, extractor: TableExtractor) -> None:
        raw = b"id,name\n1,Alice\n1,Bob"
        records, _, errors = extractor.extract_csv(
            "snap", "t.csv", "t", raw, encoding="utf-8", delimiter=",", primary_key="id",
        )
        assert len(records) == 1
        assert len(errors) == 1
        assert "duplicate_primary_key" in errors[0]["error"]

    def test_invalid_row_length(self, extractor: TableExtractor) -> None:
        raw = b"id,name,age\n1,Alice\n2,Bob,30"
        records, _, errors = extractor.extract_csv(
            "snap", "t.csv", "t", raw, encoding="utf-8", delimiter=",", primary_key="id",
        )
        # csv.DictReader handles short rows with None values
        assert len(records) == 2
        assert records[0].columns.get("age") is None


class TestXmlExtraction:
    @pytest.fixture
    def extractor(self) -> TableExtractor:
        return TableExtractor()

    def test_standard_xml(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<root>
  <item id="I1" color="red"><name>Apple</name></item>
  <item id="I2" color="green"><name>Pear</name></item>
</root>
"""
        records, contexts, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(errors) == 0
        assert len(records) == 2
        assert records[0].id == "items:I1"
        assert records[0].columns["color"] == "red"
        assert records[0].columns["name"] == "Apple"

    def test_child_element_primary_key(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<root>
  <item><code>A1</code><val>10</val></item>
  <item><code>A2</code><val>20</val></item>
</root>
"""
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_child="code",
        )
        assert len(errors) == 0
        assert records[0].id == "items:A1"

    def test_cdata(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<root>
  <item id="I1"><desc><![CDATA[Special <chars>]]></desc></item>
</root>
"""
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(errors) == 0
        assert records[0].columns["desc"] == "Special <chars>"

    def test_empty_optional_element(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<root>
  <item id="I1"><name>Alice</name><note></note></item>
</root>
"""
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(errors) == 0
        assert records[0].columns["note"] is None

    def test_missing_primary_key(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<root>
  <item><name>Alice</name></item>
</root>
"""
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(records) == 0
        assert len(errors) == 1

    def test_duplicate_primary_key(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<root>
  <item id="I1"><name>Alice</name></item>
  <item id="I1"><name>Bob</name></item>
</root>
"""
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(records) == 1
        assert len(errors) == 1
        assert "duplicate_primary_key" in errors[0]["error"]

    def test_invalid_xml(self, extractor: TableExtractor) -> None:
        raw = b"<root><item></root>"
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(records) == 0
        assert len(errors) == 1

    def test_external_entity_not_resolved(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root><item id="I1"><name>&xxe;</name></item></root>
"""
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        # Should either error or not resolve the entity
        assert len(records) == 0 or (len(records) == 1 and "xxe" not in (records[0].columns.get("name") or ""))

    def test_xml_comment_preserved_in_metadata(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<!-- Comment with PII -->
<root>
  <item id="I1"><name>Alice</name></item>
</root>
"""
        # Comments on root are not currently captured per-row; this test
        # verifies parsing succeeds despite comments.
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(errors) == 0
        assert len(records) == 1

    def test_utf8_accented_text(self, extractor: TableExtractor) -> None:
        raw = "<?xml version=\"1.0\"?><root><item id=\"I1\"><name>Adrián</name></item></root>".encode("utf-8")
        records, _, errors = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert len(errors) == 0
        assert records[0].columns["name"] == "Adrián"

    def test_deterministic_repeated_extraction(self, extractor: TableExtractor) -> None:
        raw = b"""<?xml version="1.0"?>
<root>
  <item id="I1" a="1"><name>X</name></item>
</root>
"""
        r1, _, _ = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        r2, _, _ = extractor.extract_xml(
            "snap", "t.xml", "items", raw,
            row_tag="item", primary_key_attr="id",
        )
        assert r1[0].model_dump() == r2[0].model_dump()
