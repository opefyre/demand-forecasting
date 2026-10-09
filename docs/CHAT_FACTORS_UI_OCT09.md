# Chat and Factors — 9 October 2026

- [x] User messages stay physically right; assistant messages stay physically left.
- [x] Persian text remains RTL; English text remains LTR, independent of app language.
- [x] Saved, pending and new messages use the same chat component.
- [x] Chat response tables wrap headings instead of clipping columns on laptop screens.
- [x] Chat text/table appearance has one owner in `ui-framework.css`; old page and RTL overrides removed.
- [x] Live factors, annual context, weather and saved observations use one `ConnectionRecord` layout and the existing shared Data table.
- [x] Icons, status dots, spacing and typography use global tokens. No inline styles added.
- [x] Source details, weather and factor files open in the existing centered modal.
- [x] Search includes every source type; imported observations remain accessible without a demo-only checkbox.
- [x] New labels translated into Persian.
- [x] 238 frontend tests pass; production build succeeds.
- [x] Browser checks: English/Persian chat, actual source chart, weather history, four saved observation files, source search and Connections.
- [x] 390px chat check: no document-width overflow; avatars retain the correct sides. Viewport restored afterward.
- [x] No browser errors observed. No new AI requests or external refreshes were needed.

## Connections checked

Data → Connections is the reviewed export-folder pipeline, not an ERP app marketplace.
One active demo connection, **Tehran sales export**, checks every 60 minutes.
It uses saved column mappings and content hashes, stages changed files for review,
and retains previous versions. Checks run while the server is running. A reviewed
version can create a forecast draft; it is not automatically approved or published.

Separate order-export and factor-observation folder pipelines are implemented.
The app also exposes upload, validation, saved-input and forecast-job APIs.
There is no configured real-client system, native SAP/Odoo/Dynamics connector,
or full database/HTTP ingestion pipeline. The older generic integration checks
only test connectivity; they do not import complete business data.

External feeds are managed under Factors: Servix FX, World Bank commodities and
annual Iran inflation/industry, NY Fed supply pressure, and Hormuz traffic.
NASA POWER weather is fetched on demand. IMF monthly Iran CPI is permission-gated.
Servix was configured but flagged behind during this check; successful prior
fetches are not presented as current quotes. Selecting a source still requires
appropriate history and reviewed future assumptions before it enters a forecast.

Proof: `docs/screenshots/chat-alignment-en.png`, `chat-alignment-fa.png`,
and `factors-unified.png`.
