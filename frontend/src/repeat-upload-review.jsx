import {t as uiText,unitLabel,i18n} from './localization.mjs';
import React from 'react';
import {planningMonth} from './planning-calendar.mjs';
import {Panel,DefinitionList,Disclosure} from './ui-layout.jsx';
const quantity=v=>v==null?uiText('Not present'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:3}).format(v);
export function RepeatUploadReview({review,ui,basis='gregorian'}){
  if(!review)return null;
  const {Table}=ui;
  return <Panel title={uiText("What changed in this upload?")} description={uiText('This replaces the full history in a new version; it is not appended. Original history and orders stay unchanged.')}>
    <DefinitionList rows={[
      [uiText('Sales rows'),`${quantity(review.before_rows)} → ${quantity(review.after_rows)}`],
      [unitLabel(review.unit),`${quantity(review.before_total)} → ${quantity(review.after_total)}`],
      [uiText('Added / changed / removed periods'),`${quantity(review.added_groups)} / ${quantity(review.changed_groups)} / ${quantity(review.removed_groups)}`],
    ]}/>
    {!!review.removed_periods.length&&<p role="alert">{uiText("Missing previous months:")}{' '}{review.removed_periods.map(p=>planningMonth(p,basis)).join(', ')}{uiText(". Upload full history if these removals are unintended.")}</p>}
    {review.same_file_contents&&<p>{uiText("The file contents are unchanged.")}</p>}
    {review.retained_factors&&<p>{uiText("Existing future-factor inputs are retained; check their dates before forecasting.")}</p>}
    {!!review.change_count&&<Disclosure title={<>{uiText("Review changed periods")}{review.truncated?uiText(" · first 120"):''}</>}><Table headers={[uiText("Customer/product"),uiText("Month"),uiText("Before"),uiText("After")]}>{review.changes.map((r,i)=><tr key={i}><td>{r.scope.join(' · ')||uiText('All sales')}</td><td>{planningMonth(r.period,basis)}</td><td>{quantity(r.before)}</td><td>{quantity(r.after)}</td></tr>)}</Table></Disclosure>}
  </Panel>;
}
