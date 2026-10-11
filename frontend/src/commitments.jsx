import React,{useEffect,useState} from 'react';
import {Plus,Trash} from '@phosphor-icons/react';
import {Actions,Disclosure,Grid,Stack} from './ui-layout.jsx';
import {t as uiText,unitLabel,i18n} from './localization.mjs';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {commitmentPeriods,commitmentError} from './commitment-state.mjs';

export function Commitments({inputs,run,ui,onChange,canEdit=true,onEditingChange}){
  const {Button,Table,Field,Pick,ErrorBox,Help}=ui;
  const [editing,setEditing]=useState(null),[error,setError]=useState(null);
  const periods=commitmentPeriods(run),basis=planningBasis(run);
  useEffect(()=>{onEditingChange?.(!!editing);return()=>onEditingChange?.(false);},[!!editing,onEditingChange]);
  function change(patch){setEditing(value=>({...value,row:{...value.row,...patch}}));setError(null);}
  function apply(){const message=commitmentError(editing.row,inputs,periods,editing.index);
    if(message){setError(Error(uiText(message)));return;}
    const rows=[...inputs.commitments];rows[editing.index]={...editing.row,owner:editing.row.owner.trim(),reason:editing.row.reason.trim()};
    onChange(rows);setEditing(null);setError(null);
  }
  const rows=inputs.commitments;
  return <Disclosure title={uiText('Complete monthly commitments')}><Stack>
    {Help&&<Help text={uiText('The full monthly total, including orders and deliveries. It replaces the estimate for this customer and product; it is not added to orders.')}/>}
    <Table headers={['Customer / product','Month','Quantity','Owner','Review again after',''].map(label=>uiText(label))} empty={!rows.length&&uiText('No commitments')}>
      {rows.map((row,index)=><tr key={index}>
        <td>{row.customer}<span className="ui-record-meta">{row.sku}</span></td><td><bdi>{planningMonth(row.period,basis)}</bdi></td>
        <td>{row.quantity===''?'—':new Intl.NumberFormat(i18n.language,{maximumFractionDigits:3}).format(row.quantity)} {unitLabel(row.unit)}</td>
        <td>{row.owner||'—'}</td><td><bdi>{row.valid_until}</bdi></td><td><Actions>
          <Button disabled={!canEdit||!!editing} aria-label={uiText('Edit commitment')+' · '+row.customer+' · '+row.sku+' · '+planningMonth(row.period,basis)} onClick={()=>{setEditing({index,row:{...row}});setError(null);}}>{uiText('Edit')}</Button>
          <Button disabled={!canEdit||!!editing} aria-label={uiText('Remove commitment')+' · '+row.customer+' · '+row.sku+' · '+planningMonth(row.period,basis)} onClick={()=>onChange(inputs.commitments.filter((_,i)=>i!==index))}><Trash/></Button>
        </Actions></td></tr>)}
    </Table>
        {editing&&<Stack><ErrorBox error={error}/><Grid>
          <Field title={uiText('Customer / product')}><Pick label={uiText('Customer / product')} disabled={!canEdit} value={JSON.stringify([editing.row.customer,editing.row.sku,editing.row.unit])} options={inputs.customers.map(c=>[JSON.stringify([c.customer,c.sku,c.unit]),c.customer+' · '+c.sku])} onChange={key=>{const [customer,sku,unit]=JSON.parse(key);change({customer,sku,unit});}}/></Field>
          <Field title={uiText('Month')}><Pick label={uiText('Commitment month')} disabled={!canEdit} value={editing.row.period} options={periods.map(period=>[period,planningMonth(period,basis)])} onChange={period=>change({period})}/></Field>
          <Field title={uiText('Monthly total')}><input type="number" min="0" step="any" disabled={!canEdit} value={editing.row.quantity} onChange={e=>change({quantity:e.target.value})}/></Field>
          <Field title={uiText('Owner')}><input maxLength={160} disabled={!canEdit} value={editing.row.owner} onChange={e=>change({owner:e.target.value})}/></Field>
          <Field title={uiText('Reason')}><input maxLength={500} disabled={!canEdit} value={editing.row.reason} onChange={e=>change({reason:e.target.value})}/></Field>
          <Field title={uiText('Review again after')}><input type="date" min={inputs.as_of} disabled={!canEdit} value={editing.row.valid_until} onChange={e=>change({valid_until:e.target.value})}/></Field>
        </Grid><Actions><Button disabled={!canEdit} onClick={()=>{setEditing(null);setError(null);}}>{uiText('Cancel')}</Button><Button kind="primary" disabled={!canEdit} onClick={apply}>{uiText('Apply changes')}</Button></Actions></Stack>}
    {canEdit&&<Button disabled={!!editing||!inputs.customers.length||!periods.length} onClick={()=>{const customer=inputs.customers.find(c=>!c.series_id)||inputs.customers[0];
      setEditing({index:inputs.commitments.length,row:{customer:customer.customer,sku:customer.sku,unit:customer.unit,period:periods[0],quantity:'',owner:'',reason:'',valid_until:inputs.valid_until}});setError(null);
    }}><Plus/>{uiText('Add monthly commitment')}</Button>}
  </Stack></Disclosure>;
}
