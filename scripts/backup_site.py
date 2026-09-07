#!/usr/bin/env python3
"""Snapshot the deck's same-origin runtime assets, preserving their original bytes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen

from deck import ROOT, digest, read, source, write

BASE = 'https://deck.artofgamedesign.com/'


def safe_path(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != urlsplit(BASE).netloc:
        raise ValueError(f'Not a same-origin HTTPS resource: {url}')
    path = unquote(parsed.path).lstrip('/') or 'index.html'
    if any(p in ('.', '..') for p in path.split('/')) or '\\' in path:
        raise ValueError(f'Unsafe resource path: {path}')
    return path


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value and key in ('src', 'href'):
                self.paths.add(value)


def discover(path, raw):
    found = set()
    if path.endswith('.html'):
        parser = Links()
        parser.feed(raw.decode('utf-8-sig'))
        found.update(urljoin(BASE + path, x) for x in parser.paths)
    elif path.endswith('.css'):
        for item in re.findall(r'url\(([^)]+)\)', raw.decode('utf-8-sig')):
            item = item.strip('\"\' ')
            if not item.startswith('data:'):
                found.add(urljoin(BASE + path, item))
    elif path.endswith('.js'):
        text = raw.decode('utf-8-sig')
        for item in re.findall(r'[\"\']((?:\./)?assets/[^\"\']+\.(?:png|jpg|svg|json))[\"\']', text):
            found.add(urljoin(BASE, item))
        # Menu icons are constructed with "assets/images/" + a bare filename.
        for item in re.findall(r'[\"\']((?:menu_|list_suit_)[\w@.-]+\.png)[\"\']', text):
            found.add(urljoin(BASE, 'assets/images/' + item))
    return {url for url in found if urlsplit(url).netloc == urlsplit(BASE).netloc}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Check saved checksums without network access')
    args = parser.parse_args()
    destination = ROOT / 'archive/site'
    manifest_path = ROOT / 'archive/site-manifest.json'
    if args.verify:
        manifest = read(manifest_path)
        for item in manifest['files']:
            raw = (destination / safe_path(item['url'])).read_bytes()
            if digest(raw) != item['sha256'] or len(raw) != item['bytes']:
                raise ValueError(f"Checksum mismatch: {item['path']}")
        if manifest['failures']:
            print(f"Archive gap: {len(manifest['failures'])} resources were not saved; see manifest failures")
        print(f"Verified {len(manifest['files'])} archived resources")
        return
    if destination.exists() or manifest_path.exists():
        parser.error('Snapshot already exists; refusing to overwrite it')
    localization = source()
    pending = {BASE, BASE + 'assets/json/languages.json'}
    for lens in localization['LensList']:
        pending.add(BASE + f"assets/images/lensArt/{lens['imageID']}.png")
        pending.add(BASE + 'assets/images/lensart_Thumbs/lens_thumb' + str(lens['index']).replace('.', '_') + '.png')
    seen, records, failures = set(), [], []

    def fetch(url):
        path = safe_path(url)
        for attempt in range(3):
            try:
                request = Request(url, headers={'User-Agent': 'DeckOfLenses-AuthorizedArchive/1.0'})
                with urlopen(request, timeout=45) as response:
                    safe_path(response.url)
                    raw = response.read()
                    content_type = response.headers.get('Content-Type', '')
                    if not path.endswith('.html') and 'text/html' in content_type:
                        raise ValueError('Unexpected HTML instead of asset')
                    headers = {k: response.headers[k] for k in ('ETag', 'Last-Modified') if k in response.headers}
                target = destination / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                return {'url': url, 'path': path, 'bytes': len(raw), 'sha256': digest(raw),
                        'content_type': content_type, 'headers': headers}, raw
            except Exception as exc:
                if attempt == 2:
                    return {'url': url, 'path': path, 'error': str(exc)}, None
                time.sleep(attempt + 1)

    while pending:
        batch = sorted(pending - seen)
        if not batch:
            break
        seen.update(batch)
        pending = set()
        with ThreadPoolExecutor(max_workers=4) as pool:
            for item, raw in pool.map(fetch, batch):
                if raw is None:
                    failures.append(item)
                    continue
                records.append(item)
                pending.update(discover(item['path'], raw))
                if item['path'] == 'assets/json/languages.json':
                    for language in json.loads(raw.decode('utf-8-sig'))['languages']:
                        pending.add(BASE + 'assets/strings/' + language['code'] + '.json')
        print(f'Archived {len(records)} resources; {len(failures)} failures', flush=True)
    english = destination / 'assets/strings/en.json'
    if not english.exists() or digest(english.read_bytes()) != digest((ROOT / 'archive/en.json').read_bytes()):
        failures.append({'error': 'Snapshot English localization differs from translation source'})
    write(manifest_path, {
        'source_url': BASE, 'captured_at': datetime.now(timezone.utc).isoformat(),
        'rights_note': read(ROOT / 'archive/manifest.json')['rights_note'],
        'scope': 'HTML entry point, runtime JS/CSS/font dependencies, declared locales, lens art and thumbnails; excludes external linked sites and source maps',
        'files': sorted(records, key=lambda x: x['path']), 'failures': failures
    })
    if failures:
        raise SystemExit(f'Snapshot incomplete: see {manifest_path}')


if __name__ == '__main__':
    main()
