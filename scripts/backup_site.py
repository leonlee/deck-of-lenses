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
from urllib.error import HTTPError

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


PLACEHOLDER = BASE + 'assets/images/lensArt/PLACEHOLDER.png'


def known_gap(item):
    status_is_404 = (item['http_status'] == 404 if 'http_status' in item
                     else item.get('error') == 'HTTP Error 404: Not Found')
    return item.get('url') == PLACEHOLDER and status_is_404


def required_urls(localization):
    urls = {BASE, BASE + 'assets/json/languages.json', BASE + 'assets/strings/en.json'}
    for lens in localization['LensList']:
        urls.add(BASE + f"assets/images/lensArt/{lens['imageID']}.png")
        urls.add(BASE + 'assets/images/lensart_Thumbs/lens_thumb' + str(lens['index']).replace('.', '_') + '.png')
    return urls


def dependencies(path, raw):
    urls = discover(path, raw)
    if path == 'assets/json/languages.json':
        for language in json.loads(raw.decode('utf-8-sig'))['languages']:
            urls.add(BASE + 'assets/strings/' + language['code'] + '.json')
    return urls


def checked_bytes(destination, item):
    path = safe_path(item['url'])
    if path != item['path']:
        raise ValueError(f'Manifest path mismatch: {path}')
    raw = (destination / path).read_bytes()
    if digest(raw) != item['sha256'] or len(raw) != item['bytes']:
        raise ValueError(f'Checksum mismatch: {path}')
    return raw


def verify(destination, manifest):
    required = required_urls(source())
    saved = set()
    for item in manifest['files']:
        raw = checked_bytes(destination, item)
        saved.add(item['url'])
        required.update(dependencies(item['path'], raw))
    failures = manifest['failures']
    unexpected = [item for item in failures if not known_gap(item)]
    if unexpected:
        raise ValueError(f'Archive has {len(unexpected)} unresolved failures: {unexpected[0]}')
    allowed = {item['url'] for item in failures if known_gap(item)}
    missing = required - saved - allowed
    if missing:
        raise ValueError(f'Missing required resources: {", ".join(sorted(missing))}')
    english = destination / 'assets/strings/en.json'
    if english.read_bytes() != (ROOT / 'archive/en.json').read_bytes():
        raise ValueError('Snapshot English localization differs from translation source')
    if allowed:
        print('Known upstream gap: PLACEHOLDER.png returned HTTP 404')
    print(f'Verified {len(saved)} archived resources and required dependency coverage')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--verify', action='store_true', help='Check checksums and required dependency coverage offline')
    mode.add_argument('--resume', action='store_true', help='Reuse checksum-verified downloads and retry missing or damaged files')
    args = parser.parse_args()
    destination = ROOT / 'archive/site'
    manifest_path = ROOT / 'archive/site-manifest.json'
    if args.verify:
        verify(destination, read(manifest_path))
        return
    if not args.resume and (destination.exists() or manifest_path.exists()):
        parser.error('Snapshot already exists; use --resume to recover it')
    localization = source()
    previous = read(manifest_path) if args.resume and manifest_path.exists() else {}
    records = {item['url']: item for item in previous.get('files', [])}
    cache = dict(records)
    failures = {item['url']: item for item in previous.get('failures', []) if 'url' in item}
    pending = required_urls(localization) | set(records) | set(failures)
    seen = set()
    manifest = {
        'source_url': BASE,
        'captured_at': previous.get('captured_at', datetime.now(timezone.utc).isoformat()),
        'rights_note': read(ROOT / 'archive/manifest.json')['rights_note'],
        'scope': 'HTML entry point, runtime JS/CSS/font dependencies, declared locales, lens art and thumbnails; excludes external linked sites and source maps'
    }

    def checkpoint():
        manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
        manifest['files'] = sorted(records.values(), key=lambda x: x['path'])
        manifest['failures'] = list(failures.values())
        write(manifest_path, manifest)

    def fetch(url):
        path = safe_path(url)
        if url in cache:
            try:
                return cache[url], checked_bytes(destination, cache[url])
            except (OSError, ValueError):
                pass  # Refetch missing or damaged files, never trust their bytes.
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
                if path == 'assets/strings/en.json' and raw != (ROOT / 'archive/en.json').read_bytes():
                    raise ValueError('Live English localization differs from translation source; use a new workspace for a new snapshot')
                if url in cache and (digest(raw) != cache[url]['sha256'] or len(raw) != cache[url]['bytes']):
                    raise ValueError(f'Upstream bytes differ from the recorded snapshot: {path}; refusing to replace the archived version')
                target = destination / path
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + '.part')
                temporary.write_bytes(raw)
                temporary.replace(target)
                return {'url': url, 'path': path, 'bytes': len(raw), 'sha256': digest(raw),
                        'content_type': content_type, 'headers': headers,
                        'downloaded_at': datetime.now(timezone.utc).isoformat()}, raw
            except Exception as exc:
                if isinstance(exc, HTTPError):
                    exc.close()
                if attempt == 2 or isinstance(exc, HTTPError) and exc.code == 404:
                    failure = {'url': url, 'path': path, 'error': str(exc)}
                    if isinstance(exc, HTTPError):
                        failure['http_status'] = exc.code
                    return failure, None
                time.sleep(attempt + 1)

    checkpoint()
    while pending:
        batch = sorted(pending - seen)
        if not batch:
            break
        seen.update(batch)
        pending = set()
        with ThreadPoolExecutor(max_workers=4) as pool:
            for item, raw in pool.map(fetch, batch):
                url = item['url']
                if raw is None:
                    # Retain any original checksum so subsequent resumes remain pinned.
                    failures[url] = item
                    checkpoint()
                    continue
                records[url] = item
                failures.pop(url, None)
                checkpoint()
                pending.update(dependencies(item['path'], raw))
        print(f'Archived {len(records)} resources; {len(failures)} unavailable', flush=True)
    verify(destination, manifest)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(f'Error: {exc}') from exc
