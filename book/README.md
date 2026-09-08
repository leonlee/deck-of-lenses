# Third-edition book companion

This directory connects the archived deck to Jesse Schell's *The Art of Game Design, 3rd Edition* (A K Peters/CRC Press, 2019; EPUB identifier `9781351803632`). It was prepared from the repository owner's supplied EPUB on 2026-09-08.

- [source-index.json](source-index.json) records bibliographic metadata, the source file's SHA-256, 35 numbered chapters and their section headings, and an exact chapter/file/fragment reference for each of the 116 lenses.
- [chapters.json](chapters.json) contains English and Simplified Chinese chapter summaries, two takeaways per chapter, and one original companion exercise per chapter. These are AI-authored study notes awaiting human review. The exercises are newly written prompts, not exercises attributed to the author.
- [English Markdown guide](../docs/book-guide.en.md) and [中文阅读指南](../docs/book-guide.zh.md) are generated from those records. Both languages are also included in GitHub Pages, with chapter context on every lens page.

The source index is extracted from the EPUB navigation and its **Table of Lenses**. Each lens destination was checked against an actual element ID in the EPUB. Incidental lens mentions in the prose are not used as the mapping authority. References identify EPUB files and fragments; they do not claim printed page numbers. The unnumbered farewell, internally named `chapter36`, is outside the 35-chapter guide.

Book numbering and web-deck numbering differ in their presentation. Book `67½`, `93½`, and `95½` map to deck `67.5`, `93.5`, and `95.5`. The book's `∞` (*Your Secret Purpose*) maps to deck `113`. The original deck IDs, text, translations, and images retain their existing sources; companion notes are stored separately.

The original EPUB and extracted chapter text are not repository or Pages assets. EPUB files are ignored by Git. This companion provides summaries, bibliographic references, and original exercises; it is not a complete reproduction or an official translation of the book. Source titles and references remain attributable to Jesse Schell and the publisher. Technical and commercial examples in the 2019 book should be read in their historical context.

## Verify and regenerate

No EPUB, additional Python dependencies, or model API key is needed to validate the committed data or build the guide:

```sh
python3 scripts/book.py validate
python3 scripts/book.py render
python3 scripts/build_site.py
```

To verify the extracted index and source checksum against your own copy of the same EPUB:

```sh
python3 scripts/book.py validate --epub '/path/to/The Art of Game Design, 3rd Edition.epub'
```

`python3 scripts/book.py index /path/to/book.epub` creates an index in a fresh workspace and refuses to overwrite an existing one. The extractor is specific to this edition's EPUB structure. A different edition or ebook export requires a separately reviewed mapping; a checksum mismatch must not be bypassed by relabeling the notes.

To improve the companion, edit `chapters.json`, preserve its source references, and regenerate the Markdown and site. Validation checks bilingual completeness, chapter coverage, source consistency, numbering, and chapter references. Optional EPUB validation additionally re-extracts all anchors from the actual source. Semantic accuracy and translation quality still require editorial review.
