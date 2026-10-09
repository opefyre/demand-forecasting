# Tehran sales demo

Open http://127.0.0.1:8010/forecast and choose **Tehran · sales plan**.
Select **Automatic**, or use **Compare methods** to show four methods together.
Filter by customer, product and month. **Monthly** shows the full planning grid;
**Coverage** shows confirmed orders and demand still to come.

## Business inputs

Fictional packaging-paper business in Tehran: five customers, four products and
18 customer/product relationships. Established customers have 48 months of demand;
the newer customer has 18 months, with no invented zero history before acquisition.
Each calendar has 804 history rows, 79 order lines and 12 future months.
Quantity is customer demand in tonnes, not revenue, production or stock.

Find the directory, orders, history, factors and connected feed under **Data**.
The generated input files are in `sample_data/tehran-sales-demo/`.

## Saved scenarios

- **Sales plan:** five customers; automatic, weighted average, linear-with-factors and boosted-tree methods.
- **Persian-month plan:** true Persian monthly boundaries, with three methods.
- **Established-customer seasonal comparison:** four customers, seasonal methods and guarded factor testing. The newer buyer is deliberately excluded from this test.
- **Live market sensitivity:** real World Bank Brent observations and NY Fed supply-pressure data enter two models. Future market conditions are explicit assumptions.
- **Current FX sensitivity:** the captured Servix USD/IRR reference quote is held as a future what-if assumption. This is not a prediction of future rates or the factory's settlement rate.
- **Currency and freight stress:** assumed +20% exchange rate, +18% inflation, +80% import delay and +12% selling prices. Not a claim about actual war or market events.
- **Confirmed monthly contract:** Caspian confirms its entire October demand for four products. The model does not add extra forecast to these complete commitments.
- **July–September retrospective check:** 54 closed customer/product/month comparisons. Issued now, so labelled retrospective—not a fake historical forecast.

## Useful demonstrations

- Mehr's November orders exceed expected demand: orders win, without double-counting.
- Simin orders only in selected months: the forecast fills the other months.
- Aftab has no orders: demand is still calculated, including irregular specialty purchases.
- Negin is a newer customer: short-history limits stay honest.
- Some orders are fulfilled, partially cancelled, tentative or fully cancelled.
- The contract case shows the difference between partial orders and a complete monthly commitment.

**Home** has three real assistant conversations: monthly totals, customer order
coverage and a Persian explanation. **Approvals** has two local demo approvals
and one pending review. Nothing is sent to a real ERP or MRP system.

## Live sources and limitations

All six enabled feeds refreshed successfully. World Bank Brent and NY Fed supply
pressure are used in the live scenario; Servix is used in the current-FX what-if.
Refreshes preserve source versions and do not silently overwrite saved forecasts.
The local business-input connection checks hourly while the app is running.

Iran monthly CPI is not fetched without the required source reuse permission.
Demo inflation, payment terms, promotions, prices, delays and disruption history
are fictional inputs. Annual Iran data, Hormuz traffic and NASA weather are regional
context—not automatically repeated monthly or assigned invented sales effects.

Uncertainty bands are shown where historical evidence supports them. No joint
all-customer band is invented for the newer buyer, and revised live-factor what-ifs
have no claimed historical accuracy or calibrated intervals. These synthetic results
do not establish accuracy on the client's real data or prove causal effects.

## Evidence and recovery

`outputs/tehran-sales-demo/manifest.json` records input IDs, source versions,
16 model/scenario runs, 96 demand exports, workbooks and independent checks.
Export modes separate combined demand from additional demand not yet ordered;
both exclude already fulfilled quantities from the amount still to supply.
There are also approved handoff files and a retrospective comparison export.

Previous app records were moved to
`outputs/tehran-sales-demo/previous-state-20261009T142612Z/originals/`.
The same folder contains a verified checksummed workspace backup.
Original client spreadsheets and credentials were retained.
