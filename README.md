# cite2fn

A Claude Code plugin that converts hyperlinked citations, parenthetical references, and inline author-date mentions in Word documents into properly formatted Bluebook footnotes or endnotes.

## The problem

Legal academics and law review authors frequently draft in Google Docs or Word using hyperlinks, author-date parentheticals, and references sections. Journals and publishers require Bluebook citation format with footnotes. Converting a 40-page paper by hand means hours of tedious, error-prone work: looking up each source, formatting it, inserting footnotes, cleaning up the body text, and tracking repeated citations for *supra* and *Id.*

## How it works

Drop a .docx file into Claude Code, and the plugin handles the full conversion:

1. **Scans** the document for every citation — hyperlinks, parentheticals like `(Smith 2023)`, inline references like `Bisbee et al. (2023) found...`, and existing footnotes with bare URLs
2. **Fetches metadata** from source URLs (title, authors, journal, year) so citations can be formatted correctly
3. **Resolves internal references** by matching anchor links and parentheticals to a References/Bibliography section
4. **Formats** each citation in Bluebook 21st edition style
5. **Inserts** footnotes (or endnotes) into the document
6. **Cleans up** the body text — removes redundant years, parentheticals, and hyperlink formatting while preserving author names that serve a grammatical role in the sentence
7. **Applies short forms** — *Id.* for consecutive citations to the same source, *supra* for non-consecutive repeats
8. **Flags uncertainties** with Word comments so you know exactly what to double-check

The original file is never modified. You always get a new `_converted.docx`.

## Example use cases

**Law review article drafted in Google Docs.** The author used hyperlinks throughout — clicking "Sunstein (2024)" jumps to an entry in the References section, and some citations link directly to SSRN or journal pages. The plugin detects all of these, pulls metadata from the URLs, matches internal anchors to reference entries, and produces a document with Bluebook footnotes ready for editorial review.

**Empirical legal studies paper.** The draft is full of parenthetical citations like `(Angelino et al., 2017)` and inline references like `DellaVigna and Gentzkow (2019) show that...`. There is no References section and no hyperlinks — just plain text. The plugin detects the author-date patterns, flags citations it can't find a source for, and converts the ones it can into properly formatted footnotes.

**Conference paper being adapted for a law journal.** The document has 25+ hyperlinks to arXiv, ACM Digital Library, and IEEE, with some sources cited multiple times. The plugin fetches metadata from each URL, formats the first citation in full Bluebook style, and automatically applies *supra* short forms for repeated sources — turning `Hullman (2025)` into `Hullman, *supra* note 3` on subsequent appearances.

**Existing footnotes that need cleanup.** A draft already has footnotes, but they contain bare URLs or incomplete citations rather than Bluebook formatting. The plugin detects these, fetches metadata from the URLs, and replaces the footnote content with proper Bluebook text.

## Key features

- Detects 5 citation patterns: external hyperlinks, internal anchor links, parentheticals, inline author-date, and existing footnotes
- Handles split hyperlinks from Google Docs exports (where a single citation spans multiple XML elements)
- Fetches bibliographic metadata from academic sources (arXiv, SSRN, DOI, ACM DL, and more)
- Supports both footnotes and endnotes with arabic numeral numbering
- Preserves author names that are grammatically part of a sentence
- Tracks repeated sources for *Id.* and *supra* short forms
- Adds Word comments to flag anything that needs manual attention
- Removes the References section after its content has been moved to footnotes
- Interactive review — Claude shows you every citation before modifying the document

## Setup

Requires Python 3.11+.

### As a Claude Code plugin (recommended)

Add the marketplace and install the plugin:

```
/plugin marketplace add anitasrinivasan/cite2fn
/plugin install cite2fn@cite2fn
```

Then install the Python dependencies (one time):

```bash
pip install python-docx lxml httpx beautifulsoup4
```

### Manual install

```bash
git clone https://github.com/anitasrinivasan/cite2fn.git
cd cite2fn
pip install -e .
```

## Usage

### As a Claude Code plugin (recommended)

Drop your .docx into the conversation and ask Claude to convert citations to Bluebook footnotes — or invoke the skill directly with `/cite2fn:convert`. Claude walks through the full workflow interactively, flagging uncertain citations and asking for your input before making changes.

### As a CLI

The library exposes four commands via `python -m cite2fn.cli`:

**Detect citations:**
```bash
python -m cite2fn.cli detect paper.docx
```

**Parse references section:**
```bash
python -m cite2fn.cli parse-references paper.docx
```

**Fetch URL metadata:**
```bash
python -m cite2fn.cli fetch-urls urls.json
```

**Assemble the final document:**
```bash
python -m cite2fn.cli assemble paper.docx citations.json -o paper_converted.docx
```

Options: `--endnotes` for endnotes instead of footnotes, `--keep-references` to preserve the References section.

## Limitations

- Every output needs human review — Bluebook formatting is not guaranteed to be correct
- Does not handle documents already in Bluebook footnote style
- Editorial judgment is still required for whether author names should remain in the body text

## Dependencies

- `python-docx` — reading/writing .docx
- `lxml` — XML manipulation for footnotes and document internals
- `httpx` — fetching URLs for metadata
- `beautifulsoup4` — parsing fetched HTML for metadata extraction
