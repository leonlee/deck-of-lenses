#!/usr/bin/env python3
"""Archive authorized localization JSON and manage auditable AI translations."""
import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://deck.artofgamedesign.com/assets/strings/en.json'


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def entries(data):
    """Use stable lens indices rather than list offsets as translation IDs."""
    result = {}

    def add(key, value):
        if not isinstance(value, str):
            raise ValueError(f'{key}: expected text')
        if value.strip():
            result[key] = value

    for key, value in data['strings'].items():
        add('strings/' + key, value)
    seen = set()
    for lens in data['LensList']:
        index = str(lens['index'])
        if index in seen:
            raise ValueError(f'Duplicate lens index: {index}')
        seen.add(index)
        prefix = 'lenses/' + index + '/'
        for key in ('title', 'cardTitle', 'description'):
            add(prefix + key, lens[key])
        for i, question in enumerate(lens['questionlist']):
            add(prefix + 'questionlist/' + str(i), question)
    return result


def source():
    path = ROOT / 'archive/en.json'
    manifest = read(ROOT / 'archive/manifest.json')
    if digest(path.read_bytes()) != manifest['sha256']:
        raise ValueError('Archive checksum does not match manifest')
    return read(path)


def prepare(locale):
    path = ROOT / f'translations/{locale}.json'
    if path.exists():
        raise ValueError(f'Refusing to overwrite {path}')
    write(path, {'locale': locale, 'entries': {
        key: {'source': value, 'source_sha256': digest(value), 'target': '', 'status': 'pending'}
        for key, value in entries(source()).items()
    }})


def validate(locale, complete=False, reviewed=False):
    original = entries(source())
    data = read(ROOT / f'translations/{locale}.json')
    if data['locale'] != locale or set(original) != set(data['entries']):
        raise ValueError('Translation locale or entry IDs do not match source')
    for key, value in data['entries'].items():
        if value['source'] != original[key] or value['source_sha256'] != digest(original[key]):
            raise ValueError(f'{key}: source or checksum changed')
        if not isinstance(value['target'], str) or value['status'] not in ('pending', 'ai-draft', 'reviewed'):
            raise ValueError(f'{key}: invalid translation or status')
        translated = bool(value['target'].strip())
        if translated != (value['status'] != 'pending'):
            raise ValueError(f'{key}: translation and status disagree')
        if translated:
            for pattern in (r'</?[A-Za-z][^>]*>', r'_{3,}'):
                if re.findall(pattern, value['source']) != re.findall(pattern, value['target']):
                    raise ValueError(f'{key}: markup or placeholders changed')
        if complete and not translated:
            raise ValueError(f'{key}: missing translation')
        if reviewed and value['status'] != 'reviewed':
            raise ValueError(f'{key}: needs human review')
    return data


def merge(locale, results):
    data = validate(locale)
    updates = read(results)
    if not isinstance(updates, list):
        raise ValueError('Results must be an array')
    seen = set()
    for update in updates:
        key = update['id']
        if key in seen or key not in data['entries']:
            raise ValueError(f'Duplicate or unknown ID: {key}')
        seen.add(key)
        entry = data['entries'][key]
        if update['source_sha256'] != entry['source_sha256']:
            raise ValueError(f'{key}: stale source checksum')
        if entry['status'] != 'pending':
            raise ValueError(f'{key}: refusing to overwrite existing translation')
        if not isinstance(update['target'], str) or not update['target'].strip():
            raise ValueError(f'{key}: empty translation')
        for pattern in (r'</?[A-Za-z][^>]*>', r'_{3,}'):
            if re.findall(pattern, entry['source']) != re.findall(pattern, update['target']):
                raise ValueError(f'{key}: markup or placeholders changed')
        entry.update(target=update['target'], status='ai-draft')
    write(ROOT / f'translations/{locale}.json', data)


def render(locale):
    data = validate(locale, complete=True)
    def target(key):
        return data['entries'][key]['target'] if key in data['entries'] else ''
    lines = ['# Deck of Lenses · 中文对照', '',
             'Source: https://deck.artofgamedesign.com/', '',
             'Jesse Schell · Unofficial AI translation. 未经人工审校的 AI 翻译草稿。', '',
             '原文及插画权利归原权利人所有。经仓库所有者确认获准备份与翻译。', '',
             '## 目录', '']
    for lens in source()['LensList']:
        index = str(lens['index'])
        lines.append(f"- [{lens['name']} · {target('lenses/' + index + '/title')}](#lens-{index.replace('.', '-')})")
    lines.append('')
    for lens in source()['LensList']:
        prefix = f"lenses/{lens['index']}/"
        statuses = {v['status'] for k, v in data['entries'].items() if k.startswith(prefix)}
        lines.extend([f"<a id=\"lens-{str(lens['index']).replace('.', '-')}\"></a>", '',
                      f"## {lens['name']} · {target(prefix + 'title')}", '',
                      f"Review: {', '.join(sorted(statuses))}", '',
                      f"![Lens {lens['name']}](../archive/site/assets/images/lensArt/{lens['imageID']}.png)", '',
                      lens['cardTitle'], '', target(prefix + 'cardTitle'), '',
                      lens['description'], '', target(prefix + 'description'), ''])
        for i, question in enumerate(lens['questionlist']):
            lines.extend([f'{i + 1}. {question}', '', target(prefix + 'questionlist/' + str(i)), ''])
        lines.extend([f"Artist credit: {lens.get('artist', '')}", ''])
    path = ROOT / f'docs/lenses.{locale}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(line.rstrip() for line in '\n'.join(lines).splitlines()) + '\n', encoding='utf-8')


def export_locale(locale):
    data = validate(locale, complete=True)['entries']
    output = copy.deepcopy(source())
    for key in output['strings']:
        if 'strings/' + key in data:
            output['strings'][key] = data['strings/' + key]['target']
    for lens in output['LensList']:
        prefix = f"lenses/{lens['index']}/"
        for key in ('title', 'cardTitle', 'description'):
            if prefix + key in data:
                lens[key] = data[prefix + key]['target']
        for i in range(len(lens['questionlist'])):
            key = prefix + 'questionlist/' + str(i)
            if key in data:
                lens['questionlist'][i] = data[key]['target']
    write(ROOT / f'locales/{locale}.json', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--locale', choices=['zh-CN', 'zh-TW'], default='zh-CN')
    commands = parser.add_subparsers(dest='command', required=True)
    imp = commands.add_parser('import')
    imp.add_argument('file', type=Path)
    imp.add_argument('--rights-note', required=True)
    commands.add_parser('prepare')
    jobs = commands.add_parser('jobs')
    jobs.add_argument('--limit', type=int, default=12)
    jobs.add_argument('--output', type=Path, required=True)
    mer = commands.add_parser('merge')
    mer.add_argument('file', type=Path)
    val = commands.add_parser('validate')
    val.add_argument('--complete', action='store_true')
    val.add_argument('--reviewed', action='store_true')
    commands.add_parser('render')
    commands.add_parser('export')
    args = parser.parse_args()
    try:
        if args.command == 'import':
            if not args.rights_note.strip():
                raise ValueError('Provide a nonempty authorization reference')
            raw = args.file.read_bytes()
            entries(json.loads(raw.decode('utf-8-sig')))
            archive = ROOT / 'archive/en.json'
            if archive.exists() or (ROOT / 'archive/manifest.json').exists() or (ROOT / f'translations/{args.locale}.json').exists():
                raise ValueError('Archive or translation exists; refusing overwrite')
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(raw)
            write(ROOT / 'archive/manifest.json', {
                'source_url': SOURCE_URL, 'imported_at': datetime.now(timezone.utc).isoformat(),
                'sha256': digest(raw), 'rights_note': args.rights_note,
                'scope': 'User-supplied localization JSON; excludes application and artwork'
            })
            prepare(args.locale)
        elif args.command == 'prepare':
            prepare(args.locale)
        elif args.command == 'jobs':
            if args.limit < 1:
                raise ValueError('Limit must be positive')
            data = validate(args.locale)
            pending = [{'id': k, 'source': v['source'], 'source_sha256': v['source_sha256']}
                       for k, v in data['entries'].items() if v['status'] == 'pending']
            write(args.output, {'locale': args.locale, 'entries': pending[:args.limit]})
        elif args.command == 'merge':
            merge(args.locale, args.file)
        elif args.command == 'validate':
            data = validate(args.locale, args.complete, args.reviewed)
            count = sum(v['status'] != 'pending' for v in data['entries'].values())
            print(f"Valid: {count}/{len(data['entries'])} translated")
        elif args.command == 'render':
            render(args.locale)
        elif args.command == 'export':
            export_locale(args.locale)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
