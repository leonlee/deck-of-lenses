import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import book


class BookTests(unittest.TestCase):
    def setUp(self):
        self.index = book.read(book.ROOT / 'book/source-index.json')
        self.notes = book.read(book.ROOT / 'book/chapters.json')

    def validate_with(self, index=None, notes=None):
        with patch.object(book, 'read', side_effect=[index or self.index, notes or self.notes]):
            return book.load_book()

    def test_complete_mapping_preserves_special_numbers(self):
        index, notes = book.load_book()
        self.assertEqual(len(index['lenses']), 116)
        self.assertEqual(len(notes), 35)
        self.assertEqual(index['lenses']['113']['book_number'], '∞')
        for key in ('67.5', '93.5', '95.5'):
            self.assertEqual(index['lenses'][key]['book_number'], key.replace('.5', '½'))

    def test_rejects_missing_lens_and_wrong_numbering(self):
        index = copy.deepcopy(self.index)
        del index['lenses']['113']
        with self.assertRaisesRegex(ValueError, 'every deck lens'):
            self.validate_with(index=index)
        index = copy.deepcopy(self.index)
        index['lenses']['113']['book_number'] = '113'
        with self.assertRaisesRegex(ValueError, 'numbering'):
            self.validate_with(index=index)

    def test_rejects_mismatched_source_and_chapter_reference(self):
        notes = copy.deepcopy(self.notes)
        notes['source_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, 'different sources'):
            self.validate_with(notes=notes)
        index = copy.deepcopy(self.index)
        index['lenses']['113']['epub_href'] = index['chapters'][0]['epub_href']
        with self.assertRaisesRegex(ValueError, 'outside its chapter'):
            self.validate_with(index=index)
        notes = copy.deepcopy(self.notes)
        notes['chapters'][0]['references'] = ['unknown.xhtml#section']
        with self.assertRaisesRegex(ValueError, 'unknown source'):
            self.validate_with(notes=notes)

    def test_rejects_missing_translation_and_duplicate_chapter(self):
        notes = copy.deepcopy(self.notes)
        notes['chapters'][0]['exercise']['zh'] = ' '
        with self.assertRaisesRegex(ValueError, 'bilingual exercise'):
            self.validate_with(notes=notes)
        index = copy.deepcopy(self.index)
        index['chapters'].append(index['chapters'][0])
        with self.assertRaisesRegex(ValueError, '35 numbered chapters'):
            self.validate_with(index=index)


if __name__ == '__main__':
    unittest.main()
