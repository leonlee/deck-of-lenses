import contextlib
import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import backup_site as backup
import deck


class BackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for module in (backup, deck):
            patcher = patch.object(module, 'ROOT', self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.original = json.dumps({'strings': {}, 'LensList': [], 'scales': {}}).encode()
        (self.root / 'archive').mkdir()
        (self.root / 'archive/en.json').write_bytes(self.original)
        deck.write(self.root / 'archive/manifest.json', {'sha256': deck.digest(self.original), 'rights_note': 'Test fixture'})
        self.urls = {
            backup.BASE: b'<html><script src="js/app.js"></script></html>',
            backup.BASE + 'js/app.js': b'"assets/images/lensArt/PLACEHOLDER.png"',
            backup.BASE + 'assets/json/languages.json': b'{"languages":[{"code":"en"}]}',
            backup.BASE + 'assets/strings/en.json': self.original,
        }
        self.calls = Counter()

    def fetch(self, request, timeout):
        url = request.full_url
        self.calls[url] += 1
        if url not in self.urls:
            raise HTTPError(url, 404, 'Not Found', {}, None)
        value = self.urls[url]
        if isinstance(value, Exception):
            raise value
        response = io.BytesIO(value)
        response.url = url
        response.headers = {}
        return response

    def run_cli(self, *args):
        with patch.object(sys, 'argv', ['backup_site.py', *args]), patch.object(backup, 'urlopen', self.fetch), patch.object(backup.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            backup.main()

    def test_empty_or_failed_archive_cannot_verify(self):
        for manifest in ({'files': [], 'failures': []}, {'files': [], 'failures': [{'url': backup.BASE, 'error': 'timeout'}]}):
            deck.write(self.root / 'archive/site-manifest.json', manifest)
            with self.assertRaises(ValueError):
                self.run_cli('--verify')

    def test_known_placeholder_404_is_the_only_allowed_gap(self):
        self.run_cli()
        self.run_cli('--verify')
        self.assertEqual(self.calls[backup.PLACEHOLDER], 1)
        path = self.root / 'archive/site-manifest.json'
        manifest = deck.read(path)
        manifest['failures'][0]['http_status'] = 500
        manifest['failures'][0]['error'] = 'HTTP Error 500'
        deck.write(path, manifest)
        with self.assertRaisesRegex(ValueError, 'unresolved failures'):
            self.run_cli('--verify')

    def test_resume_reuses_good_files_and_retries_failed_dependency(self):
        script = backup.BASE + 'js/app.js'
        self.urls[script] = OSError('Temporary network failure')
        with self.assertRaisesRegex(ValueError, 'unresolved failures'):
            self.run_cli()
        self.urls[script] = b'"assets/images/lensArt/PLACEHOLDER.png"'
        self.calls.clear()
        self.run_cli('--resume')
        self.assertEqual(self.calls, Counter({script: 1, backup.PLACEHOLDER: 1}))
        self.run_cli('--verify')

    def test_resume_repairs_corrupt_and_missing_downloads(self):
        self.run_cli()
        (self.root / 'archive/site/index.html').write_bytes(b'broken')
        (self.root / 'archive/site/js/app.js').unlink()
        self.calls.clear()
        self.run_cli('--resume')
        self.assertEqual(self.calls, Counter({backup.BASE: 1, backup.BASE + 'js/app.js': 1, backup.PLACEHOLDER: 1}))

    def test_resume_without_manifest_refetches_untrusted_partial_files(self):
        target = self.root / 'archive/site'
        target.mkdir()
        (target / 'index.html').write_bytes(b'partial')
        self.run_cli('--resume')
        self.assertEqual((target / 'index.html').read_bytes(), self.urls[backup.BASE])

    def test_resume_never_accepts_new_upstream_bytes_for_recorded_file(self):
        self.run_cli()
        url = backup.BASE + 'js/app.js'
        target = self.root / 'archive/site/js/app.js'
        old_bytes = target.read_bytes()
        original_record = next(item for item in deck.read(self.root / 'archive/site-manifest.json')['files'] if item['url'] == url)
        target.write_bytes(b'damaged')
        self.urls[url] = b'new upstream version'
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                self.run_cli('--resume')
            self.assertEqual(target.read_bytes(), b'damaged')
            manifest = deck.read(self.root / 'archive/site-manifest.json')
            self.assertIn(original_record, manifest['files'])
            self.assertTrue(any('Upstream bytes differ' in f['error'] for f in manifest['failures']))
        self.urls[url] = old_bytes
        self.run_cli('--resume')
        self.assertEqual(target.read_bytes(), old_bytes)

    def test_missing_dependency_record_is_detected_even_without_failure(self):
        self.run_cli()
        path = self.root / 'archive/site-manifest.json'
        manifest = deck.read(path)
        manifest['files'] = [f for f in manifest['files'] if f['path'] != 'js/app.js']
        deck.write(path, manifest)
        with self.assertRaisesRegex(ValueError, 'Missing required resources'):
            self.run_cli('--verify')


if __name__ == '__main__':
    unittest.main()
