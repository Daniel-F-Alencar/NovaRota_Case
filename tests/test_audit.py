import unittest

from novarota.observability.audit import audited


class MemoryEvents:
    def __init__(self, fail_on=None):
        self.events = []
        self.fail_on = fail_on

    def emit(self, source, status, metrics, error=None):
        if status == self.fail_on:
            raise OSError("audit storage unavailable")
        self.events.append((source, status, dict(metrics), error))


class AuditTests(unittest.TestCase):
    def test_success_keeps_start_and_final_metrics_separate(self):
        writer = MemoryEvents()
        with audited(writer, "transacoes") as metrics:
            metrics["rows"] = 3
        self.assertEqual([e[1] for e in writer.events], ["STARTED", "SUCCEEDED"])
        self.assertEqual(writer.events[0][2], {})
        self.assertEqual(writer.events[1][2], {"rows": 3})

    def test_original_exception_is_raised_and_recorded(self):
        writer = MemoryEvents()
        failure = ValueError("manifest mismatch")
        with self.assertLogs("novarota", "ERROR"), self.assertRaises(ValueError) as caught:
            with audited(writer, "transacoes"):
                raise failure
        self.assertIs(caught.exception, failure)
        self.assertEqual(writer.events[-1][1], "FAILED")
        self.assertIn("manifest mismatch", writer.events[-1][3])

    def test_failed_error_logging_cannot_mask_original_failure(self):
        writer = MemoryEvents(fail_on="FAILED")
        failure = ValueError("original failure")
        with self.assertLogs("novarota", "ERROR"), self.assertRaises(ValueError) as caught:
            with audited(writer, "transacoes"):
                raise failure
        self.assertIs(caught.exception, failure)

    def test_failed_success_event_is_not_reported_as_success(self):
        with self.assertRaises(OSError):
            with audited(MemoryEvents(fail_on="SUCCEEDED"), "transacoes"):
                pass
