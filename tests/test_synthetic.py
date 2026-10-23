import csv
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from novarota.contracts import SOURCES
from novarota.ingestion.manifests import decode_records, read_manifest, verify_files
from novarota.synthetic.generator import GeneratorConfig, build_records, generate
from novarota.synthetic.scenarios import BATCH_IDS, fixed_scenarios


class SyntheticTests(unittest.TestCase):
    def test_same_seed_produces_byte_identical_artifacts(self):
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            generate(first, GeneratorConfig())
            generate(second, GeneratorConfig())
            snapshot = lambda root: {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest() for p in Path(root).rglob("*") if p.is_file()}
            self.assertEqual(snapshot(first), snapshot(second))
            generate(first, GeneratorConfig())  # Retry identico nao altera arquivos.

    def test_changed_seed_cannot_silently_overwrite_generation(self):
        with TemporaryDirectory() as output:
            generate(output, GeneratorConfig())
            with self.assertRaises(ValueError):
                generate(output, GeneratorConfig(seed=123))

    def test_parameter_bounds(self):
        for params in ({"customers": 3}, {"transactions": -1}, {"seed": True}, {"customers": True}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                GeneratorConfig(**params)

    def test_business_fixture_is_independent_of_background_volume(self):
        expected = json.loads((Path(__file__).parent / "fixtures/scenario_expectations.json").read_text())
        batches = fixed_scenarios(date(2026, 6, 30))
        all_rows = lambda source: [row for batch in batches.values() for row in batch[source]]
        transactions = all_rows("transacoes")
        refunds = {r["id_estorno"]: r for r in all_rows("estornos")}
        for scenario in ("partial_refund", "full_refund"):
            rule = expected[scenario]
            row = next(r for r in transactions if r["id_transacao"] == rule["transaction"])
            refund = refunds[rule["refund"]]
            self.assertEqual(row["valor"], rule["amount"])
            self.assertEqual(refund["valor_estorno"], rule["refund_amount"])
            self.assertEqual(Decimal(row["valor"]) - Decimal(refund["valor_estorno"]), Decimal(rule["expected_net"]))
        copies = [r for r in transactions if r["id_transacao"] == expected["duplicate_transaction"]]
        self.assertEqual(len(copies), 2)
        self.assertEqual(copies[0], copies[1])
        cdc = all_rows("clientes_cdc")
        self.assertEqual(sum(r["id_evento_cdc"] == expected["duplicate_cdc"] for r in cdc), 2)
        versions = {r["id_evento_cdc"] for r in cdc if r["id_cliente"] == "C001"}
        self.assertEqual(versions, set(expected["customer_versions"]))
        self.assertTrue(any(r["id_cliente"] == "C001" and r["id_conta"] == "A001" for r in all_rows("contas_cdc")))
        self.assertTrue(any(r["id_cliente"] == "C001" and r["id_conta"] == "A002" for r in all_rows("contas_cdc")))
        self.assertEqual({r["id_cartao"] for r in all_rows("cartoes_cdc") if r["id_conta"] in {"A001", "A002"}}, {"K001", "K002"})
        cancelled = next(r for r in all_rows("cartoes_cdc") if r["id_cartao"] == expected["cancelled_card"] and r["status_cartao"] == "CANCELADO")
        before = next(r for r in transactions if r["id_transacao"] == expected["before_cancel"])
        after = next(r for r in transactions if r["id_transacao"] == expected["after_cancel"])
        self.assertLess(before["data_transacao"], cancelled["data_atualizacao"])
        self.assertGreater(after["data_transacao"], cancelled["data_atualizacao"])
        self.assertEqual(next(r for r in transactions if r["id_transacao"] == expected["cancelled_transaction"])["status_transacao"], "CANCELADA")

    def test_manifest_counts_and_csv_schema_extension(self):
        with TemporaryDirectory() as output:
            manifests = generate(output, GeneratorConfig(transactions=0))
            self.assertEqual(len(manifests), 4)
            for path in manifests:
                manifest = read_manifest(path)
                verify_files(manifest, path.parent / "files")
                self.assertEqual({e["source"] for e in manifest["files"]}, set(SOURCES))
                for entry in manifest["files"]:
                    rows = decode_records(entry, (path.parent / "files" / entry["path"]).read_bytes())
                    for row in rows:
                        self.assertTrue(set(SOURCES[entry["source"]].fields).issubset(row))
                    if entry["source"] == "transacoes":
                        headers = next(csv.reader((path.parent / "files" / entry["path"]).read_text().splitlines()))
                        self.assertEqual("dispositivo" in headers, manifest["batch_id"] == BATCH_IDS[3])
            evolution = read_manifest(manifests[-1])
            self.assertTrue(any(e["rows"] == 0 and e["source"] == "clientes_cdc" for e in evolution["files"]))

    def test_invalid_links_and_transaction_versions_are_explicit(self):
        expected = json.loads((Path(__file__).parent / "fixtures/scenario_expectations.json").read_text())
        batches = fixed_scenarios(date(2026, 6, 30))
        rows = {source: [row for batch in batches.values() for row in batch[source]] for source in SOURCES}
        for link in expected["orphan_links"]:
            actual = next(row for row in rows[link["source"]] if row[link["key"]] == link["id"])
            self.assertEqual(actual[link["field"]], link["value"])
            parent_ids = {row[link["parent_key"]] for row in rows[link["parent_source"]]}
            self.assertNotIn(link["value"], parent_ids)
        bad_cpf = expected["invalid_cpf"]
        self.assertEqual(next(row for row in rows["clientes_cdc"] if row["id_cliente"] == bad_cpf["customer"])["cpf"], bad_cpf["value"])
        fx = expected["foreign_currency"]
        self.assertEqual(next(row for row in rows["transacoes"] if row["id_transacao"] == fx["transaction"])["moeda"], fx["currency"])
        versions = [row for row in rows["transacoes"] if row["id_transacao"] == "T_VERSION"]
        self.assertEqual([(row["sequencia_origem"], row["status_transacao"]) for row in versions], [("1", "PENDENTE"), ("2", "APROVADA")])
        self.assertTrue(any(row["id_cartao"] == "K004" and row["operacao"] == "D" for row in rows["cartoes_cdc"]))

    def test_out_of_order_events_and_seed_variation(self):
        records = build_records(GeneratorConfig())
        initial, incremental, late = (records[batch] for batch in BATCH_IDS[:3])
        self.assertLess(late["clientes_cdc"][0]["data_atualizacao"], incremental["clientes_cdc"][0]["data_atualizacao"])
        self.assertLess(late["transacoes"][1]["data_transacao"], initial["transacoes"][0]["data_transacao"])
        self.assertNotEqual(records[BATCH_IDS[0]]["transacoes"], build_records(GeneratorConfig(seed=99))[BATCH_IDS[0]]["transacoes"])
