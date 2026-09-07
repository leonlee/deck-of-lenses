# Deck of Lenses · 中文翻译工作区

An authorized snapshot of the [Deck of Lenses](https://deck.artofgamedesign.com/), with a complete Simplified Chinese AI translation and tools for checking and reviewing it.

**内容：116 张透镜卡牌、全部问题和界面文字，共 850 个翻译字段。简体中文由 Codex 翻译，当前均为未经人工审校的 AI 草稿，并非官方译文。**

- [阅读中英对照卡牌](docs/lenses.zh-CN.md)
- [简体中文本地化文件](locales/zh-CN.json) — preserves the original localization schema and non-text metadata.
- [逐条翻译与审校状态](translations/zh-CN.json) — English source, Chinese translation, source hash, and review status for every field.
- [英文原文](archive/en.json) and [provenance](archive/manifest.json).
- [原站快照](archive/site/) and [per-file checksums](archive/site-manifest.json) — original application, English/Japanese localizations, styles, fonts, card art, thumbnails, and interface images.

The source was captured on 2026-09-07. Its 116 entries include fractional indices `67.5`, `93.5`, and `95.5`; these are preserved exactly. External linked websites and source maps are outside the snapshot scope.

**Known source gap:** `assets/images/lensArt/PLACEHOLDER.png` is referenced by the original script but returned HTTP 404. The manifest records this unavailable resource. All 116 actual card illustrations and all 116 thumbnails were saved. Verification checks the 294 saved files and reports the known gap.

## Source and rights

The deck is associated with Jesse Schell's *The Art of Game Design*. The repository owner confirmed permission to reproduce and translate the deck on 2026-09-07. This statement is recorded in the archive manifests. Original text and artwork remain the property of their respective rights holders; this repository does not grant additional rights to that material. Artist credits and source attribution are preserved. The Chinese translation is unofficial and requires human review.

## Read and verify

Read the [bilingual Markdown](docs/lenses.zh-CN.md) directly on GitHub. To view the original site snapshot locally:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory archive/site
```

Open `http://127.0.0.1:8000/`. The original snapshot retains its original English/Japanese language menu. The Chinese translation is delivered separately as Markdown and a compatible localization JSON; the archived application bytes are unchanged.

```sh
python3 scripts/backup_site.py --verify
python3 scripts/deck.py validate --complete
python3 -m unittest discover -s tests -v
```

## Workflow

Requires Python 3.10 or later; no dependencies or API keys are needed for the tools. Run from the repository root.

The committed Simplified Chinese translation is complete. The steps below describe creating a new archive/translation in a clean workspace, or working on another locale.

1. Obtain an authorized English localization JSON file. Its format has `strings`, `scales`, and `LensList` at the top level. Import it with a record of your authorization:

   ```sh
   python3 scripts/deck.py import /path/to/en.json --rights-note 'Permission reference or license details'
   ```

   This preserves the exact input bytes in `archive/en.json`, writes its SHA-256 and provenance to `archive/manifest.json`, and prepares `translations/zh-CN.json`. Import refuses to overwrite an existing archive or translation.

2. Ask an AI agent to follow [the translation instructions](TRANSLATION.md). Export work in small batches:

   ```sh
   python3 scripts/deck.py jobs --limit 12 --output /tmp/deck-jobs.json
   ```

   The agent returns a JSON array of `{ "id": "…", "source_sha256": "…", "target": "…" }` objects. Merge it with:

   ```sh
   python3 scripts/deck.py merge /tmp/deck-results.json
   ```

3. Repeat until all entries are translated, then check completeness and generate bilingual Markdown:

   ```sh
   python3 scripts/deck.py validate --complete
   python3 scripts/deck.py render
   python3 scripts/deck.py export
   ```

   Output is written to `docs/lenses.zh-CN.md` and `locales/zh-CN.json`. All translated text is initially marked `ai-draft`. A reviewer can edit an entry's target and change its status to `reviewed` after checking it against the source; regenerate both outputs afterwards. Run `validate --complete --reviewed` to require human review of every entry. Checks cover completeness, source integrity, markup, and placeholders; they do not prove linguistic quality.

Use `--locale zh-TW` **before the subcommand** for Traditional Chinese, starting with import. This is a separate translation file; the original archive is shared. Use `prepare` after importing to create another locale.

```sh
python3 scripts/deck.py --locale zh-TW prepare
python3 -m unittest discover -s tests -v
```

## GitHub

GitHub repository: [leonlee/deck-of-lenses](https://github.com/leonlee/deck-of-lenses).

The archive is a dated snapshot, not an automatic synchronization job. `scripts/backup_site.py` discovers and downloads same-origin runtime dependencies with four concurrent requests, writes a checksum manifest, and refuses to overwrite an existing snapshot. Original application bugs, external shopping links, and feedback links remain as supplied by the source site.
