# cite2footnote v2 — Build Spec

## One-line summary

A Python CLI tool that reads an academic Word document (.docx), detects all citations (hyperlinked, parenthetical, and inline), converts them to Bluebook-formatted footnotes or endnotes with proper short-form handling (supra/id.), cleans citation artifacts from the body text, and flags anything it can't handle via Word comments.

---

## Problem

Legal academics often draft in social-science citation style — author-date parentheticals, hyperlinked author names, or references sections — rather than Bluebook footnotes. Converting to Bluebook is tedious manual work: you have to identify every citation, look up the full bibliographic details, format it correctly, insert a footnote, and clean up the inline text. LLMs are reasonably good at generating first-pass Bluebook from raw bibliographic data, so the tool should automate the mechanical parts and use an LLM for the formatting step.

---

## Real-world citation patterns the tool must handle

Based on analysis of two test papers, the tool will encounter these patterns (often mixed within the same document):

### Pattern 1: Hyperlinked text with external URL
The author name or citation is a clickable hyperlink pointing to the source (arxiv, journal page, SSRN, etc.). The display text varies — sometimes it includes the year, sometimes not.

Examples from the test papers:
- `[Hullman 2025 describes](https://arxiv.org/html/2602.15785v1)`
- `[Kaiser et al (2025)](https://dl.acm.org/doi/10.1145/3708319.3733685)`
- `[Wilson & Caliskan, 2024](https://arxiv.org/abs/2407.20371)`
- `[Bhatnagar](https://ieeexplore.ieee.org/abstract/document/11021210)` (author only, no year in display text)
- `[Rozado](https://peerj.com/articles/cs-3628/)` (author only)

**What to do:** The hyperlink URL is the source. Fetch the URL to extract metadata (title, authors, journal, year, volume, pages, DOI). Send that metadata + the display text to the LLM for Bluebook formatting. Insert as footnote/endnote.

### Pattern 2: Hyperlinked text with internal anchor (references section)
The author name is a hyperlink pointing to a bookmark/anchor within the same document, which resolves to an entry in a References section at the bottom.

Examples:
- `[Rossi et al., 1996)](#_hqe1036ucurq)` → points to anchor `_hqe1036ucurq` in References
- `[Dube and Misra](#_tx25d2522jxa) [(2023)](#_tx25d2522jxa)` → same anchor, split across runs
- `[Aguirre et al., 2010](#_pa9qzg16uy7f)` → internal anchor

**What to do:** Resolve the anchor to find the full bibliographic entry in the References section. Send that entry to the LLM for Bluebook formatting. Insert as footnote/endnote.

### Pattern 3: Plain parenthetical citation (no hyperlink)
An author-date citation in parentheses with no link at all.

Examples:
- `(Salminen et al 2022)`
- `Cegin et al 2023`
- `Hämäläinen et al. (2023)`
- `(Bar-Gill, Sunstein, and Talgam-Cohen, 2023)`

**What to do:** If a References section exists, try to match the author name + year to a full entry there. If no match is found and no hyperlink exists, flag via a Word comment: "Citation detected but no source URL found — please add a hyperlink to the source." Still insert a footnote with whatever information is available, marked as needing verification.

### Pattern 4: Existing footnotes
The document already has footnotes, which may contain bare URLs, partial Bluebook, or a mix.

Examples from Paper 1:
- Footnote 3: just a bare URL to a news article
- Footnote 15: partial Bluebook (`See JOHN RAWLS, A THEORY OF JUSTICE §§ 11–14 (Belknap Press 1971)...`)
- Footnote 13: parenthetical with a hyperlinked year

**What to do:** Convert existing footnotes to proper Bluebook too. If a footnote contains a URL, fetch metadata. Send everything to the LLM for reformatting.

### Pattern 5: Hyperlinked plain text (not a citation)
Some hyperlinks point to sources that aren't standard citations — like the link to `[Automatic Persona Generation](https://persona.qcri.org/)` which is a product/tool, not a paper.

**What to do:** Include these in the scan but let the LLM + classification logic determine whether they're a citable source. If unclear, flag via Word comment.

---

## High-level workflow

```
1. User runs:  python cite2footnote.py paper.docx --endnotes
2. Tool scans document → builds list of all detected citations
3. For each citation with a URL → fetch the URL for metadata
4. If document has a References section → parse it and match to inline cites
5. Send all citation data to Claude API for Bluebook formatting (batched)
6. For each citation in the document body:
   a. Insert footnote/endnote with Bluebook text
   b. Clean the inline text (remove year, remove standalone parentheticals)
   c. Remove the hyperlink formatting (keep author name as plain text)
7. For citations without a source URL → add Word comment flagging it
8. Convert existing footnotes to Bluebook
9. Apply supra/id. short forms for repeated citations
10. Remove the References section (if one was used)
11. Save new .docx + report file
```

---

## CLI interface

```
python cite2footnote.py <input.docx> [options]

Required:
  input              Input .docx file path

Options:
  -o, --output       Output .docx path (default: <input>_converted.docx)
  --endnotes         Use endnotes instead of footnotes (default: footnotes)
  --api-key          Anthropic API key (also reads ANTHROPIC_API_KEY env var)
  --model            Claude model (default: claude-sonnet-4-20250514)
  --dry-run          Show all detected citations and what would happen, don't modify
  --no-fetch         Skip URL fetching (use display text only — faster but less accurate)
  --keep-references  Don't remove the References section from the output
```

---

## Detailed design

### Step 1: Citation detection

Scan the entire document (body paragraphs, tables, existing footnotes) and build a list of every detected citation. Each citation record should capture:

```
{
  "type": "hyperlink_external" | "hyperlink_internal" | "parenthetical" | "inline" | "existing_footnote",
  "display_text": "Hullman 2025 describes",
  "url": "https://arxiv.org/html/2602.15785v1" or null,
  "internal_anchor": "_hqe1036ucurq" or null,
  "matched_reference": "full text from References section" or null,
  "paragraph_index": 5,
  "location_in_paragraph": { "start": 42, "end": 78 },
  "surrounding_sentence": "As Hullman 2025 describes, researchers have used...",
  "author_name": "Hullman",
  "year": "2025",
}
```

**Detection methods (in priority order):**

1. **Hyperlinks**: Walk the document's XML looking for `<w:hyperlink>` elements. Each one is a candidate. Extract the display text, the URL (for external links) or anchor ID (for internal bookmarks).

2. **Parenthetical author-date patterns**: Regex for patterns like `(Author et al. YYYY)`, `(Author YYYY)`, `(Author and Author, YYYY)`, `(Author, Author, and Author YYYY)`. These appear in the body text without any hyperlink.

3. **Inline author-date patterns**: Regex for `Author et al. (YYYY)`, `Author (YYYY)` where the author name is part of the sentence and only the year is in parentheses.

4. **Existing footnotes**: Read all existing footnote content. If a footnote contains a bare URL or non-Bluebook citation text, flag it for conversion.

### Step 2: References section parsing

If the document contains a References / Bibliography / Works Cited section:

1. Identify it by heading text (look for headings containing "References", "Bibliography", "Works Cited").
2. Parse each entry. Entries are typically one paragraph each. Extract author(s), year, title, journal/publisher.
3. Build a lookup table: `(author_last_name, year)` → full reference text.
4. Match parenthetical and inline citations (Pattern 3) against this table.

### Step 3: URL fetching for metadata

For each citation with an external URL:

1. Fetch the page (with a reasonable timeout, e.g. 10 seconds).
2. Extract metadata from the page: look for `<meta>` tags (citation_title, citation_author, citation_journal_title, citation_date, citation_doi, etc.), OpenGraph tags, or structured data.
3. If the URL is a known repository (arxiv, SSRN, DOI.org, ACM DL, JSTOR), use repository-specific parsing for cleaner extraction.
4. Store the extracted metadata alongside the citation record.
5. If the fetch fails (timeout, 403, paywall), fall back to display text only and note the failure.

**Rate limiting:** Add a small delay between fetches (0.5–1 second) to be polite to servers. Deduplicate URLs before fetching.

### Step 4: Bluebook conversion via Claude API

For each citation, assemble all available information and send to the Claude API:

```
Input to LLM:
- Display text: "Kaiser et al (2025)"
- URL: https://dl.acm.org/doi/10.1145/3708319.3733685
- Fetched metadata: { title: "...", authors: [...], journal: "...", year: "2025", ... }
- Matched reference entry (if any): "Kaiser, B., Smith, J., ..."
- Context: "the sentence this citation appears in"

Output from LLM:
- Bluebook formatted citation string
- Confidence flag: "confident" | "needs_review"
```

**System prompt for the LLM** should instruct it to:
- Use Bluebook 21st edition format
- Return ONLY the formatted citation
- For journal articles: Author, *Title*, Volume JOURNAL Page (Year).
- For cases: *Case Name*, Volume Reporter Page (Court Year).
- For books: AUTHOR, TITLE Page (Publisher Year).
- For websites/online sources: Author, *Title*, SITE NAME (Date), URL.
- If information is insufficient for confident formatting, prefix with `[NEEDS MANUAL FORMATTING]`
- Preserve all substance — don't drop authors, dates, or page numbers

**Batching:** Group citations into batches of ~10 for API efficiency. Deduplicate identical citations before sending.

### Step 5: Inline text cleanup

After inserting the footnote/endnote, clean the body text. The rules:

**Rule 1: Author name serves a grammatical role in the sentence → keep name, drop year.**

Before: `As Hullman 2025 describes, researchers have used...`
After: `As Hullman describes,¹ researchers have used...`

Before: `Bisbee et al. (2023) found that ChatGPT...`
After: `Bisbee et al. found that ChatGPT...¹`

Before: `Recent work by Wang et al (2025), for instance, argues that...`
After: `Recent work by Wang et al., for instance, argues that...¹`

**Rule 2: Standalone parenthetical → remove entirely, replace with footnote number.**

Before: `...diversity, by creating affordable entry points for budget-conscious fans. (Arslan et al., 2023)`
After: `...diversity, by creating affordable entry points for budget-conscious fans.¹`

Before: `...as the LLMs create more diverse paraphrases (Cegin et al 2023).`
After: `...as the LLMs create more diverse paraphrases.¹`

**Rule 3: Entire hyperlinked phrase is the citation (no grammatical role) → remove and replace with footnote number.**

Before: `...offering significant advantages. [Argyle et al. (2023)](url)`
After: `...offering significant advantages.¹`

**Rule 4: Hyperlink on a sentence where only the link needs removal → remove hyperlink formatting, keep text, add footnote.**

Before: `[Automatic Persona Generation](https://persona.qcri.org/) promises to take customer data...`
After: `Automatic Persona Generation¹ promises to take customer data...`

**Rule 5: Remove hyperlink formatting.** After adding the footnote, the hyperlink itself (the blue underlined clickable link) should be removed. The text stays; the link goes.

**Determining which rule to apply:** This is the hardest part. The tool should analyze the surrounding sentence to determine whether the author name is part of the sentence grammar (subject, object, etc.) or is a standalone citation marker. Heuristics:
- If the citation text is inside parentheses → Rule 2
- If the citation text starts a sentence or follows a verb/preposition ("As X describes", "found by X") → Rule 1
- If the citation is a standalone hyperlink at the end of a sentence → Rule 3
- If the hyperlinked text is a proper noun / product name rather than author-date → Rule 4

When in doubt, keep the author name and add a Word comment saying "Review: should this author name be kept in the body text?"

### Step 6: Flagging via Word comments

Use Word comments (margin annotations) to flag issues. Comments should be attributed to author "cite2footnote" and should be used for:

- **No source URL found:** "⚠ Citation detected but no source URL. Please add a hyperlink to the source document so Bluebook formatting can be verified."
- **URL fetch failed:** "⚠ Could not access [URL] — citation formatted from display text only. Please verify."
- **Ambiguous text cleanup:** "⚠ Review: should the author name be kept in the body text here, or removed entirely?"
- **LLM low confidence:** "⚠ Bluebook formatting may be incorrect — please verify against the source."

The comment should be anchored to the relevant text span in the document.

### Step 7: Existing footnote conversion

For each pre-existing footnote:
1. Extract its text content.
2. If it contains a URL, fetch metadata from the URL.
3. Send the footnote text (+ any fetched metadata) to the LLM for Bluebook reformatting.
4. Replace the footnote content with the Bluebook version.
5. If the footnote is already in proper Bluebook format, the LLM should return it unchanged.

### Step 8: References section removal

If the document has a References section and it was used for citation matching:
1. Remove the entire References section (heading + all entries) from the output document.
2. The information now lives in the footnotes/endnotes.

This behavior is ON by default but can be disabled with `--keep-references`.

### Step 9: Supra / Id. short-form citations

After all footnotes have been inserted, make a second pass to apply Bluebook short-form rules for repeated sources. This requires tracking which sources have been cited and in which footnote.

**Data structure:** Maintain a citation ledger — a mapping from each unique source (keyed by a normalized identifier like author+title or DOI) to the footnote number where it was first cited in full.

**Rules:**

1. ***Id.***: If the immediately preceding footnote cites the same source, replace the full citation with *Id.* (or *Id.* at [page] if the page differs). "Immediately preceding" means the prior footnote in document order, with no intervening footnote citing a different source.

2. ***Supra***: If a source was cited in full in an earlier (non-immediately-preceding) footnote, replace the full citation with: `Author, *supra* note X`, where X is the footnote number of the first full citation. If the new citation references a specific page, append `, at [page]`.

3. **First occurrence**: The first time a source appears, always use the full Bluebook citation. This is what gets referenced by subsequent *supra* notes.

4. **Multiple authorities in one footnote**: If a footnote cites multiple sources (semicolon-separated), apply *Id.* only if ALL sources in the preceding footnote match. Otherwise, use *supra* for any previously cited source and full citation for new ones.

**Example sequence:**
```
Footnote 1: Ryan Calo, Artificial Intelligence Policy: A Primer and Roadmap, 51 U.C. DAVIS L. REV. 399 (2017).
Footnote 2: Id. at 405.
Footnote 3: Danielle Keats Citron & Frank Pasquale, The Scored Society, 89 WASH. L. REV. 1 (2014).
Footnote 4: Calo, supra note 1, at 410.
Footnote 5: Id.
```

**Edge cases:**
- If the tool can't confidently determine that two citations refer to the same source (e.g., slightly different author name spellings), it should use the full citation and add a Word comment: "⚠ This may be a repeated citation of [source in note X] — consider using supra."
- Signals like "See" and "See also" should be preserved before the short form: `See id.` or `See Calo, supra note 1.`

---

## Output

### Converted document (.docx)

- All detected citations converted to footnotes or endnotes
- Repeated citations use Bluebook short forms (*Id.* and *supra* note X)
- Inline text cleaned per the rules above
- Hyperlink formatting removed from citation text
- Word comments added for any flagged issues
- References section removed (unless `--keep-references`)

### Conversion report (.report.txt)

A plain-text file listing:
- Every citation detected, its type, and its source (URL, reference entry, or "no source")
- The original text → Bluebook conversion for each
- Any issues encountered (fetch failures, unmatched citations, ambiguous cleanup)
- Summary statistics (total citations, by type, number of issues)

---

## Warnings / README for users

The tool should print a clear warning at startup and include it in the report:

```
⚠ IMPORTANT — READ BEFORE USING OUTPUT

This tool converts social-science-style citations to Bluebook footnotes/endnotes.
It provides a strong first pass, but human verification is still required.

What it does:
  • Detects inline citations and converts them to footnotes/endnotes
  • Uses an LLM to generate Bluebook formatting
  • Fetches source URLs for metadata when available
  • Handles supra/id. short forms for repeated citations
  • Removes the References section (info is now in footnotes)
  • Cleans inline citation text from the body
  • Adds Word comments to flag anything it couldn't resolve

What it does NOT do:
  • Guarantee correct Bluebook formatting — citations should still be verified
  • Handle citations with no hyperlink or reference entry (these are flagged via comments)
  • Replace human editorial judgment on text cleanup

What to check:
  • All Word comments flagging issues (click through them in the margin)
  • Whether author names were correctly kept/removed from body text
  • Proper italicization, small caps, and signals (see, e.g., cf.)
  • Pin cites and page numbers
  • Supra/id. cross-references point to the correct footnote numbers
```

---

## Dependencies

- `python-docx` — reading/writing .docx, manipulating XML for footnotes and comments
- `anthropic` — Claude API for Bluebook conversion
- `requests` or `httpx` — fetching URLs for metadata
- `beautifulsoup4` — parsing fetched HTML for metadata extraction
- `lxml` — XML manipulation for Word document internals
- No other external dependencies

---

## Edge cases

- **Bracket spanning multiple Word runs**: A single `[Author (Year)](URL)` hyperlink may be split across multiple XML `<w:r>` elements due to formatting changes mid-word. The tool must reconstruct the full text across runs before classifying.
- **Multiple citations in one parenthetical**: `(Smith 2020; Jones 2021)` — split into separate footnotes or keep as one footnote with multiple authorities separated by semicolons. Prefer: one footnote, semicolon-separated.
- **Signal words**: Preserve Bluebook signals like "See", "See, e.g.,", "Cf.", "See generally" that precede the citation.
- **Supra/infra references**: If the same source is cited multiple times, subsequent references should ideally use short-form (*supra* note X). This is a stretch goal — the first version can repeat the full cite each time and flag it.
- **Malformed brackets/parentheses**: `[Vaishampayan et al. (2025](url))` — handle gracefully.
- **Google Docs artifacts**: Internal anchors like `#_hqe1036ucurq` and `#heading=h.262p5h6469y1` are Google Docs bookmark IDs that won't resolve as real URLs. Detect these and route to the references-matching logic instead.
- **Paywall / 403 on fetch**: Some journal URLs require institutional access. Fall back to display text + reference entry, flag in comment.
- **Non-English sources**: Pass through to LLM; Bluebook has rules for foreign-language sources.
- **Tables and text boxes**: Scan these too, not just body paragraphs.

---

## Acceptance criteria

1. **Dry run works**: `--dry-run` correctly identifies and classifies all citations in both test papers.
2. **Hyperlinked citations are converted**: Citations with external URLs produce footnotes with Bluebook text derived from fetched metadata.
3. **Internal-anchor citations are matched**: Citations pointing to a References section are resolved to full entries and converted.
4. **Parenthetical citations without links are flagged**: Word comments are added for citations with no source URL.
5. **Inline text is cleaned correctly**: Author names kept when grammatically needed; years and standalone parentheticals removed; hyperlink formatting removed.
6. **Existing footnotes are converted**: Pre-existing footnotes with bare URLs or non-Bluebook text are reformatted.
7. **References section is removed**: When the tool uses a References section for matching, it removes it from the output.
8. **Footnote/endnote choice works**: `--endnotes` flag produces endnotes instead of footnotes.
9. **Supra/id. short forms work**: When the same source is cited consecutively, the second footnote uses *Id.*; when cited non-consecutively, it uses *supra* note X.
10. **Word comments are properly inserted**: Flagged issues appear as margin comments navigable in Word.
11. **Report file is generated**: Comprehensive report covering all detections, conversions, and issues.
12. **Both test papers process without crashing**: The tool handles the full range of citation patterns across both real papers.

---

## What this tool is NOT

- Not a Bluebook validator. It generates a first draft.
- Not a replacement for a human editor. Every output must be checked.
- Not a citation manager (no persistent database of sources).
- It does not handle footnote-style input (documents already in Bluebook) — only social-science / parenthetical / hyperlinked citation styles.
- It does not modify the original file. Always writes to a new file.

---

## Stretch goals (not required for v1)

- **Parallel citation support**: For cases available in multiple reporters.
- **Interactive mode**: Instead of fully automatic, pause at each citation for user confirmation.
- **Batch processing**: Process a folder of .docx files at once.
