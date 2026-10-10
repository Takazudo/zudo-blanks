"""Completed assets must never become fresh generation destinations or candidate carts."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from order_packages import ROOT, run
from build_lower_panels import build
from retain_order_bundle import retain
from verify_ordered import DEFAULT, verify_ordered


class CompletedOrderTests(unittest.TestCase):
    def test_exporters_reject_completed_storage_before_writing(self):
        target = ROOT / 'order-packages/never-generated'
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(ValueError, 'cannot be generation outputs'):
            run(SimpleNamespace(output=target))
        with self.assertRaisesRegex(ValueError, 'cannot be generation outputs'):
            build(target)
        with self.assertRaisesRegex(ValueError, 'not completed order storage'):
            retain(Path('/tmp/nonexistent-candidate'), target, 'unused', 'unused')
        self.assertFalse(target.exists())

    def test_candidate_identity_cannot_pass_completed_verification(self):
        original = json.loads((DEFAULT / 'retention.json').read_text())
        for field, value in [('selection', 'individual-100'), ('sourceCommit', 'unknown'), ('runId', '0')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                candidate = {**original, field: value}
                (root / 'retention.json').write_text(json.dumps(candidate))
                with self.assertRaisesRegex(ValueError, 'identity differs'):
                    verify_ordered(root)

    def test_selected_original_checksums_are_not_rewritten(self):
        original = json.loads((DEFAULT / 'retention.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'provenance').mkdir()
            checksum = (DEFAULT / 'provenance/original-SHA256SUMS').read_bytes()
            (root / 'provenance/original-SHA256SUMS').write_bytes(checksum)
            original['files']['receipt.json']['sha256'] = '0' * 64
            (root / 'retention.json').write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, 'differs from original run'):
                verify_ordered(root)


if __name__ == '__main__':
    unittest.main()
