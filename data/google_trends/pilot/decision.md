# Search-form pilot (United Kingdom, fetched 2026-11-15)

Question: should a fabric or colour be searched as the plain word inside Google's Apparel category
(form a, e.g. "satin" with category 68 "Apparel"), or as the word with a typical garment in all categories
(form b, e.g. "satin dress")?

## Data
- `GB_a_fabrics.csv`, `GB_a_colours.csv`: form a, category 68 (the page label reads "Apparel").
- `GB_b_fabrics.csv`, `GB_b_colours.csv`: form b, category 0.

## Results (from `scripts/pilot_compare.py`)

| plain | garment | corr. (all months) | corr. (seasonal shape) | Nov bump plain | Nov bump garment |
|---|---|---|---|---|---|
| satin | satin dress | 0.85 | 0.11 | 1.11 | 1.10 |
| cotton | cotton dress | 0.84 | 0.87 | 1.09 | 0.97 |
| denim | denim jacket | 0.69 | 0.97 | 0.94 | 0.97 |
| velvet | velvet dress | 0.98 | 0.99 | 1.22 | 1.35 |
| linen | linen trousers | 0.99 | 0.99 | 0.93 | 0.88 |
| black | black dress | 0.80 | 0.86 | 1.15 | 1.11 |
| white | white dress | 0.89 | 0.81 | 1.05 | 0.88 |
| beige | beige dress | 0.75 | -0.30 | 1.00 | 1.00 |
| red | red dress | 0.85 | 0.84 | 1.02 | 1.05 |
| camel | camel coat | 0.71 | 0.88 | 1.17 | 1.13 |

Both forms pass the quality checks for these terms and mostly move together.

## Related searches (form a, Apparel, rising queries, top 5)
- jersey: "ronaldo jersey", "kobe bryant jersey", "chrome hearts jersey" (football/basketball shirts, not the fabric)
- crepe: "air max 1 crepe hemp", "nike air max 1 crepe" (a trainer model, not the fabric)
- camel: "demonia camel 311" (a boot model) next to "camel puffer coat"
- lace: "balenciaga speed lace up", "lace and favour" (lace-up shoes, a shop) next to "lace corset top"
- navy: "navy wide leg trousers", "navy trousers women" (clothing, fine)

## Decision
- Fabrics, colours, styles and runway details use form b (word + typical garment, all categories).
  The plain word picks up brand and product names even inside the Apparel category, and form b matches the
  41 items already on the site.
- Garments are single garment words, so they are searched as the plain word inside the Apparel category (68),
  which keeps out meanings such as "dress code" or "coat of arms".
- Denmark: the Danish and the English term are fetched in the same request; the Danish term is used when it passes
  the quality checks, otherwise the English one.
