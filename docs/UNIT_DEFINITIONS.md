# Reviewed product-unit conversions

Implemented locally on 21 September 2026. This is a stock-outlook feature, not a
general conversion of forecast history, BOMs, currencies or production routing.

## User workflow

Settings → Product units → Add definitions. Enter exact product and unit labels,
the quantity in one stock unit, applicable stock dates, and the supporting
specification/reference. Identify real versus sample definitions and the reviewer.
Saving creates an immutable version. Create revised version copies the rules for
editing; it never changes the original. Unfinished form values stay in this
browser, with review confirmation reset on reopening.

Supply → Inventory → choose a stock snapshot → Unit definitions. Standard units
only is the default. Factory definitions are never selected implicitly. The
version applies to the stock snapshot date, not future forecast periods. Source
quantities are untouched. Conversion details retain source row, original and
converted quantity, stock status, factor, reference and version identity.

## Boundaries

- [Pint 0.25.2](https://pypi.org/project/Pint/0.25.2/) (BSD) performs standard
  conversions. A deliberately small exact-label allowlist covers mass, length
  and volume. No arbitrary unit expressions, ambiguous `ton`, currency conversion,
  automatic Persian translations, or casing guesses.
- A factory rule is one direction for one exact SKU and exact unit pair. No
  inferred inverse, chained conversions or global packaging assumptions.
- Positive finite factors and valid inclusive date ranges are required. Overlap
  for the same SKU/direction is rejected. Standard physical conversions cannot
  be overridden by a product definition.
- Missing or expired definitions leave stock unknown. Unknown stock quality stays
  unknown after conversion; held stock is converted but excluded from availability.
- Custom definitions, stock and forecast must have matching real/sample classes.
- Versions are stored in `data/units.sqlite3` with creation time, reviewer, parent,
  rules hash and library version. Local reviewer text is not authenticated approval.
- The live outlook is recalculated from explicitly selected inputs; it is not yet
  an immutable saved stock-plan artifact. Record input IDs to reproduce it.
- This does not add future receipts, stock reservations, safety/service targets,
  unit-aware BOM conversion, routing, or authentication. Those remain open.

## Verification

Seven additional automated tests (87 total) cover standard dimensions, ambiguous
labels, exact product/direction/date matching, overlap and invalid inputs,
immutable revisions, sample isolation, held/unknown stock, and API selection.

Saved through the UI: synthetic definition version
`236ed81223f9401aa0ca9b6bce4f8e4c`, one DEMO-PALLET = 2 tonnes for COA-ART-135.
This is not a client packing definition. The provided workbooks' BOB/بوبین and
blank/KBlank relationships remain unconfirmed and were not entered as rules.

`scripts/verify_units_sample.py` imports `sample_data/inventory_units_demo.csv`
and checks the selected version against run `01e6aa772eba`. Result snapshot
`5b4ebe0e718340b1a25fb797e609497d`: 1,000 × 2 = 2,000 usable tonnes; 125 × 2 =
250 held tonnes; closing 1,883.5086256178618 tonnes after September demand.
50,000 kg = 50 tonnes for PKG-KRAFT-120. Without the custom version, pallet-based
opening/closing remain unknown while the kg conversion still works.

Browser checks: definition entry and saving, exact version selection, unknown to
known balance transition, source evidence, product search, laptop/mobile layouts.
Client stock snapshot date and the meaning of Warehouse status remain unconfirmed.
