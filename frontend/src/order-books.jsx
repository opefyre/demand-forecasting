import React, { useEffect, useState } from "react";
import { Plus, Trash } from "@phosphor-icons/react";
import { t as uiText, unitLabel } from "./localization.mjs";
import { Actions, Grid, Stack, Disclosure, Collection, FieldGroup } from "./ui-layout.jsx";
import { forecastInputs } from "./forecast-start.mjs";

export function appendOrder(inputs) {
  const p=inputs.customers?.[0];
  if(!p)return inputs.orders;
  return [...inputs.orders,{reference:'',customer:p.customer,sku:p.sku,unit:p.unit,due_date:inputs.as_of,ordered:0,fulfilled:0,cancelled:0,status:'confirmed'}];
}
export function OrderTable({ inputs, ui, empty, onEdit, onRemove, disabled = false, renderDetails }) {
  const { Button, Table } = ui;
  return <Table headers={[uiText('Order line'),uiText('Customer / product'),uiText('Due date'),uiText('Ordered'),uiText('Already fulfilled'),uiText('Cancelled'),uiText('Status'),'']} empty={empty}>
    {inputs?.orders.map((row,index)=><React.Fragment key={index}>
      <tr><td>{row.reference||'—'}</td><td><strong>{row.customer}</strong><span className="ui-record-meta">{row.sku}</span></td><td>{row.due_date}</td><td>{row.ordered} {unitLabel(row.unit)}</td><td>{row.fulfilled} {unitLabel(row.unit)}</td><td>{row.cancelled} {unitLabel(row.unit)}</td><td>{uiText(row.status==='confirmed'?'Confirmed':row.status==='unconfirmed'?'Unconfirmed':'Cancelled')}</td><td><div className="ui-record-actions">
        {onEdit&&<Button disabled={disabled} aria-label={uiText('Edit order')+' · '+(row.reference||row.customer+' · '+row.sku)} onClick={()=>onEdit(index,row)}>{uiText('Edit')}</Button>}
        {onRemove&&<Button disabled={disabled} aria-label={uiText('Remove order')+' · '+(row.reference||row.customer+' · '+row.sku)} onClick={()=>onRemove(index)}><Trash/></Button>}
      </div></td></tr>
      {renderDetails?.(row,index)}
    </React.Fragment>)}
  </Table>;
}

export function OrderReview({ inputs, onChange, ui, canEdit = true, onEditingChange }) {
  const { Button } = ui;
  const [editing,setEditing]=useState(null);
  useEffect(()=>{onEditingChange?.(!!editing);return()=>onEditingChange?.(false);},[!!editing,onEditingChange]);
  const displayedInputs=editing?.index===inputs.orders.length?{...inputs,orders:[...inputs.orders,editing.row]}:inputs;
  return <Stack>
    <OrderTable inputs={displayedInputs} ui={ui} empty={!displayedInputs.orders.length&&uiText('No orders yet.')} disabled={!canEdit}
      onEdit={canEdit?(index,row)=>setEditing({index,row:{...row}}):undefined}
      onRemove={canEdit?index=>{onChange(inputs.orders.filter((_,i)=>i!==index));setEditing(null);}:undefined}
      renderDetails={(row,index)=>editing?.index===index&&<tr><td colSpan={8}><Stack>
        <OrderRows inputs={{...inputs,orders:[editing.row]}} ui={ui} canEdit={canEdit} showAdd={false} showRemove={false} onChange={rows=>setEditing({...editing,row:rows[0]})}/>
        <Actions><Button disabled={!canEdit} onClick={()=>setEditing(null)}>{uiText('Cancel')}</Button><Button kind="primary" disabled={!canEdit} onClick={()=>{const orders=[...inputs.orders];orders[index]=editing.row;onChange(orders);setEditing(null);}}>{uiText('Apply changes')}</Button></Actions>
      </Stack></td></tr>}/>
    {canEdit&&<Button disabled={!!editing||!inputs.customers?.length} onClick={()=>setEditing({index:inputs.orders.length,row:appendOrder({...inputs,orders:[]})[0]})}><Plus/>{uiText('Add order')}</Button>}
  </Stack>;
}
export function OrderRows({ inputs, onChange, ui, canEdit = true, showAdd = true, showRemove = true }) {
  const { Button, Pick, Field } = ui;
  const pairs = inputs.customers || [];
  function change(index, patch) {
    onChange(
      inputs.orders.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  }
  return (
    <Stack>
      {inputs.orders.map((row, index) => (
        <FieldGroup key={index}>
          <Grid>
            <Field title={uiText("Order line")}>
              <input
                value={row.reference}
                disabled={!canEdit}
                onChange={(e) => change(index, { reference: e.target.value })}
              />
            </Field>
            <Field title={uiText("Customer / product")}>
              <Pick
                label={uiText("Customer / product")}
                disabled={!canEdit}
                value={JSON.stringify([row.customer, row.sku, row.unit])}
                options={pairs.map((p) => [
                  JSON.stringify([p.customer, p.sku, p.unit]),
                  p.customer + " · " + p.sku,
                ])}
                onChange={(key) => {
                  const [customer, sku, unit] = JSON.parse(key);
                  change(index, { customer, sku, unit });
                }}
              />
            </Field>
            <Field title={uiText("Due date")}>
              <input
                type="date"
                disabled={!canEdit}
                value={row.due_date}
                onChange={(e) => change(index, { due_date: e.target.value })}
              />
            </Field>
            <Field title={uiText("Ordered")}>
              <input
                type="number"
                min="0"
                step="any"
                disabled={!canEdit}
                value={row.ordered}
                onChange={(e) => change(index, { ordered: e.target.value })}
              />
            </Field>
          </Grid>
          <Actions>
            <Disclosure title={uiText("Delivery & status")}>
              <Grid>
                {["fulfilled", "cancelled"].map((key) => (
                  <Field
                    key={key}
                    title={uiText(
                      key === "fulfilled" ? "Already fulfilled" : "Cancelled",
                    )}
                  >
                    <input
                      type="number"
                      min="0"
                      step="any"
                      disabled={!canEdit}
                      value={row[key]}
                      onChange={(e) => change(index, { [key]: e.target.value })}
                    />
                  </Field>
                ))}
                <Field title={uiText("Status")}>
                  <Pick
                    label={uiText("Status")}
                    disabled={!canEdit}
                    value={row.status}
                    options={["confirmed", "unconfirmed", "cancelled"].map(
                      (s) => [
                        s,
                        uiText(
                          s === "confirmed"
                            ? "Confirmed"
                            : s === "unconfirmed"
                              ? "Unconfirmed"
                              : "Cancelled",
                        ),
                      ],
                    )}
                    onChange={(status) => change(index, { status })}
                  />
                </Field>
              </Grid>
            </Disclosure>
            {showRemove&&<Button
              disabled={!canEdit}
              aria-label={uiText("Remove order")}
              onClick={() =>
                onChange(inputs.orders.filter((_, i) => i !== index))
              }
            >
              <Trash />
            </Button>}
          </Actions>
        </FieldGroup>
      ))}
      {showAdd&&<Button
        disabled={!canEdit || !pairs.length}
        onClick={() => {
          onChange(appendOrder(inputs));
        }}
      >
        <Plus />
        {uiText("Add order")}
      </Button>}
    </Stack>
  );
}

export function OrderBooks({ datasets, api, ui, canEdit,initialDatasetId }) {
  const { Button, Pick, Field, ErrorBox, Table, Modal } = ui;
  const sources = forecastInputs(datasets),
    [id, setId] = useState(sources.find(s=>s.id===initialDatasetId)?.id||sources[0]?.id || ""),
    [book, setBook] = useState(null),
    [saved, setSaved] = useState(false),
    [error, setError] = useState(null),
    [busy, setBusy] = useState(false),
    [editing,setEditing]=useState(null);
  useEffect(() => {
    let live = true;
    setBook(null);
    setSaved(false);
    setError(null);
    setEditing(null);
    if (id)
      api("/api/order-books/" + id)
        .then((v) => live && setBook(v))
        .catch((e) => live && setError(e));
    return () => {
      live = false;
    };
  }, [id]);
  const change = (field, value) => {
    setSaved(false);
    setBook((b) => ({ ...b, inputs: { ...b.inputs, [field]: value } }));
  };
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const { as_of, valid_until, order_feed, orders } = book.inputs;
      setBook(
        await api(
          "/api/order-books/" + id,
          { version: book.version, as_of, valid_until, order_feed, orders },
          "PUT",
        ),
      );
      setSaved(true);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
    <Collection label={uiText('Orders')} controls={
        <Pick
          label={uiText("Sales data")}
          value={id}
          options={sources.map((d) => [d.id, d.name])}
          onChange={setId}
          disabled={busy}
        />
      } actions={canEdit&&<><Button disabled={busy||!book?.inputs.customers?.length} onClick={()=>setEditing({index:book.inputs.orders.length,row:appendOrder({...book.inputs,orders:[]})[0]})}><Plus/>{uiText('Add order')}</Button><Button kind="primary" disabled={busy||!book} onClick={save}>{uiText(busy?'Saving…':saved?'Saved':'Save orders')}</Button></>}>
      <ErrorBox error={error} />
      <OrderTable inputs={book?.inputs} ui={ui} disabled={busy} empty={!id?uiText('Add sales history first.'):!book?uiText('Loading orders…'):!book.inputs.orders.length&&uiText('No orders yet.')} onEdit={canEdit?(index,row)=>setEditing({index,row:{...row}}):undefined} onRemove={canEdit?index=>change('orders',book.inputs.orders.filter((_,i)=>i!==index)):undefined}/>
      {book && (
        <Disclosure title={uiText('Order coverage')}>
          <Grid>
            <Field title={uiText("Orders correct as of")}>
              <input
                type="date"
                disabled={!canEdit || busy}
                value={book.inputs.as_of}
                onChange={(e) => change("as_of", e.target.value)}
              />
            </Field>
            <Field title={uiText("Review again after")}>
              <input
                type="date"
                disabled={!canEdit || busy}
                value={book.inputs.valid_until}
                onChange={(e) => change("valid_until", e.target.value)}
              />
            </Field>
            <Field title={uiText("Order coverage")}>
              <Pick
                label={uiText("Order coverage")}
                disabled={!canEdit || busy}
                value={book.inputs.order_feed}
                onChange={(v) => change("order_feed", v)}
                options={[
                  ["unknown", uiText("Orders not provided or incomplete")],
                  [
                    "complete_snapshot",
                    uiText("All known orders included — including none"),
                  ],
                ]}
              />
            </Field>
          </Grid>
        </Disclosure>
      )}
    </Collection>
    <Modal title={uiText(editing?.index===book?.inputs.orders.length?'Add order':'Edit order')} open={!!editing} onClose={()=>setEditing(null)}>
      {editing&&book&&<Stack>
        <OrderRows inputs={{...book.inputs,orders:[editing.row]}} ui={ui} canEdit={canEdit&&!busy} showAdd={false} showRemove={false} onChange={rows=>setEditing({...editing,row:rows[0]})}/>
        <Actions><Button onClick={()=>setEditing(null)}>{uiText('Cancel')}</Button><Button kind="primary" disabled={!canEdit||busy} onClick={()=>{const rows=[...book.inputs.orders];rows[editing.index]=editing.row;change('orders',rows);setEditing(null);}}>{uiText('Apply changes')}</Button></Actions>
      </Stack>}
    </Modal>
    </>
  );
}
