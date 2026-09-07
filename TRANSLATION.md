# AI agent translation instructions

Translate only authorized material imported into this workspace. Read `archive/manifest.json` for provenance, then use `scripts/deck.py jobs` to obtain pending strings.

- Default to Simplified Chinese (`zh-CN`); use Traditional Chinese for `zh-TW`.
- Translate all supplied text faithfully, including questions, without adding advice or omitting qualifications.
- Use natural game-design language. Translate “lens” consistently as “透镜” and “game design” as “游戏设计”. Maintain a terminology list in `translations/glossary.json` if additional terms need decisions.
- Preserve HTML tags, placeholders, paragraph breaks, numbering, and the order of questions. Preserve URLs and proper names unless a standard Chinese name is appropriate.
- Never modify IDs, hashes, suit identifiers, image IDs, artist names, or the original archive.
- Return a UTF-8 JSON array containing exactly `id`, `source_sha256`, and `target` for each requested entry. Copy IDs and hashes from the work file.
- Merge through the CLI. Do not mark your own output `reviewed`; that status is for human review.
- Work in small batches. Validate after merging, and finish with `validate --complete` and `render`.

The resulting translation is an unofficial AI draft until reviewed. Structural validation detects missing entries and changed sources, but does not establish translation quality.
