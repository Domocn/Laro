# Cookbook & book recipe intake

How recipes from **physical / PDF cookbooks** get into Laro today, and the planned
path that avoids photographing every page.

## What works today

| Path | Surface | Notes |
|------|---------|--------|
| **Text PDF cookbook** | Quick Add / Import → PDF, Meal Planner PDF | `POST /ai/import-recipe-pdf` + `POST /ai/import-pdf` split multi-recipe text PDFs; tags `needs-review` + `imported-pdf` |
| **Scanned / image-only PDF** | Same PDF UI | When the text layer is empty, pages are rasterized (`pymupdf`, cap `SCANNED_PDF_MAX_PAGES` default 5) and sent through vision OCR (one AI quota use). Tags `needs-review` + `imported-pdf` + `scanned-pdf` |
| **Weekly meal-plan PDF** | Meal Planner | Same PDF pipeline; schedules the week when structure matches (text-layer only) |
| **Cookbook page photos** | Quick Add → Photos / Android Scan | `POST /ai/extract-from-images` — up to **20** pages (batched); each distinct dish is a recipe; optional `cookbook_id` attach |
| **Cookbook shelf + ISBN** | Cookbooks | Metadata only (title/author/notes). ISBN lookup via `GET /cookbooks/lookup?isbn=` (alias `GET /cookbooks/isbn/{isbn}`). Google Books then Open Library. Does **not** fetch chapter recipes |
| **Legal buy / borrow links** | Cookbooks search | Open Library + storefront search links only (no pirate sources) |
| **Attach to cookbook** | Quick Add photo/PDF | Optional cookbook + page number; persisted as `cookbook_id` / `cookbook_page` / `source_type=cookbook` on save |

Cookbooks in Laro are a **library organiser**, not a rights-cleared recipe corpus.
ISBN / Open Library fills bibliographic fields; it does not unlock book text.

## Gaps vs “no per-page photos”

Users with a paper book still need either:

1. A **text-layer PDF** (or ebook export) → bulk PDF import (best path today), or
2. **Photos / scans** → vision OCR (up to 5 pages per call), or
3. Manual entry / paste.

There is **no** chapter-by-ISBN recipe fetch (copyright). Scanned PDF OCR is an MVP
(page-capped); very long scans should be split or photographed in batches.

## Recommended phases

### Phase A — foundations (shipped)

- Prefer **text PDF** import for digital cookbooks and meal-plan PDFs.
- Document ISBN as metadata-only.
- Dietary + preferred-site prefs feed AI recipe ideas (separate from books).

### Phase B — better photo/PDF OCR (shipped MVP)

1. Pass **all** uploaded page images into vision for `extract-from-images`.
2. Render image-only PDF pages → same vision path (page cap + quota).
3. Attach imported recipes to a cookbook + optional page; mark `needs-review`.

### Phase C — guided book workflow

1. Optional user-supplied chapter outline (typed), then paste/PDF/OCR per chapter.
2. Never scrape commercial ebook stores or copyrighted APIs for full text.

## Practical advice for users (now)

1. If you have a **searchable PDF** of recipes you own → Import PDF (recipes).
2. If you have a **scanned PDF** → same Import PDF (first N pages OCR'd; raise
   `SCANNED_PDF_MAX_PAGES` on self-host if needed, max 10).
3. If you have a **meal-plan PDF** → Meal Planner → PDF.
4. Paper book → photograph up to 5 pages per recipe (Quick Add → Photos), or type/paste.
5. Add the book to **Cookbooks** with ISBN for your shelf; attach on import when easy.
