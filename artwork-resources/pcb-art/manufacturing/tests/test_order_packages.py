"""Downloaded evidence must fail closed on stale, missing or unsafe data."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from collections import Counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from order_packages import checksum_manifest, verify_bundle, safe_path, check_drc, write_order_table, drc_input_text, ROOT
from order_profiles import load_profile, order_manifest, VARIANTS


class BundleIntegrityTests(unittest.TestCase):
    def test_drc_seam_copy_preserves_every_native_primitive(self):
        source=ROOT/'panels/art-spider-nest/01-spider-nest-L07-gold-enig-fill.kicad_pcb'
        original=source.read_text()
        normalized=drc_input_text(source)
        self.assertNotEqual(original,normalized)
        self.assertEqual(Counter(original.splitlines()),Counter(normalized.splitlines()))
        top=ROOT/'panels/art-spider-nest/01-spider-nest-L01-black-enig-art.kicad_pcb'
        self.assertEqual(top.read_text(),drc_input_text(top))

    def test_readable_orders_include_all_source_members(self):
        profile,boards=load_profile()
        with tempfile.TemporaryDirectory() as tmp:
            for variant in VARIANTS:
                order=order_manifest(profile,variant,boards)
                for item in order['packages']:
                    item['zip']={'path':'packages/'+item['id']+'.zip'}
                path=Path(tmp)/(variant+'.md')
                write_order_table(order,path)
                text=path.read_text()
                self.assertTrue(all(board_id in text for board_id in boards))
                self.assertIn('Choose ONE alternative',text)
                self.assertIn('unknown',text)

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
