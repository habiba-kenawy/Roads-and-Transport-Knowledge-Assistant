# Roads and Transport Knowledge Assistant

Evidence-grounded Q&A backend over Dubai "Roads and Transport" legislation (FastAPI, LangChain, LangGraph, Pydantic).
Not legal advice. The corpus is not exhaustive and not guaranteed to be legally current.

> Work in progress. This README currently covers only data acquisition. Architecture, graph, chunking, fusion,
> reranking, persistence, middleware and limitations are added as each phase is built.

## Data acquisition (reproducing the corpus)

The corpus is every result of the portal's "Roads and Transport" primary-category filter (45 documents on the day it was collected;
the unfiltered portal listed 461). This is more than the 15-25 the assignment suggests: a deliberate choice.

### 1. Apply the category filter and save the results page (manual, one time)
1. Open the [Dubai Legislation Search Engine](https://dlp.dubai.gov.ae/en/Pages/LegislationSearch.aspx).
2. Tick **Roads and Transport** under the main categories (not "Traffic", which is a different category) and click Search.
3. Confirm the page says "45 Results Found" (the number may change if the portal is updated) and take a screenshot showing the ticked filter
   and the result count. Save it in `evidence/`.
4. Save the page (Ctrl+S, "Webpage, HTML only") into `data/source_pages/`. All results appear on a single page.

### 2. Build the manifest
```
python -I scripts/build_manifest.py "data/source_pages/Legislation Search Engine.html" data/manifest.csv
```
Writes one row per document: doc_id (`dlp-<portal item id>`), file_name, title, source_url, content_url, primary_category,
language, doc_type, number, year, authority, status, issue_date, retrieval_date, notes. Blank means "not available on the portal";
values are never guessed. `retrieval_date` is left blank here and filled in by step 3. Re-running keeps dates already recorded.

### 3. Download the PDFs
```
python -I scripts/download_pdfs.py data/manifest.csv data/raw data/download_log.csv
```
- Downloads only the URLs listed in the manifest (no searching or crawling), one at a time, 1 s apart.
- Up to 3 attempts per file with growing waits; a response counts only if it is HTTP 200 and starts with `%PDF`.
- Files already in `data/raw/` are skipped, so re-running is safe.
- Writes `data/download_log.csv` (downloaded / skipped_exists / failed, attempts, error, bytes) and fills `retrieval_date`
  in the manifest (today's date for new downloads; the file's write date for files that were already on disk).
- `data/raw/` is git-ignored because redistribution of the PDFs is not confirmed. The manifest is the way to re-acquire them.

### Setup used so far
Python 3.13.7 on Windows:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then fill in your own values; .env is git-ignored
```
`requirements.txt` pins direct dependencies only; LangChain/LangGraph and retrieval libraries are added in later phases.

### Known limitations of the data step
- `primary_category` is assigned from the filter that was applied; the portal results do not print a category on each record.
- `source_url` is the portal's own "View as HTML" link. The portal serves it as a raw Word-exported HTML file without the site's styling.
- Titles and file names are kept exactly as the portal publishes them (some contain typos or truncations).
- Document status (In Force / Not in Force ...) is copied from the portal and is not independently checked.
