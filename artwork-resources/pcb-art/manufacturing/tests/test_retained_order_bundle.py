"""Retention must preserve every original byte without unsafe reconstruction."""
import hashlib
import base64
from unittest.mock import patch
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retain_order_bundle import restore, zip_members


class RetentionTests(unittest.TestCase):
    def fixture(self, root):
        snapshot = root / 'snapshot'
        bundle = snapshot / 'bundle'
        bundle.mkdir(parents=True)
        pcb = b'original native geometry'
        cam = b'original gerber bytes'
        (bundle / 'source.kicad_pcb').write_bytes(pcb)
        with zipfile.ZipFile(bundle / 'order.zip', 'w') as archive:
            archive.writestr('layer.gbr', cam)
        def record(data):
            return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        files = {'source.kicad_pcb': record(pcb), 'order.zip': record((bundle / 'order.zip').read_bytes()),
                 'raw/cam/layer.gbr': {**record(cam), 'zip': 'order.zip', 'member': 'layer.gbr'}}
        (snapshot / 'retention.json').write_text(json.dumps({'schemaVersion': 1, 'files': files}))
        return snapshot, files

    def test_restore_reproduces_original_native_and_cam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot, files = self.fixture(root)
            restore(snapshot, root / 'restored')
            for name, record in files.items():
                self.assertEqual(hashlib.sha256((root / 'restored' / name).read_bytes()).hexdigest(), record['sha256'])
            self.assertFalse((snapshot / 'bundle/raw').exists())

    def test_missing_modified_extra_and_zip_substitution_fail(self):
        for mutation in ('missing', 'modified', 'extra', 'zip'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                snapshot, _ = self.fixture(root)
                bundle = snapshot / 'bundle'
                if mutation == 'missing': (bundle / 'source.kicad_pcb').unlink()
                if mutation == 'modified': (bundle / 'source.kicad_pcb').write_bytes(b'changed')
                if mutation == 'extra': (bundle / 'unknown.zip').write_bytes(b'unknown')
                if mutation == 'zip':
                    with zipfile.ZipFile(bundle / 'order.zip', 'w') as archive:
                        archive.writestr('layer.gbr', b'changed gerber')
                with self.assertRaises(ValueError): restore(snapshot, root / 'restored')

    def test_original_local_settings_restore_without_tracking_editor_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot, files = self.fixture(root)
            original = b'original local settings'
            files['source.kicad_prl'] = {'sha256': hashlib.sha256(original).hexdigest(),
                'bytes': len(original), 'base64': base64.b64encode(original).decode('ascii')}
            (snapshot / 'retention.json').write_text(json.dumps({'schemaVersion': 1, 'files': files}))
            (snapshot / 'bundle/source.kicad_prl').write_bytes(b'current user window settings')
            restore(snapshot, root / 'restored')
            self.assertEqual((root / 'restored/source.kicad_prl').read_bytes(), original)

    def test_oversized_retained_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot, _ = self.fixture(root)
            with patch('retain_order_bundle.MAX_GIT_FILE', 1), self.assertRaisesRegex(ValueError, 'storage limit'):
                restore(snapshot, root / 'restored')

    def test_unsafe_recipe_paths_fail(self):
        for unsafe in ('../outside', '/tmp/outside'):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                snapshot, files = self.fixture(root)
                files[unsafe] = files.pop('source.kicad_pcb')
                (snapshot / 'retention.json').write_text(json.dumps({'schemaVersion': 1, 'files': files}))
                with self.assertRaises(ValueError): restore(snapshot, root / 'restored')

    def test_archive_nested_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / 'bad.zip', 'w') as archive:
                archive.writestr('../outside', b'bad')
            with self.assertRaises(ValueError): zip_members(root)

    def test_restore_never_overwrites_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot, _ = self.fixture(root)
            dest = root / 'restored'
            dest.mkdir()
            (dest / 'keep').write_text('user file')
            with self.assertRaises(ValueError): restore(snapshot, dest)
            self.assertEqual((dest / 'keep').read_text(), 'user file')


if __name__ == '__main__':
    unittest.main()
