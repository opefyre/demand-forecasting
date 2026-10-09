import { t as uiText, i18n } from "./localization.mjs";
import { persianHelpTopics } from "./locales/help-fa.mjs";
import React from "react";
import { Page } from "./ui-layout.jsx";

export function HelpPage({ navigate, importNew, canEdit }) {
  const topics =
    i18n.language === "fa"
      ? persianHelpTopics
      : [
          [
            "How do I start a forecast?",
            "Open Forecast → New forecast. Choose or import sales history, check the calendar and months ahead, select factors, and review customers and current orders in the same window. Choose one or more methods and run. Compare their results, filter by customer, product or month, and export. Orders are not counted twice.",
          ],
          [
            "Can the app prepare monthly drafts automatically?",
            "In Settings → Schedules, an administrator opens Monthly draft settings. Choose an original sales forecast, the day of its Persian or Gregorian planning month, months ahead and a method. Optionally choose its existing sales connection. Confirm draft calculation and enable the schedule. Checks run on Tehran time while the app server is running. Only reviewed history is used; new files and missing latest-month records stop calculation. Settings → Schedules shows the draft or the problem. Review external factors, current orders and changes before exporting. No forecast is automatically approved or sent to another system.",
          ],
          [
            "Can the assistant prepare several customers or products?",
            "Choose an existing forecast on Home and name the customers and products. Ask it to prepare a monthly batch. It opens the same review screen, restricted to those products, with saved profiles where available. If you provide all sources, methods, timing and future values, it can prepare one confirmation card and calculate after your approval. Missing values are never guessed; stale sources need attention in Data → Factors. Once calculated, open the result to review current orders and export. Other products keep their baseline.",
          ],
          [
            "Can different customers use different factors?",
            "Yes. In Forecast → Scenarios → Add forecast factors, choose a customer and product, then review its sources, timing, method and future values. Add another group when needed. Review the batch and calculate one monthly forecast. Each group is calculated separately; products you leave out keep their baseline. Review current orders afterwards, then export. Saving factor groups never copies or changes orders.",
          ],
          [
            "How do I refresh the monthly forecast?",
            "Choose Update forecast on Home or Forecast, or ask the Assistant to start a monthly update. Review complete sales history, calculate, optionally compare external factors, then review current orders. The app remembers your step. Review changes against the earlier forecast and export Excel, CSV or JSON. Original versions are unchanged. Connected factors are not applied without reviewing their timing and future assumptions. Exports are drafts, not company approvals.",
          ],
          [
            "What data do I need?",
            "Past sales with date, customer, SKU, quantity and unit. Choose Each customer & product when matching columns; no extra customer–SKU identifier is needed. Current orders need a delivery date, order reference, customer, SKU, quantity, fulfilled quantity and status. Keep names and units consistent. Two or more years of actual sales help test yearly patterns; short histories cannot prove seasonality.",
          ],
          [
            "Where do I add customers?",
            "Use Customers to add or import your list, including customers with no current orders. Link the products they buy. In Forecast → Update orders, choose “Use customer directory” to include active customer–product links in the next reviewed snapshot. Directory changes never rewrite saved forecasts.",
          ],
          [
            "Persian or Gregorian months?",
            "Choose the dates used in your file and the months used for planning when importing sales. Both calendars use their real month boundaries, including leap years. Dated sales can be regrouped into either calendar. Monthly totals cannot be reliably split into a different calendar; use matching months or supply dated transactions. Orders and actual-results files have their own date-calendar choice. Exports include the planning month and its exact Gregorian start and end dates.",
          ],
          [
            "What does sales history mean?",
            "Choose customer demand, shipped quantities or invoiced quantities when you know. Otherwise keep Recorded sales; the app does not pretend shipments prove all demand. If sales were lost because of shortages, the history may understate demand. Negative returns or corrections need an explicit choice: reject them, exclude them from gross sales, or subtract within their own customer/product/month. Original files are kept.",
          ],
          [
            "How are orders and estimates combined?",
            "For each customer, product and month, confirmed orders consume the calculated estimate. If the estimate is 10 tonnes and orders are 14, demand is at least 14. If orders are 6, the other 4 stay as expected demand. Orders from one customer never cancel another customer’s forecast. Already fulfilled quantities are shown separately and are not exported as future demand.",
          ],
          [
            "How do I update existing orders?",
            "Choose Update orders in Forecast. Your saved customers and orders are already loaded. Import only changed lines, or choose Full order book to replace all lines. Keep the same unique reference for each delivery line and send its full current quantities, not the difference. For cancellations, update the cancelled quantity and status; simply omitting a line from a changes file does not remove it. Check the before/after preview and save a new version. Older versions stay available.",
          ],
          [
            "Which forecasting method should I choose?",
            "Automatic selection compares available methods on held-back historical periods. You can also select a method yourself when calculating. Choices include recent averages, trends, seasonal patterns, methods for irregular demand and models that use extra factors. “How was this calculated?” shows the chosen method and its test results. A more complex method is not always more accurate.",
          ],
          [
            "Can the app decide which factors help?",
            "In Forecast → Scenarios, review relevant factors and choose Test which factors help. The app tests history-only methods, each factor and the combined set, separately for each customer/product. Two earlier test windows and a separate final check are required. Factors must improve earlier error by at least 5%; otherwise history and seasonality remain in use. Which factors helped? explains the frozen choice and the final check. Recently downloaded history with unverified past releases remains what-if only, not eligible for automatic accuracy-based selection.",
          ],
          [
            "How do Iran and external factors work?",
            "Data → Factors manages live Iran and global sources. Select them in New forecast → Factors, then review locations, historical coverage and future assumptions. Sources refresh while the server runs; each forecast keeps its exact reviewed version. Stale, missing or permission-restricted sources cannot be included. Downloaded history without verified release dates remains a what-if estimate, not proof of past accuracy. Exchange rates are in rials, not toman. Annual figures are background, not monthly inputs. War effects remain explicit assumptions, not an invented automatic demand multiplier.",
          ],
          [
            "Can I save factors for a customer or product?",
            "Open Customers → Factors. Save a customer default, or a product-specific profile. A product profile replaces—not adds to—the customer default. These are declarations of exposure, not future values or proof of accuracy. In a factor scenario, choose the saved profile; only its exact customer/product is affected. You still review current sources, timing and future assumptions. Ask the assistant to review the sources for that customer and product; it prepares the same review screen.",
          ],
          [
            "Can factor files update automatically?",
            "An administrator can use the connection icon beside an imported factor to connect one export in an approved folder. Select how often to check it. Keep the complete history with the same columns, dates and units. Refresh & review shows changes before you save a new version. Prepare forecast draft then lets you review timing and future assumptions before calculating. Automatic checks never approve data or replace forecasts.",
          ],
          [
            "How do I approve a forecast for my planning system?",
            "Open Sales forecast → Export demand → For planning. Name the receiving system and confirm whether it already has the customer orders. Review the monthly quantities and customer/product details, then submit. In Approvals, a different company reviewer approves the fixed version. Download Excel, CSV or JSON; this does not send anything to the ERP. New orders, expired inputs or a newer approved version block old planning downloads. Local sign-off is labelled Demo approved, not company approval.",
          ],
          [
            "How do I explore and export?",
            "In Forecast, filter customer, SKU and month. Switch Chart, Trend, Table, Monthly or Coverage. Monthly shows customer–product rows across months; Coverage separates no orders from missing data. Use Views to save your filters and layout for this order version. “Download view” exports the currently filtered table as CSV for review. “Export demand” creates planning files for the whole selected order version: choose expected demand only if your receiving system already has orders, otherwise include orders.",
          ],
          [
            "What can the assistant do?",
            "Start on Home: attach sales history or choose saved inputs. No forecast is needed first. Ask “Forecast Customer A for the next 10 months.” It checks inputs and prepares a run for your confirmation. On the result, ask to use a named saved order book; review all months before saving a separate demand draft. Open the dashboard to filter and export. Follow-up questions keep bounded recent context. AI chooses its model by task and asks permission before sharing data.",
          ],
          [
            "Can the assistant check my inputs?",
            "Ask “Check my sales data” or “Check formatting.” It can propose column mappings and exact formatting changes, such as outer spaces or Persian date/quantity digits. Review before/after cells and totals before saving a new version. It never invents missing sales, removes duplicates or guesses customer matches. Original files, orders and forecasts stay unchanged.",
          ],
          [
            "How do I update sales history?",
            "Ask the assistant to update history, or open Data → Review data → Upload files. Upload complete updated history, not just the newest month. Review added, changed and removed periods before saving. A replacement creates a new input version; old corrections do not carry into a different file. Calculate a new forecast and review current orders separately.",
          ],
          [
            "Why does a result say Unknown?",
            "A customer–product match, history or another required input is missing. Unknown does not mean zero. Fix the flagged data before using the output for planning. Sample forecasts are demonstrations, not evidence of real customer accuracy.",
          ],
        ];
  return (
    <Page title={uiText("Help")}>
      <section className="surface help-start">
        <h2>{uiText("Start here")}</h2>
        <ol>
          <li>
            <button onClick={() => navigate("data")}>{uiText("Data")}</button>
            <span>{uiText("Add sales history, customers and orders.")}</span>
          </li>
          <li>
            <button onClick={() => navigate("demand")}>
              {uiText("Forecast")}
            </button>
            <span>
              {uiText("Choose inputs, factors and methods in one window.")}
            </span>
          </li>
          <li>
            <button onClick={() => navigate("demand")}>
              {uiText("Review demand")}
            </button>
            <span>{uiText("Compare methods, filter results and export.")}</span>
          </li>
        </ol>
      </section>
      <section className="help-topics">
        {topics.map(([q, a]) => (
          <details key={q}>
            <summary>{q}</summary>
            <p>{a}</p>
          </details>
        ))}
      </section>
    </Page>
  );
}
