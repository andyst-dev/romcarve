"""Check the public derived-facts record and rendering invariants without ROMs."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cartridge_map', ROOT / 'docs/make_cartridge_map.py')
assert spec is not None and spec.loader is not None
visual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(visual)


class PublishedFactsTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / 'docs/german-validation.json').read_text())
        self.map = json.loads((ROOT / 'docs/cartridge-map.json').read_text())

    def test_manifest_and_visual_counts_agree(self):
        manifest = self.record['manifest']
        self.assertEqual(sum(manifest['operations_by_kind'].values()), manifest['staging_operations'])
        self.assertEqual(sum(manifest['source_decisions'].values()), 37)
        self.assertEqual(self.map['edits_total'], manifest['staging_operations'])
        self.assertEqual(sum(b['edits'] for b in self.map['blocks']), self.map['edits_total'])
        self.assertFalse(any(b['same'] and b['edits'] for b in self.map['blocks']))

    def test_reference_and_distribution_counts_are_consistent(self):
        symbols = self.record['reference_symbols']
        self.assertEqual(symbols['names'], symbols['nonzero'] + symbols['unresolved'])
        pack = self.record['reconstruction']
        self.assertEqual(pack['pack_entries_exact'], pack['recipe_entries_exact'] + pack['generated_outputs_exact'])
        self.assertEqual(pack['pak_verified'], pack['pack_entries_exact'])
        self.assertLessEqual(pack['game_literal_bytes'], pack['game_literal_limit'])
        self.assertTrue(all(s == 'success' for s in self.record['ci_jobs'].values()))

    def test_both_renderings_are_valid_xml_with_current_count(self):
        for name, palette in visual.PALETTES.items():
            text = visual.build(self.map, palette, dark=name == 'dark')
            ET.fromstring(text)
            self.assertIn(f"{self.map['edits_total']:,} staging operations", text)

    def test_renderer_refuses_inconsistent_operation_total(self):
        broken = copy.deepcopy(self.map)
        broken['edits_total'] += 1
        with self.assertRaises(AssertionError):
            visual.build(broken, visual.PALETTES['light'], dark=False)

    def test_renderer_refuses_inconsistent_block_coverage(self):
        broken = copy.deepcopy(self.map)
        broken['image_bytes'] += 1
        with self.assertRaises(AssertionError):
            visual.build(broken, visual.PALETTES['light'], dark=False)


if __name__ == '__main__':
    unittest.main()
