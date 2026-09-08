#!/usr/bin/env python3
"""Index a supplied EPUB and validate the bilingual companion study notes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from deck import ROOT, read, source, write

NS = {'h': 'http://www.w3.org/1999/xhtml', 'n': 'http://www.daisy.org/z3986/2005/ncx/',
      'p': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}


def extract_index(epub):
    with zipfile.ZipFile(epub) as archive:
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        package_path = next(e.get('full-path') for e in container.iter() if e.tag.endswith('rootfile'))
        prefix = str(Path(package_path).parent) + '/'
        package = ET.fromstring(archive.read(package_path))
        metadata = package.find('p:metadata', NS)
        manifest = {e.get('id'): e.get('href') for e in package.findall('p:manifest/p:item', NS)}
        spine = package.find('p:spine', NS)
        toc = ET.fromstring(archive.read(prefix + manifest[spine.get('toc')]))
        chapters = []
        documents = {}
        for point in toc.findall('.//n:navPoint', NS):
            href = point.find('n:content', NS).get('src')
            match = re.fullmatch(r'(.+\.xhtml)#chapter(\d+)', href)
            if not match:
                continue
            number = int(match[2])
            if number > 35:  # The unnumbered farewell uses chapter36 internally.
                continue
            document = ET.fromstring(archive.read(prefix + match[1]))
            documents[match[1]] = document
            title = ''.join(point.find('n:navLabel/n:text', NS).itertext())
            chapters.append({
                'number': number, 'title': re.sub(r'^\d+\s+', '', title),
                'epub_href': prefix + href,
                'sections': [{'title': ''.join(e.itertext()).strip(), 'epub_href': prefix + match[1] + '#' + e.get('id')}
                             for e in document.iter() if re.fullmatch(r'sec\d+_\d+(?:_\d+)*', e.get('id', ''))],
            })
        table_path = next(prefix + href for href in manifest.values() if href.endswith('_tol.xhtml'))
        table = ET.fromstring(archive.read(table_path))
        lenses = {}
        for link in table.findall('.//h:a', NS):
            label = ''.join(link.itertext()).strip()
            match = re.match(r'#(\d+½?|∞)\s*(.*)', label)
            if not match:
                continue
            book_number = match[1]
            deck_id = '113' if book_number == '∞' else book_number.replace('½', '.5')
            href = link.get('href')
            filename, anchor = href.split('#', 1)
            chapter_number = int(re.search(r'chapter(\d+)', filename)[1])
            document = documents[filename]
            if not any(e.get('id') == anchor for e in document.iter()):
                raise ValueError(f'Missing EPUB lens anchor: {href}')
            if deck_id in lenses:
                raise ValueError(f'Duplicate lens ID: {deck_id}')
            lenses[deck_id] = {'book_number': book_number, 'book_title': match[2],
                               'chapter': chapter_number, 'epub_href': prefix + href}
        return {
            'schema_version': 1,
            'book': {key: metadata.findtext('dc:' + key, namespaces=NS) for key in
                     ('title', 'creator', 'publisher', 'date', 'identifier', 'language')},
            'provenance': {'source': 'User-supplied EPUB', 'sha256': hashlib.sha256(Path(epub).read_bytes()).hexdigest(),
                           'index_method': 'EPUB navigation and Table of Lenses; every lens anchor verified',
                           'numbering_note': 'Book ∞ maps to deck 113; book half numbers map to .5. Original deck IDs are unchanged.'},
            'chapters': sorted(chapters, key=lambda c: c['number']), 'lenses': lenses,
        }


def load_book():
    index = read(ROOT / 'book/source-index.json')
    notes = read(ROOT / 'book/chapters.json')
    deck_ids = {str(lens['index']) for lens in source()['LensList']}
    if set(index['lenses']) != deck_ids:
        raise ValueError('Book mapping must cover every deck lens exactly once')
    chapters = {c['number']: c for c in index['chapters']}
    if len(index['chapters']) != 35 or len(chapters) != 35 or set(chapters) != set(range(1, 36)):
        raise ValueError('Expected the 35 numbered chapters of the third edition')
    if len(notes['chapters']) != 35 or {c['number'] for c in notes['chapters']} != set(chapters):
        raise ValueError('Study notes must cover every chapter exactly once')
    if notes['source_sha256'] != index['provenance']['sha256']:
        raise ValueError('Study notes and book index have different sources')
    for c in notes['chapters']:
        for field in ('title', 'summary', 'exercise'):
            if set(c[field]) != {'en', 'zh'} or any(not v.strip() for v in c[field].values()):
                raise ValueError(f"Chapter {c['number']}: missing bilingual {field}")
        if c['title']['en'] != chapters[c['number']]['title']:
            raise ValueError(f"Chapter {c['number']}: title differs from source")
        for point in c['takeaways']:
            if set(point) != {'en', 'zh'} or any(not v.strip() for v in point.values()):
                raise ValueError(f"Chapter {c['number']}: incomplete takeaway")
        if len(c['takeaways']) < 2:
            raise ValueError('Each chapter needs at least two takeaways')
        valid_refs = {chapters[c['number']]['epub_href']} | {s['epub_href'] for s in chapters[c['number']]['sections']}
        if not c['references'] or not set(c['references']) <= valid_refs:
            raise ValueError(f"Chapter {c['number']}: unknown source references")
    for key, lens in index['lenses'].items():
        if lens['chapter'] not in chapters:
            raise ValueError(f'Lens {key}: unknown chapter')
        chapter_file = chapters[lens['chapter']]['epub_href'].split('#')[0]
        if not lens['epub_href'].startswith(chapter_file + '#') or not lens['epub_href'].split('#', 1)[1]:
            raise ValueError(f'Lens {key}: source reference is outside its chapter')
        expected = '∞' if key == '113' else key.replace('.5', '½')
        if lens['book_number'] != expected:
            raise ValueError(f'Lens {key}: incorrect edition numbering')
    return index, {c['number']: c for c in notes['chapters']}


def render_markdown():
    index, notes = load_book()
    for locale in ('en', 'zh'):
        title = 'Book companion · Third edition' if locale == 'en' else '第三版阅读指南'
        lines = [f'# {title}', '',
                 'Jesse Schell · The Art of Game Design, 3rd Edition · A K Peters/CRC Press · 2019', '',
                 'AI-authored summaries and original exercises; not book excerpts or an official translation.' if locale == 'en' else 'AI 撰写的章节摘要与原创练习；并非原书摘录或官方译文。', '',
                 'Source references use the EPUB’s internal file and fragment IDs, not print page numbers.' if locale == 'en' else '来源采用 EPUB 内部文件与段落锚点，不作为纸质版页码。', '']
        for number, note in notes.items():
            lines += [f"## {number}. {note['title'][locale]}", '', note['summary'][locale], '']
            lines += ['- ' + point[locale] for point in note['takeaways']]
            lines += ['', ('**Try it:** ' if locale == 'en' else '**试一试：** ') + note['exercise'][locale], '']
            lenses = [(key, lens) for key, lens in index['lenses'].items() if lens['chapter'] == number]
            if lenses:
                lines += [('**Lenses:** ' if locale == 'en' else '**相关透镜：** ') + ', '.join(
                    f"[{lens['book_number']}](https://leonlee.github.io/deck-of-lenses/{locale}/lenses/{key.replace('.', '-')}/)" for key, lens in lenses), '']
            lines += [('**EPUB references:** ' if locale == 'en' else '**EPUB 来源：** ') + '; '.join('`' + ref + '`' for ref in note['references']), '']
        path = ROOT / f'docs/book-guide.{locale}.md'
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    index_cmd = commands.add_parser('index')
    index_cmd.add_argument('epub', type=Path)
    validate_cmd = commands.add_parser('validate')
    validate_cmd.add_argument('--epub', type=Path, help='Also verify index against the original local EPUB')
    commands.add_parser('render')
    args = parser.parse_args()
    if args.command == 'index':
        target = ROOT / 'book/source-index.json'
        if target.exists():
            parser.error('Book index exists; refusing to overwrite it')
        write(target, extract_index(args.epub))
    elif args.command == 'validate':
        index, notes = load_book()
        if args.epub and extract_index(args.epub) != index:
            parser.error('Book index does not match the supplied EPUB')
        print(f"Validated {len(notes)} chapters and {len(index['lenses'])} lens references")
    else:
        render_markdown()


if __name__ == '__main__':
    main()
