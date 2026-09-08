import contextlib
from html.parser import HTMLParser
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_site


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.lang = None
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'html':
            self.lang = attrs.get('lang')
        for key in ('href', 'src'):
            if attrs.get(key):
                self.refs.append(attrs[key])


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        # Mimic GitHub's /deck-of-lenses/ project subdirectory.
        cls.output = Path(cls.temp.name).resolve() / 'deck-of-lenses'
        with patch.object(build_site, 'OUT', cls.output), contextlib.redirect_stdout(io.StringIO()):
            build_site.build()

    def test_all_generated_links_and_assets_resolve_inside_project(self):
        pages = list(self.output.rglob('*.html'))
        self.assertEqual(len(pages), 237)
        parsed_pages = {}
        for page in pages:
            parsed = References()
            parsed.feed(page.read_text())
            parsed_pages[page] = parsed
        for page, parsed in parsed_pages.items():
            for ref in parsed.refs:
                url = urlsplit(ref)
                if url.scheme or url.netloc:
                    continue
                target = (page.parent / unquote(url.path)).resolve() if url.path else page
                self.assertTrue(target.is_relative_to(self.output), (page, ref))
                if target.is_dir():
                    target /= 'index.html'
                self.assertTrue(target.is_file(), (page, ref))
                if url.fragment:
                    self.assertIn(unquote(url.fragment), parsed_pages[target].ids, (page, ref))

    def test_every_lens_has_complete_text_and_matching_language_link(self):
        entries = build_site.validate('zh-CN', complete=True)['entries']
        for lens in build_site.source()['LensList']:
            slug = build_site.slug(lens)
            for locale in ('en', 'zh'):
                page = self.output / locale / 'lenses' / slug / 'index.html'
                text = page.read_text()
                parsed = References()
                parsed.feed(text)
                self.assertEqual(parsed.lang, 'en' if locale == 'en' else 'zh-CN')
                other = 'zh' if locale == 'en' else 'en'
                self.assertIn(f'../../../{other}/lenses/{slug}/', parsed.refs)
                book_index, notes = build_site.load_book()
                reference = book_index['lenses'][str(lens['index'])]
                self.assertIn(f'../../../{locale}/book/#chapter-{reference["chapter"]}', parsed.refs)
                self.assertIn(build_site.esc(reference['epub_href']), text)
                self.assertIn(build_site.esc(notes[reference['chapter']]['summary'][locale]), text)
                for i, question in enumerate(lens['questionlist']):
                    expected = question if locale == 'en' else entries[f"lenses/{lens['index']}/questionlist/{i}"]['target']
                    self.assertIn(build_site.esc(expected), text)

    def test_quotations_preserve_attribution_without_source_markers(self):
        entries = build_site.validate('zh-CN', complete=True)['entries']
        for lens in build_site.source()['LensList']:
            if not lens['description'].startswith('~'):
                continue
            for locale, description in (
                ('en', lens['description']),
                ('zh', entries[f"lenses/{lens['index']}/description"]['target']),
            ):
                rendered = build_site.paragraphs(description)
                self.assertIn('<blockquote>', rendered)
                self.assertNotIn('~', rendered)
                self.assertIn('</blockquote><p>', rendered)
                for line in description.splitlines():
                    if line.strip().strip('~'):
                        self.assertIn(build_site.esc(line.strip().strip('~')), rendered)
        self.assertEqual(build_site.paragraphs('About ~10 items.'), '<p>About ~10 items.</p>')

    def test_catalog_controls_require_successful_javascript_initialization(self):
        for locale in ('en', 'zh'):
            page = (self.output / locale / 'index.html').read_text()
            self.assertRegex(page, r'<section[^>]*id="catalog-tools"[^>]* hidden>')
            self.assertEqual(page.count('<li data-lens '), 116)

    def test_book_guides_have_all_chapters_exercises_and_lenses(self):
        index, notes = build_site.load_book()
        for locale in ('en', 'zh'):
            text = (self.output / locale / 'book/index.html').read_text()
            self.assertEqual(text.count('class="chapter"'), 35)
            for number, note in notes.items():
                self.assertIn(f'id="chapter-{number}"', text)
                self.assertIn(build_site.esc(note['exercise'][locale]), text)
            for key in index['lenses']:
                self.assertIn(f'../lenses/{key.replace(".", "-")}/', text)
            other = 'zh' if locale == 'en' else 'en'
            self.assertIn(f'../../{other}/book/', text)


if __name__ == '__main__':
    unittest.main()
