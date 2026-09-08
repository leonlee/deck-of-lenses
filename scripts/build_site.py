#!/usr/bin/env python3
"""Build a dependency-free bilingual static reader for GitHub Pages."""
import copy
import html
import re
import shutil
from pathlib import Path

from deck import ROOT, source, validate
from book import load_book

OUT = ROOT / '_site'
REPO = 'https://github.com/leonlee/deck-of-lenses'
COPY = {
    'en': {
        'lang': 'en', 'title': 'A Deck of Lenses', 'subtitle': '116 perspectives on game design',
        'guide': 'Book guide', 'chapter': 'Chapter', 'exercise': 'Try it · Original exercise',
        'book_note': 'AI-authored chapter summaries and original exercises, awaiting human review. A companion to Jesse Schell’s The Art of Game Design, 3rd Edition (A K Peters/CRC Press, 2019).',
        'reference': 'EPUB source reference', 'book_lens': 'Lens number in the book',
        'contents': 'Explore 35 chapters', 'context': 'Book context · AI draft',
        'all': 'All lenses', 'search': 'Find a lens', 'placeholder': 'Search a title in English or Chinese…',
        'results': 'lenses', 'empty': 'No lenses match your search.', 'clear': 'Clear search',
        'catalog': 'The deck', 'questions': 'Questions to ask yourself', 'illustration': 'Illustration',
        'previous': 'Previous lens', 'next': 'Next lens', 'source': 'Original deck',
        'note': 'An independent reading edition of Jesse Schell’s Deck of Lenses. Chinese text is an unofficial AI translation awaiting human review.',
        'rights': 'Original text and artwork belong to their respective rights holders. Archived and translated with permission confirmed by the repository owner.',
        'skip': 'Skip to content', 'draft': 'Chinese translation · AI draft', 'lens': 'Lens',
        'Designer': 'Designer', 'Player': 'Player', 'Experience': 'Experience', 'Process': 'Process', 'Game': 'Game',
    },
    'zh': {
        'lang': 'zh-CN', 'title': '游戏设计透镜', 'subtitle': '从 116 个视角思考游戏设计',
        'guide': '阅读指南', 'chapter': '章节', 'exercise': '试一试 · 原创练习',
        'book_note': 'AI 撰写的章节摘要与原创练习，尚待人工审校。配合 Jesse Schell《The Art of Game Design》第三版（A K Peters/CRC Press，2019）阅读。',
        'reference': 'EPUB 来源定位', 'book_lens': '原书透镜编号',
        'contents': '浏览 35 个章节', 'context': '原书背景 · AI 草稿',
        'all': '全部透镜', 'search': '寻找透镜', 'placeholder': '用中文或英文搜索标题…',
        'results': '张透镜', 'empty': '没有找到匹配的透镜。', 'clear': '清除搜索',
        'catalog': '卡牌目录', 'questions': '问问自己', 'illustration': '插画',
        'previous': '上一张透镜', 'next': '下一张透镜', 'source': '原版卡牌',
        'note': 'Jesse Schell「透镜卡牌」的独立阅读版本。中文为非官方 AI 翻译草稿，尚未经人工审校。',
        'rights': '原文与插画的权利归原权利人所有。仓库所有者已确认获得备份与翻译许可。',
        'skip': '跳至正文', 'draft': '中文译文 · AI 草稿', 'lens': '透镜',
        'Designer': '设计师', 'Player': '玩家', 'Experience': '体验', 'Process': '过程', 'Game': '游戏',
    },
}


def esc(value):
    return html.escape(str(value), quote=True)


def slug(lens):
    return str(lens['index']).replace('.', '-')


def paragraphs(value):
    # Parse the source's leading quotation without stripping literal tildes elsewhere.
    quote = re.match(r'^\s*~(.*?)~\s*(.*)$', value, re.DOTALL)
    def prose(text):
        return ''.join('<p>' + '<br>'.join(esc(line.strip()) for line in part.strip().splitlines()) + '</p>'
                       for part in re.split(r'\n[ \t]*\n', text) if part.strip())
    if quote:
        return '<blockquote>' + prose(quote[1]) + '</blockquote>' + prose(quote[2])
    return prose(value)


def shell(locale, title, content, base, alternate, catalog=False):
    t = COPY[locale]
    switch = (f'<span aria-current="page">English</span><a href="{alternate}" lang="zh-CN" hreflang="zh-CN">简体中文</a>'
              if locale == 'en' else
              f'<a href="{alternate}" lang="en" hreflang="en">English</a><span aria-current="page">简体中文</span>')
    return f'''<!doctype html>
<html lang="{t['lang']}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} · Deck of Lenses</title>
  <meta name="description" content="{esc(t['subtitle'])}. {esc(t['note'])}">
  <link rel="stylesheet" href="{base}assets/style.css">
  <link rel="icon" href="{base}assets/favicon.ico">
  <link rel="alternate" hreflang="{'zh-CN' if locale == 'en' else 'en'}" href="{alternate}">
  <script defer src="{base}assets/app.js"></script>
</head>
<body>
<a class="skip" href="#content">{t['skip']}</a>
<header class="topbar"><div class="topbar-inner">
  <a class="brand" href="{base}{locale}/"><span class="brand-mark" aria-hidden="true">◈</span> DECK OF LENSES</a>
  <a class="guide-link" href="{base}{locale}/book/">{t['guide']}</a>
  <nav class="language" aria-label="Language / 语言">{switch}</nav>
</div></header>
<main id="content" class="{'catalog' if catalog else 'reader'}">{content}</main>
<footer><div class="footer-top"><a class="footer-brand" href="{base}{locale}/">{t['title']}</a>
<div><a href="https://deck.artofgamedesign.com/">{t['source']} ↗</a><a href="{REPO}">GitHub ↗</a></div></div>
<p>{t['note']}</p><p class="rights">{t['rights']}</p></footer>
</body></html>'''


def catalog(locale, lenses, english, chinese, base='../'):
    t = COPY[locale]
    other = 'zh' if locale == 'en' else 'en'
    cards = []
    for lens, en, zh in zip(lenses, english, chinese):
        search = f"{lens['name']} {en['title']} {zh['title']}"
        suits = ' · '.join(t[s] for s in lens['suitlist'])
        cards.append(f'''<li data-lens data-search="{esc(search)}" data-suits="{esc(' '.join(lens['suitlist']))}">
<a class="lens-card" href="{base}{locale}/lenses/{slug(lens)}/">
<div class="card-art"><img src="{base}assets/thumbs/lens_thumb{str(lens['index']).replace('.', '_')}.png" alt="" loading="lazy" width="220" height="160"><span class="card-number">{esc(lens['name'])}</span></div>
<div class="card-copy"><h2>{esc(lens['title'])}</h2><div class="card-meta"><span>{suits}</span><span aria-hidden="true">↗</span></div></div>
</a></li>''')
    filters = ''.join(f'<button type="button" data-filter="{key}" aria-pressed="false">{t[key]}</button>'
                      for key in ('Designer', 'Player', 'Experience', 'Process', 'Game'))
    content = f'''<section class="intro"><div><p class="eyebrow">JESSE SCHELL · THE ART OF GAME DESIGN</p>
<h1>{t['title']}</h1><p class="subtitle">{t['subtitle']}</p></div><span class="edition">EN / 简体中文</span></section>
<section class="tools" id="catalog-tools" aria-label="{t['search']}" hidden>
<label class="search"><span aria-hidden="true">⌕</span><span class="sr-only">{t['search']}</span><input type="search" id="search" placeholder="{t['placeholder']}" autocomplete="off"></label>
<div class="filters" role="group" aria-label="{t['catalog']}"><button type="button" data-filter="all" aria-pressed="true">{t['all']}</button>{filters}</div>
</section>
<p class="result-count" aria-live="polite" aria-atomic="true"><span id="count">{len(lenses)}</span> {t['results']}</p>
<ul class="card-grid">{''.join(cards)}</ul>
<div id="empty" class="empty" hidden><p>{t['empty']}</p><button type="button" id="clear">{t['clear']}</button></div>'''
    return shell(locale, t['title'], content, base, f'{base}{other}/', catalog=True)


def reader(locale, lenses, index, book_data):
    lens = lenses[index]
    t = COPY[locale]
    base = '../../../'
    other = 'zh' if locale == 'en' else 'en'
    questions = ''.join(f'<li>{esc(question)}</li>' for question in lens['questionlist'])
    suits = ' · '.join(t[s] for s in lens['suitlist'])
    previous = (f'<a href="../{slug(lenses[index - 1])}/"><span>← {t["previous"]}</span><strong>{esc(lenses[index - 1]["title"])}</strong></a>' if index else '<span></span>')
    following = (f'<a href="../{slug(lenses[index + 1])}/"><span>{t["next"]} →</span><strong>{esc(lenses[index + 1]["title"])}</strong></a>' if index + 1 < len(lenses) else '<span></span>')
    book_index, notes = book_data
    ref = book_index['lenses'][str(lens['index'])]
    note = notes[ref['chapter']]
    context = f'''<section class="book-context"><p class="eyebrow">{t['context']}</p>
<h2><a href="{base}{locale}/book/#chapter-{ref['chapter']}">{t['chapter']} {ref['chapter']}: {esc(note['title'][locale])}</a></h2>
<p>{esc(note['summary'][locale])}</p><p class="source-ref">{t['book_lens']}: {esc(ref['book_number'])}</p>
<details><summary>{t['reference']}</summary><code>{esc(ref['epub_href'])}</code></details></section>'''
    content = f'''<a class="back" href="../../">← {t['catalog']}</a>
<div class="reading-layout"><aside class="illustration"><div class="art-frame"><img src="{base}assets/art/{esc(lens['imageID'])}.png" alt="{esc(lens['title'])}" width="560" height="480"></div><p>{t['illustration']}: {esc(lens['artist'])}</p></aside>
<article><p class="eyebrow">{t['lens']} {esc(lens['name'])} <span>· {suits}</span></p>
<h1>{esc(lens['title'])}</h1>{'<p class="draft">'+t['draft']+'</p>' if locale == 'zh' else ''}
<div class="description">{paragraphs(lens['description'])}</div>
<h2 class="question-heading">{t['questions']}</h2><ol class="questions">{questions}</ol>
{context}
</article></div><nav class="reader-nav" aria-label="{t['catalog']}">{previous}{following}</nav>'''
    return shell(locale, lens['cardTitle'], content, base, f'{base}{other}/lenses/{slug(lens)}/')


def book_guide(locale, lenses, book_data):
    t = COPY[locale]
    index, notes = book_data
    lens_by_id = {str(lens['index']): lens for lens in lenses}
    contents, sections = [], []
    for number, note in sorted(notes.items()):
        title = esc(note['title'][locale])
        contents.append(f'<li><a href="#chapter-{number}">{number}. {title}</a></li>')
        takeaways = ''.join(f'<li>{esc(point[locale])}</li>' for point in note['takeaways'])
        links = ''.join(f'<li><a href="../lenses/{slug(lens_by_id[key])}/">{esc(ref["book_number"])} · {esc(lens_by_id[key]["title"])}</a></li>'
                        for key, ref in index['lenses'].items() if ref['chapter'] == number)
        references = '<br>'.join(f'<code>{esc(ref)}</code>' for ref in note['references'])
        sections.append(f'''<section class="chapter" id="chapter-{number}">
<p class="eyebrow">{t['chapter']} {number:02}</p><h2>{title}</h2>
<p>{esc(note['summary'][locale])}</p><ul>{takeaways}</ul>
<div class="exercise"><h3>{t['exercise']}</h3><p>{esc(note['exercise'][locale])}</p></div>
{'<h3>'+t['all']+'</h3><ul class="chapter-lenses">'+links+'</ul>' if links else ''}
<details><summary>{t['reference']}</summary>{references}</details>
</section>''')
    content = f'''<a class="back" href="../">← {t['catalog']}</a>
<section class="intro"><div><p class="eyebrow">JESSE SCHELL · THIRD EDITION</p><h1>{t['guide']}</h1><p class="guide-note">{t['book_note']}</p></div></section>
<div class="guide-layout"><nav class="chapter-index" aria-label="{t['contents']}"><details><summary>{t['contents']}</summary><ol>{''.join(contents)}</ol></details></nav>
<div>{''.join(sections)}</div></div>'''
    other = 'zh' if locale == 'en' else 'en'
    return shell(locale, t['guide'], content, '../../', f'../../{other}/book/')


def build():
    book_data = load_book()
    original = source()
    translated = copy.deepcopy(original)
    entries = validate('zh-CN', complete=True)['entries']
    for lens in translated['LensList']:
        prefix = f"lenses/{lens['index']}/"
        for key in ('title', 'cardTitle', 'description'):
            lens[key] = entries[prefix + key]['target']
        lens['questionlist'] = [entries[prefix + 'questionlist/' + str(i)]['target'] for i in range(len(lens['questionlist']))]
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    assets = OUT / 'assets'
    shutil.copytree(ROOT / 'web', assets)
    shutil.copytree(ROOT / 'archive/site/assets/images/lensArt', assets / 'art')
    shutil.copytree(ROOT / 'archive/site/assets/images/lensart_Thumbs', assets / 'thumbs')
    shutil.copyfile(ROOT / 'archive/site/favicon.ico', assets / 'favicon.ico')
    english, chinese = original['LensList'], translated['LensList']
    for locale, lenses in (('en', english), ('zh', chinese)):
        directory = OUT / locale
        directory.mkdir()
        (directory / 'index.html').write_text(catalog(locale, lenses, english, chinese), encoding='utf-8')
        (directory / 'book').mkdir()
        (directory / 'book/index.html').write_text(book_guide(locale, lenses, book_data), encoding='utf-8')
        for i, lens in enumerate(lenses):
            target = directory / 'lenses' / slug(lens)
            target.mkdir(parents=True)
            (target / 'index.html').write_text(reader(locale, lenses, i, book_data), encoding='utf-8')
    (OUT / 'index.html').write_text(catalog('en', english, english, chinese, base='./'), encoding='utf-8')
    (OUT / '.nojekyll').touch()
    print(f'Built {2 * len(english) + 5} pages in {OUT}')


if __name__ == '__main__':
    build()
