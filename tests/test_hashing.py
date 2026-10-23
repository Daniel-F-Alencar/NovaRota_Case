import unittest

from novarota.contracts import SourceContract
from novarota.ingestion.hashing import canonical_payload, row_hash


class HashingTests(unittest.TestCase):
    contract = SourceContract("example", "json", ("id", "valor"), "id")

    def test_canonical_form_has_sorted_keys_and_explicit_nulls(self):
        self.assertEqual(canonical_payload({"id": "A"}, self.contract), '[{"key":"id","value":"A"},{"key":"valor","value":null}]')

    def test_order_does_not_change_hash_but_lexical_values_do(self):
        self.assertEqual(row_hash({"id": "A", "valor": "10.00"}, self.contract), row_hash({"valor": "10.00", "id": "A"}, self.contract))
        self.assertNotEqual(row_hash({"id": "A", "valor": "10.00"}, self.contract), row_hash({"id": "A", "valor": "10.0"}, self.contract))

    def test_extra_values_and_corrupt_record_contribute_to_hash(self):
        original = {"id": "A", "valor": "abc"}
        self.assertNotEqual(row_hash(original, self.contract), row_hash({**original, "dispositivo": "app"}, self.contract))
        self.assertNotEqual(row_hash(original, self.contract), row_hash(original, self.contract, corrupt_record="broken"))

    def test_null_empty_and_unicode_remain_distinct_and_preserved(self):
        self.assertNotEqual(row_hash({"id": "A", "valor": None}, self.contract), row_hash({"id": "A", "valor": ""}, self.contract))
        self.assertIn("São Paulo", canonical_payload({"id": "São Paulo", "valor": "\"\\\n"}, self.contract))
