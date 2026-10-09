import {t as uiText} from './localization.mjs';
import React from 'react';
import {planningMonth} from './planning-calendar.mjs';
const quantity=v=>v==null?'Not present':new Intl.NumberFormat('en',{maximumFractionDigits:3}).format(v);
export function RepeatUploadReview({review,ui,basis='gregorian'}){
  if(!review)return null;
  const {Table}=ui;
  return <section className="ai-proposal" aria-label={uiText("Updated history comparison")}><h3>{uiText("What changed in this upload?")}</h3>
    <p>{review.message}</p>
    <p>{review.before_rows} → {review.after_rows}{' '}{uiText("sales rows ·")}{' '}{quantity(review.before_total)} → {quantity(review.after_total)} {review.unit}</p>
    <p>{review.added_groups}{' '}{uiText("added ·")}{' '}{review.changed_groups}{' '}{uiText("changed ·")}{' '}{review.removed_groups}{' '}{uiText("removed customer/product periods")}</p>
    {!!review.removed_periods.length&&<p role="alert">{uiText("Missing previous months:")}{' '}{review.removed_periods.map(p=>planningMonth(p,basis)).join(', ')}{uiText(". Upload full history if these removals are unintended.")}</p>}
    {review.same_file_contents&&<p>{uiText("The file contents are unchanged.")}</p>}
    {review.retained_factors&&<p>{uiText("Existing future-factor inputs are retained; check their dates before forecasting.")}</p>}
    {!!review.change_count&&<details><summary>{uiText("Review changed periods")}{review.truncated?uiText(" · first 120"):''}</summary><Table headers={[uiText("Customer/product"),uiText("Month"),uiText("Before"),uiText("After")]}>{review.changes.map((r,i)=><tr key={i}><td>{r.scope.join(' · ')||'All sales'}</td><td>{planningMonth(r.period,basis)}</td><td>{quantity(r.before)}</td><td>{quantity(r.after)}</td></tr>)}</Table></details>}
  </section>;
}
