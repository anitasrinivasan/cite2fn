# cite2fn

Convert social-science citations in Word documents (.docx) to Bluebook-formatted footnotes or endnotes.

Legal academics often draft with author-date parentheticals, hyperlinked author names, or references sections rather than Bluebook footnotes. Converting by hand is tedious. This tool automates the mechanical parts and uses Claude for the Bluebook formatting step.

## What it does

- Detects all citations in a .docx: hyperlinked (external URLs and internal anchors), parenthetical `(Smith et al., 2023)`, inline `Smith (2023)`, and existing footnotes
- Fetches source URLs for bibliographic metadata (title, authors, journal, year)
- Matches internal-anchor citations to a References section
- Formats citations in Bluebook 21st edition style (via Claude)
- Inserts footnotes or endnotes into the document
- Cleans inline text: removes years, parentheticals, and hyperlink formatting while preserving author names that serve a grammatical role
- Applies *Id.* and *supra* short forms for repeated sources
- Flags anything it can't resolve via Word comments
- Removes the References section (the information now lives in footnotes)
- Never modifies the original file

## What it does NOT do

- Guarantee correct Bluebook formatting — every output needs human review
- Replace editorial judgment on whether author names should stay in the body text
- Handle documents already in Bluebook footnote style

## Setup

Requires Python 3.11+.

```bash
git clone https://github.com/anitasrinivasan/cite2fn.git
cd cite2fn
pip install -e .
```

## Usage

### As a Claude Code skill (recommended)

This tool is designed to run as a [Claude Code](https://claude.ai/code) skill. Drop your .docx into the conversation and ask Claude to convert citations to Bluebook footnotes. The skill handles the full workflow interactively:

1. Detects and classifies all citations
2. Fetches metadata from source URLs
3. Matches citations to any References section
4. Formats each citation in Bluebook style (Claude does this directly — no separate API call)
5. Shows you the results for review before modifying anything
6. Assembles the final document

This gives you an interactive review loop — Claude will flag uncertain citations and ask for your input before proceeding.

### As a CLI

The library exposes four commands via `python -m cite2fn.cli`:

**Detect citations:**
```bash
python -m cite2fn.cli detect paper.docx
```
Outputs JSON with all detected citations, their types, display text, URLs, and context.

**Parse references section:**
```bash
python -m cite2fn.cli parse-references paper.docx
```
Outputs JSON with parsed reference entries and any bookmark anchors.

**Fetch URL metadata:**
```bash
# First write URLs to a JSON file: ["https://arxiv.org/abs/...", ...]
python -m cite2fn.cli fetch-urls urls.json
```
Outputs JSON with bibliographic metadata extracted from each URL.

**Assemble the final document:**
```bash
python -m cite2fn.cli assemble paper.docx citations.json -o paper_converted.docx
```
Takes the original document and a JSON file with Bluebook-formatted citations (the `bluebook_text` field filled in for each), and produces the converted document.

Options:
- `-o, --output` — output file path (default: `<input>_converted.docx`)
- `--endnotes` — use endnotes instead of footnotes
- `--keep-references` — don't remove the References section

### Typical CLI workflow

```bash
# 1. Detect citations
python -m cite2fn.cli detect paper.docx > citations.json

# 2. Parse references (if the document has a References section)
python -m cite2fn.cli parse-references paper.docx > references.json

# 3. Fetch metadata for URLs found in citations
# (extract URLs from citations.json, write to urls.json)
python -m cite2fn.cli fetch-urls urls.json > metadata.json

# 4. Format citations in Bluebook (fill in bluebook_text in citations.json)
# This step is done by Claude in the skill, or manually

# 5. Assemble the final document
python -m cite2fn.cli assemble paper.docx citations_formatted.json -o paper_converted.docx
```

## Citation patterns handled

| Pattern | Example | Detection method |
|---------|---------|-----------------|
| Hyperlink with external URL | `[Kaiser et al (2025)](https://dl.acm.org/...)` | XML hyperlink walk |
| Hyperlink with internal anchor | `[Rossi et al., 1996](#_hqe1036ucurq)` | Anchor resolution to References section |
| Parenthetical (no link) | `(Spann et al., 2025)` | Regex matching |
| Inline author-date | `Neumann et al. (2024) note...` | Regex matching |
| Existing footnotes | Footnotes with bare URLs or non-Bluebook text | Footnote XML scan |

## Inline text cleanup rules

| Rule | When | Before | After |
|------|------|--------|-------|
| 1 | Author name is grammatical (subject/object) | `Bisbee et al. (2023) found that...` | `Bisbee et al. found that...`^1 |
| 2 | Standalone parenthetical | `...for budget-conscious fans. (Arslan et al., 2023)` | `...for budget-conscious fans.`^1 |
| 3 | Hyperlinked citation, no grammatical role | `...significant advantages. [Argyle et al. (2023)](url)` | `...significant advantages.`^1 |
| 4 | Hyperlink on non-citation text | `[Automatic Persona Generation](url) promises...` | `Automatic Persona Generation`^1 `promises...` |
| 5 | Default | Any remaining hyperlink | Remove link formatting, keep text |

## Architecture

```
cite2fn/
  models.py       # Citation, Reference, CitationLedger dataclasses
  detect.py       # Citation detection (5 patterns)
  references.py   # References section parsing + matching
  fetch.py        # URL metadata extraction
  footnotes.py    # Footnote/endnote XML insertion via lxml
  cleanup.py      # Inline text cleanup (Rules 1-5)
  comments.py     # Word comment insertion
  supra.py        # Id./supra short-form logic
  assemble.py     # Full assembly pipeline
  cli.py          # JSON I/O entry points
```

The skill at `.claude/skills/cite2footnote.md` orchestrates these modules. Claude handles the Bluebook formatting step directly in conversation — no separate API call needed.

## Dependencies

- `python-docx` — reading/writing .docx
- `lxml` — XML manipulation for footnotes and document internals
- `httpx` — fetching URLs for metadata
- `beautifulsoup4` — parsing fetched HTML for metadata extraction
