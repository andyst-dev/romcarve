"""Synthetic report fixtures only: no cartridge data or extracted game text."""
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def symbol(name, address, size=4, kind='object'):
    return (f'.global {name}\n.type {name}, %{kind}\n'
            f'.equ {name}, {address}\n.size {name}, {size}\n')


class ManifestReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = self.root / 'synthetic.json.gz'
        self.symbols = self.root / 'synthetic-symbols.s.gz'
        self.data = {'version': 'test', 'status': 'synthetic', 'rom_sha1': '0' * 40,
                     'files': {'sample.c': {'edits': [[0, 1, 16, 2, 'c']]}},
                     'graphics': [], 'floors': [], 'credits': 0, 'credits_entries': 0,
                     'unmapped_source_texts': [],
                     'source_text_decisions': [
                         {'disposition': 'placement_accepted'},
                         {'disposition': 'retail_keyboard_table'},
                         {'disposition': 'retain_source_invariant'}],
                     'id_lists': {'gTestIds': [16, 4]}}

    def run_report(self, symbols=None):
        self.manifest.write_bytes(gzip.compress(json.dumps(self.data).encode(), mtime=0))
        args = [sys.executable, str(ROOT / 'romcarve.py'), 'report', str(self.manifest)]
        if symbols is not None:
            self.symbols.write_bytes(gzip.compress(symbols.encode(), mtime=0))
            args += ['--symbols', str(self.symbols)]
        return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)

    def test_report_decisions_and_id_lists_without_symbol_file(self):
        result = self.run_report()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('decisions  3', result.stdout)
        self.assertIn('placement_accepted', result.stdout)
        self.assertIn('retail_keyboard_table', result.stdout)
        self.assertIn('retain_source_invariant', result.stdout)
        self.assertIn('id_lists   1', result.stdout)

    def test_partial_symbol_counts_and_honest_validation_boundary(self):
        text = '.syntax unified\n' + symbol('gTest', 134217744)
        text += symbol('TestCode', 134217760, kind='function') + symbol('Unproven', 0)
        result = self.run_report(text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('symbols    3 names, 2 nonzero, 1 unresolved', result.stdout)
        self.assertIn('metadata only; cartridge addresses are not validated', result.stdout)

    def test_legacy_integer_unmapped_is_still_supported(self):
        self.data['unmapped_source_texts'] = 17
        del self.data['source_text_decisions']
        del self.data['id_lists']
        result = self.run_report()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('unmapped   17 source texts', result.stdout)
        self.assertNotIn('decisions', result.stdout)

    def test_rejects_data_directives(self):
        result = self.run_report(symbol('gTest', 16) + '.byte 1, 2, 3\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsupported directive', result.stderr)

    def test_rejects_incomplete_records(self):
        result = self.run_report('.global gTest\n.equ gTest, 16\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('incomplete', result.stderr)

    def test_rejects_duplicate_fields(self):
        result = self.run_report(symbol('gTest', 16) + '.equ gTest, 20\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate', result.stderr)

    def test_rejects_expressions_instead_of_evaluating_them(self):
        result = self.run_report(symbol('gTest', 'evil()'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('integer', result.stderr)

    def test_corrupt_deflate_has_a_diagnostic_without_traceback(self):
        self.run_report()
        damaged = bytearray(gzip.compress(b'synthetic metadata', mtime=0))
        damaged[10] = 0xff  # Reserved DEFLATE block type, inside a valid gzip header.
        self.symbols.write_bytes(damaged)
        result = subprocess.run([sys.executable, str(ROOT / 'romcarve.py'), 'report',
                                 str(self.manifest), '--symbols', str(self.symbols)],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid reference metadata', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_supports_plain_text_reference_metadata(self):
        self.run_report()
        path = self.root / 'symbols.s'
        path.write_text(symbol('gPlain', 0x08000010))
        result = subprocess.run([sys.executable, str(ROOT / 'romcarve.py'), 'report',
                                 str(self.manifest), '--symbols', str(path)],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('symbols    1 names, 1 nonzero, 0 unresolved', result.stdout)


if __name__ == '__main__':
    unittest.main()
