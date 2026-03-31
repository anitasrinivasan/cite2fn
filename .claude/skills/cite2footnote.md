---
name: cite2footnote
description: Convert social-science citations in a Word document to Bluebook-formatted footnotes or endnotes
triggers:
  - bluebook
  - footnote
  - endnote
  - citation
  - cite2fn
  - convert citations
---

# cite2footnote

Convert social-science-style citations (parenthetical, hyperlinked, inline author-date) in a .docx document to Bluebook-formatted footnotes or endnotes.

## When to use

When the user provides a .docx file and asks to convert citations to Bluebook footnotes/endnotes, or mentions "bluebook", "footnote", "endnote", or "citation conversion".

## Workflow

### Step 1: Detect citations

Run citation detection on the input document:

```bash
cd /Users/anitasrinivasan/cite2fn && python3 -m cite2fn.cli detect "<input.docx>"
```

This outputs JSON with all detected citations. Present a summary to the user:
- Count by type (hyperlink_external, hyperlink_internal, parenthetical, inline_author_date, existing_footnote)
- List any citations with issues (no URL, no year, etc.)
- Ask if the user wants footnotes or endnotes

### Step 2: Parse references (if applicable)

If the document has internal-anchor hyperlinks or parenthetical citations without URLs, parse the references section:

```bash
cd /Users/anitasrinivasan/cite2fn && python3 -m cite2fn.cli parse-references "<input.docx>"
```

Match citations to reference entries to get full bibliographic information.

### Step 3: Fetch URL metadata

For citations with external URLs, fetch metadata:

1. Write the list of unique URLs to a temp JSON file
2. Run: `cd /Users/anitasrinivasan/cite2fn && python3 -m cite2fn.cli fetch-urls <urls.json>`
3. This returns metadata (title, authors, journal, year, etc.) for each URL

### Step 4: Format citations in Bluebook

For each citation, use ALL available information to generate proper Bluebook formatting. You have:
- Display text from the document
- URL and fetched metadata (title, authors, journal, year, DOI)
- Matched reference entry text (from References section)
- Surrounding sentence context

Apply these Bluebook 21st edition rules:
- **Journal articles**: Author, *Title*, Volume JOURNAL First_Page (Year).
- **Books**: AUTHOR, TITLE Page (Publisher Year).
- **Web/online sources**: Author, *Title*, SITE NAME (Date), URL.
- **Cases**: *Case Name*, Volume Reporter Page (Court Year).

Set confidence to "needs_review" if information is insufficient. Prefix with [NEEDS MANUAL FORMATTING] if you can't confidently format.

Output the citations as a JSON list with `bluebook_text` and `confidence` filled in for each.

### Step 5: User review

Present the formatted citations to the user in a clear table:
- Original display text → Bluebook formatted text
- Flag any "needs_review" items
- Ask for corrections before proceeding

### Step 6: Assemble the document

Write the final citations JSON and run assembly:

```bash
cd /Users/anitasrinivasan/cite2fn && python3 -m cite2fn.cli assemble "<input.docx>" <citations.json> -o "<output.docx>" [--endnotes] [--keep-references]
```

This will:
- Insert footnotes/endnotes with Bluebook text
- Clean inline text (remove years, parentheticals, hyperlink formatting)
- Add Word comments for flagged issues
- Apply supra/id. short forms for repeated sources
- Remove the References section (unless --keep-references)

### Step 7: Report results

Show the user:
- Number of footnotes inserted
- Number of existing footnotes converted
- Number of comments added
- Any issues encountered
- Path to the output file

## Important notes

- Always work on a COPY of the document (the assemble command writes to a new file)
- The original file is never modified
- Print the standard warning about human verification being required
- If the document has no citations detected, inform the user and stop
