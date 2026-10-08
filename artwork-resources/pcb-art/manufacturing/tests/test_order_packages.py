"""Downloaded evidence must fail closed on stale, missing or unsafe data."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from order_packages import checksum_manifest, verify_bundle, safe_path, check_drc


class BundleIntegrityTests(unittest.TestCase):
    def test_missing_changed_and_extra_files_fail_checksums(self):
        for mutation in ('missing','changed','extra'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                data=root/'native.kicad_pcb'
                data.write_text('source board')
                checksum_manifest(root)
                if mutation=='missing':data.unlink()
                if mutation=='changed':data.write_text('different board')
                if mutation=='extra':(root/'extra.zip').write_bytes(b'unknown package')
                with self.assertRaisesRegex(ValueError,'stale bundle file|inventory differs'):
                    verify_bundle(root)

    def test_absolute_parent_and_symlink_references_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for ref in ('/etc/passwd','../outside','a/../../outside',''):
                with self.subTest(ref=ref),self.assertRaises(ValueError):safe_path(root,ref)
            (root/'link').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):safe_path(root,'link')

    def test_failed_receipt_never_becomes_successful_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'receipt.json').write_text(json.dumps({'status':'running','manufacturingRelease':False}))
            checksum_manifest(root)
            with self.assertRaisesRegex(ValueError,'successful local verification'):verify_bundle(root)

    def test_malformed_drc_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'drc.json'
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Malformed'):check_drc(path,'test.kicad_pcb')
            clean={'source':'test.kicad_pcb','coordinate_units':'mm','included_severities':['error','warning','exclusion'],
                   'kicad_version':'10.0.0','violations':[],'unconnected_items':[]}
            for key in ('violations','unconnected_items','included_severities','ignored_checks'):
                for bad in (None,{},''):
                    with self.subTest(key=key,bad=bad):
                        path.write_text(json.dumps({**clean,key:bad}))
                        with self.assertRaisesRegex(ValueError,'Malformed'):check_drc(path,'test.kicad_pcb')


if __name__=='__main__':unittest.main()
