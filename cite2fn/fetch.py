"""URL fetching and metadata extraction for academic sources.

Fetches URLs and extracts bibliographic metadata from HTML meta tags,
OpenGraph tags, and structured data.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


# Domains that should be skipped (internal document links, not real URLs)
SKIP_DOMAINS = {"docs.google.com"}

# Known academic repositories with special handling
ARXIV_DOMAINS = {"arxiv.org"}
DOI_DOMAINS = {"doi.org", "dx.doi.org"}
SSRN_DOMAINS = {"ssrn.com", "papers.ssrn.com"}

# User agent to identify ourselves
USER_AGENT = "cite2footnote/0.1 (academic citation tool; +https://github.com/anitasrinivasan/cite2fn)"


def fetch_metadata_batch(
    urls: list[str],
    timeout: float = 10.0,
    delay: float = 0.5,
) -> dict[str, dict]:
    """Fetch metadata for a batch of URLs.

    Returns {url: metadata_dict} where metadata_dict contains:
    - title, authors, journal, year, volume, pages, doi, abstract
    - fetch_error: str if fetch failed

    Deduplicates URLs before fetching. Adds delay between requests.
    """
    # Deduplicate
    unique_urls = list(dict.fromkeys(urls))
    results: dict[str, dict] = {}

    for i, url in enumerate(unique_urls):
        if _should_skip(url):
            results[url] = {"fetch_error": "Skipped (internal document link)"}
            continue

        # Normalize arxiv URLs to abstract page for better metadata
        fetch_url = _normalize_url(url)

        try:
            metadata = _fetch_single(fetch_url, timeout)
            results[url] = metadata
        except Exception as e:
            results[url] = {"fetch_error": str(e)}

        # Rate limiting
        if i < len(unique_urls) - 1:
            time.sleep(delay)

    return results


def _should_skip(url: str) -> bool:
    """Check if a URL should be skipped (e.g., internal document links)."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return any(skip in domain for skip in SKIP_DOMAINS)


def _normalize_url(url: str) -> str:
    """Normalize URLs for better metadata extraction."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # arxiv: convert html/pdf URLs to abs URLs
    if any(d in domain for d in ARXIV_DOMAINS):
        # https://arxiv.org/html/2602.15785v1#bib.bib10 -> https://arxiv.org/abs/2602.15785v1
        m = re.search(r"arxiv\.org/(?:html|pdf)/(\d+\.\d+(?:v\d+)?)", url)
        if m:
            return f"https://arxiv.org/abs/{m.group(1)}"

    return url


def _fetch_single(url: str, timeout: float) -> dict:
    """Fetch a single URL and extract metadata."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "xml" not in content_type:
        return {"fetch_error": f"Non-HTML content type: {content_type}", "url": url}

    soup = BeautifulSoup(resp.text, "html.parser")
    metadata: dict = {"url": url}

    # 1. Try Highwire Press citation meta tags (used by most academic sites)
    _extract_highwire(soup, metadata)

    # 2. Try Dublin Core meta tags
    _extract_dublin_core(soup, metadata)

    # 3. Try OpenGraph tags
    _extract_opengraph(soup, metadata)

    # 4. Fallback to <title>
    if "title" not in metadata or not metadata["title"]:
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)

    return metadata


def _extract_highwire(soup: BeautifulSoup, metadata: dict) -> None:
    """Extract Highwire Press citation meta tags."""
    tag_map = {
        "citation_title": "title",
        "citation_journal_title": "journal",
        "citation_date": "date",
        "citation_year": "year",
        "citation_volume": "volume",
        "citation_issue": "issue",
        "citation_firstpage": "first_page",
        "citation_lastpage": "last_page",
        "citation_doi": "doi",
        "citation_pdf_url": "pdf_url",
        "citation_abstract": "abstract",
        "citation_publisher": "publisher",
    }

    for meta_name, field in tag_map.items():
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            metadata[field] = tag["content"]

    # Authors (can be multiple tags)
    authors = []
    for tag in soup.find_all("meta", attrs={"name": "citation_author"}):
        if tag.get("content"):
            authors.append(tag["content"])
    if authors:
        metadata["authors"] = authors

    # Extract year from date if not directly available
    if "year" not in metadata and "date" in metadata:
        year_match = re.search(r"(\d{4})", metadata["date"])
        if year_match:
            metadata["year"] = year_match.group(1)


def _extract_dublin_core(soup: BeautifulSoup, metadata: dict) -> None:
    """Extract Dublin Core meta tags."""
    dc_map = {
        "DC.title": "title",
        "DC.creator": "authors",
        "DC.date": "date",
        "DC.publisher": "publisher",
        "DC.identifier": "doi",
    }

    for meta_name, field in dc_map.items():
        if field in metadata:
            continue
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            value = tag["content"]
            if field == "authors":
                metadata[field] = [value]
            else:
                metadata[field] = value


def _extract_opengraph(soup: BeautifulSoup, metadata: dict) -> None:
    """Extract OpenGraph meta tags as fallback."""
    og_map = {
        "og:title": "title",
        "og:description": "abstract",
        "og:site_name": "journal",
    }

    for og_prop, field in og_map.items():
        if field in metadata:
            continue
        tag = soup.find("meta", attrs={"property": og_prop})
        if tag and tag.get("content"):
            metadata[field] = tag["content"]
