"""Regression assertions for the executed Databricks notebook exports.

These tests validate captured run outputs. They do not execute Spark or replace
the remote Databricks runs recorded by the HTML exports.
"""

import base64
import csv
import json
from pathlib import Path
import re
import urllib.parse
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
NOTEBOOK_EXPORTS = EVIDENCE / "notebooks"


def load_notebook_model(filename):
    html = (NOTEBOOK_EXPORTS / filename).read_text(encoding="utf-8")
    marker = "__DATABRICKS_NOTEBOOK_MODEL = " + chr(39)
    end_marker = chr(39) + ";</script>"
    encoded = html.split(marker, 1)[1].split(end_marker, 1)[0]
    decoded = base64.b64decode(encoded).decode("utf-8")
    return json.loads(urllib.parse.unquote(decoded))


def final_output(model):
    for command in reversed(model.get("commands", [])):
        results = command.get("results") or {}
        for item in reversed(results.get("data", [])):
            if item.get("type") != "ansi":
                continue
            try:
                value = json.loads(item.get("data", ""))
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and "status" in value:
                return value
    raise AssertionError("Notebook export does not contain a final JSON status")


def result_tables(model, command_index):
    results = model["commands"][command_index].get("results") or {}
    return [
        item.get("data", [])
        for item in results.get("data", [])
        if item.get("type") == "table"
    ]


def table_containing(tables, key):
    for rows in tables:
        if any(row and row[0] == key for row in rows):
            return rows
    raise AssertionError(f"No exported result table contains {key}")


class DatabricksEvidenceTests(unittest.TestCase):
    def test_notebook_exports_have_finished_cells_and_success_statuses(self):
        expected = {
            "01_bronze_demo.html": "BRONZE_DEMO_PASSED",
            "02_silver_demo.html": "SILVER_PIPELINE_SUCCEEDED",
            "03_gold_demo.html": "GOLD_PIPELINE_SUCCEEDED",
        }
        for filename, status in expected.items():
            with self.subTest(notebook=filename):
                model = load_notebook_model(filename)
                self.assertTrue(model["commands"])
                self.assertTrue(
                    all(command.get("state") == "finished" for command in model["commands"])
                )
                self.assertEqual(final_output(model)["status"], status)

    def test_bronze_and_silver_reconciliation_outputs(self):
        bronze = final_output(load_notebook_model("01_bronze_demo.html"))
        self.assertEqual(bronze["proof_mode"], "FRESH")
        self.assertEqual(
            bronze["rows_by_source"],
            {
                "clientes_cdc": 14,
                "contas_cdc": 16,
                "cartoes_cdc": 21,
                "transacoes": 54,
                "eventos_risco": 3,
                "estornos": 3,
            },
        )
        self.assertTrue(
            {"replay", "late_files", "schema_rescue", "negative_audit"}.issubset(
                bronze["checks"]
            )
        )

        silver_model = load_notebook_model("02_silver_demo.html")
        silver = final_output(silver_model)
        self.assertEqual(silver["run_id"], "5e3210757d82445cad0bfa0cbe38e9c2")
        quality = silver["quality_by_source"]
        self.assertEqual(sum(row["input_rows"] for row in quality.values()), 111)
        self.assertEqual(sum(row["approved"] for row in quality.values()), 102)
        self.assertEqual(sum(row["duplicates"] for row in quality.values()), 2)
        self.assertEqual(sum(row["quarantine"] for row in quality.values()), 7)
        self.assertEqual(silver["rows_by_table"]["transacoes_atual"], 50)

    def test_silver_outputs_cover_scd2_and_transaction_rules(self):
        model = load_notebook_model("02_silver_demo.html")
        tables = result_tables(model, 4)
        customers = table_containing(tables, "C001")
        customer_history = [row for row in customers if row[0] == "C001"]
        self.assertEqual([row[1] for row in customer_history], ["C001-v1", "C001-v2", "C001-v3"])
        self.assertFalse(customer_history[0][6])
        self.assertFalse(customer_history[1][6])
        self.assertEqual(customer_history[0][5], customer_history[1][4])
        self.assertEqual(customer_history[1][5], customer_history[2][4])
        self.assertEqual(customer_history[-1][6], True)
        self.assertEqual(customer_history[-1][3], "Campinas")

        cards = table_containing(tables, "K001")
        card_history = [row for row in cards if row[0] == "K001"]
        self.assertEqual([row[1] for row in card_history], ["ATIVO", "CANCELADO"])
        self.assertIsNone(card_history[-1][4])

        transactions = table_containing(tables, "T_AFTER_CANCEL")
        by_id = {row[0]: row for row in transactions}
        self.assertFalse(by_id["T_AFTER_CANCEL"][4])
        self.assertEqual(by_id["T_AFTER_CANCEL"][5], ["CARD_NOT_ACTIVE"])
        self.assertTrue(by_id["T_BEFORE_CANCEL"][4])
        self.assertFalse(by_id["T_CANCELLED"][4])
        self.assertEqual(by_id["T_CANCELLED"][5], ["TRANSACTION_NOT_APPROVED"])
        self.assertFalse(by_id["T_FX"][4])
        self.assertEqual(by_id["T_FX"][5], ["NON_BRL"])

    def test_gold_counts_and_business_scenarios(self):
        model = load_notebook_model("03_gold_demo.html")
        output = final_output(model)
        self.assertEqual(output["run_id"], "ddb1e31e37d3426e8b1d97550cfe576f")
        self.assertEqual(output["silver_run_id"], "5e3210757d82445cad0bfa0cbe38e9c2")
        self.assertEqual(
            output["rows_by_table"],
            {
                "gold_fato_transacao": 50,
                "gold_dim_cliente": 12,
                "gold_dim_conta": 15,
                "gold_dim_cartao": 20,
                "gold_dim_estabelecimento": 1,
                "gold_cliente_mes": 27,
                "gold_indicadores_risco": 27,
                "gold_features_cliente": 10,
            },
        )
        self.assertTrue(all(item["version"] == 1 for item in output["input_versions"].values()))

        facts = table_containing(result_tables(model, 3), "T_PARTIAL")
        by_id = {row[0]: row for row in facts}
        self.assertEqual(by_id["T_PARTIAL"][5:10], [True, [], "100.00", "30.00", "70.00"])
        self.assertEqual(by_id["T_FULL"][5:10], [True, [], "80.00", "80.00", "0.00"])
        self.assertTrue(by_id["T_BEFORE_CANCEL"][5])
        self.assertFalse(by_id["T_AFTER_CANCEL"][5])
        self.assertEqual(by_id["T_AFTER_CANCEL"][6], ["CARD_NOT_ACTIVE"])
        self.assertIsNone(by_id["T_AFTER_CANCEL"][7])
        self.assertFalse(by_id["T_CANCELLED"][5])
        self.assertEqual(by_id["T_CANCELLED"][6], ["TRANSACTION_NOT_APPROVED"])
        self.assertFalse(by_id["T_FX"][5])
        self.assertEqual(by_id["T_FX"][6], ["NON_BRL"])

    def test_saved_anomaly_query_run_and_csv_are_consistent(self):
        profile_path = EVIDENCE / "query-profile_01f1d084-b11e-1d8c-aaee-496e19470eb7.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))["query"]
        self.assertEqual(profile["status"], "FINISHED")
        self.assertEqual(profile["id"], "01f1d084-b11e-1d8c-aaee-496e19470eb7")
        self.assertEqual(profile["metrics"]["rowsProducedCount"], 28)
        self.assertEqual(profile["metrics"]["rowsReadCount"], 118)
        with (EVIDENCE / "01_anomalias_cliente_sql.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), profile["metrics"]["rowsProducedCount"])
        from collections import Counter

        self.assertEqual(
            Counter(row["classificacao_comportamento"] for row in rows),
            {"BASELINE_INSUFICIENTE": 25, "NORMAL": 2, "ANOMALIA": 1},
        )

    def test_current_anomaly_sql_is_configured_and_uses_grouped_windows(self):
        sql = (ROOT / "sql" / "01_anomalias_cliente.sql").read_text(encoding="utf-8")
        self.assertNotRegex(sql, r"__(?:CATALOG|GOLD_SCHEMA|DATASET_KEY)__")
        self.assertIn("workspace.novarota_case01_gold.gold_fato_transacao", sql)
        self.assertIn("workspace.novarota_case01_gold.gold_dim_cliente", sql)
        self.assertIn("PARTITION BY id_cliente, cidade, segmento ORDER BY data_mes", sql)
        self.assertIn(
            "PARTITION BY h.data_mes, h.cidade, h.segmento", sql
        )
        self.assertNotIn("PARTITION BY id_cliente ORDER BY data_mes", sql)
        self.assertNotIn("PARTITION BY h.data_mes ORDER BY", sql)
        self.assertRegex(sql, r"(?is)\bROW_NUMBER\s*\(")
        self.assertRegex(sql, r"(?is)\bLAG\s*\(")
        self.assertRegex(sql, r"(?is)\bFIRST_VALUE\s*\(")
        self.assertRegex(sql, r"(?is)\bNTILE\s*\(\s*4\s*\)")


if __name__ == "__main__":
    unittest.main()
