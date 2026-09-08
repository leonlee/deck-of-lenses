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

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
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
        self.assertEqual(len(pages), 235)
        for page in pages:
            parsed = References()
            parsed.feed(page.read_text())
            for ref in parsed.refs:
                url = urlsplit(ref)
                if url.scheme or url.netloc or not url.path:
                    continue
                target = (page.parent / unquote(url.path)).resolve()
                self.assertTrue(target.is_relative_to(self.output), (page, ref))
                if target.is_dir():
                    target /= 'index.html'
                self.assertTrue(target.is_file(), (page, ref))

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


if __name__ == '__main__':
    unittest.main()
