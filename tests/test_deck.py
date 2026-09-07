import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('deck', Path(__file__).parents[1] / 'scripts/deck.py')
deck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deck)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        original_root = deck.ROOT
        self.addCleanup(setattr, deck, 'ROOT', original_root)
        deck.ROOT = Path(self.temp.name)
        # Original synthetic text, not copied from the deck.
        self.source = {'strings': {'Menu': 'Example menu'}, 'scales': {}, 'LensList': [
            {'index': 1, 'name': '1', 'title': 'Prototype', 'cardTitle': 'Prototype study',
             'description': 'Build a small experiment.', 'questionlist': ['What will you measure?'],
             'artist': 'Example artist', 'imageID': 'example', 'thumbID': 'example', 'suitlist': ['Game']}]}
        deck.write(deck.ROOT / 'archive/en.json', self.source)
        deck.write(deck.ROOT / 'archive/manifest.json', {'sha256': deck.digest((deck.ROOT / 'archive/en.json').read_bytes())})
        deck.prepare('zh-CN')

    def results(self):
        return [{'id': k, 'source_sha256': v['source_sha256'], 'target': '示例翻译'}
                for k, v in deck.validate('zh-CN')['entries'].items()]

    def test_complete_render_preserves_archive_and_requires_review(self):
        before = (deck.ROOT / 'archive/en.json').read_bytes()
        path = deck.ROOT / 'results.json'
        deck.write(path, self.results())
        deck.merge('zh-CN', path)
        deck.validate('zh-CN', complete=True)
        with self.assertRaisesRegex(ValueError, 'human review'):
            deck.validate('zh-CN', complete=True, reviewed=True)
        deck.render('zh-CN')
        deck.export_locale('zh-CN')
        exported = deck.read(deck.ROOT / 'locales/zh-CN.json')
        for key in ('index', 'name', 'artist', 'imageID', 'thumbID', 'suitlist'):
            self.assertEqual(exported['LensList'][0][key], self.source['LensList'][0][key])
        self.assertEqual(len(exported['LensList'][0]['questionlist']), 1)
        self.assertIn('示例翻译', (deck.ROOT / 'docs/lenses.zh-CN.md').read_text())
        self.assertEqual(before, (deck.ROOT / 'archive/en.json').read_bytes())

    def test_stale_batch_is_rejected_without_partial_merge(self):
        results = self.results()
        results[-1]['source_sha256'] = 'stale'
        path = deck.ROOT / 'results.json'
        deck.write(path, results)
        with self.assertRaisesRegex(ValueError, 'stale'):
            deck.merge('zh-CN', path)
        self.assertTrue(all(v['status'] == 'pending' for v in deck.validate('zh-CN')['entries'].values()))

    def test_incomplete_translation_cannot_render(self):
        with self.assertRaisesRegex(ValueError, 'missing translation'):
            deck.render('zh-CN')

    def test_archive_tampering_is_detected(self):
        (deck.ROOT / 'archive/en.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            deck.validate('zh-CN')

    def test_source_text_cannot_be_silently_replaced(self):
        path = deck.ROOT / 'translations/zh-CN.json'
        data = deck.read(path)
        data['entries']['strings/Menu']['source'] = 'Different source'
        deck.write(path, data)
        with self.assertRaisesRegex(ValueError, 'source or checksum'):
            deck.validate('zh-CN')

    def test_duplicate_batch_is_rejected(self):
        results = self.results()
        results.append(results[0])
        path = deck.ROOT / 'results.json'
        deck.write(path, results)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            deck.merge('zh-CN', path)

    def test_changed_markup_is_rejected_before_write(self):
        results = self.results()
        results[-1]['target'] = '<b>新增标记</b>'
        path = deck.ROOT / 'results.json'
        deck.write(path, results)
        with self.assertRaisesRegex(ValueError, 'markup'):
            deck.merge('zh-CN', path)
        self.assertTrue(all(v['status'] == 'pending' for v in deck.validate('zh-CN')['entries'].values()))


if __name__ == '__main__':
    unittest.main()
