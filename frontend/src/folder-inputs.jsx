import {t as uiText,i18n} from './localization.mjs';
import React, { useEffect, useState } from "react";
import {Collection,SearchControl,Disclosure} from './ui-layout.jsx';

export function FolderInputs({ api, ui, datasets, canAdmin, onReview }) {
  const { Button, Field, Pick, ErrorBox, Table, Modal, Help } = ui;
  const [data, setData] = useState({ connections: [], approved_roots: [] });
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const [drafts,setDrafts]=useState({});
  const [search,setSearch]=useState(''),[loading,setLoading]=useState(true);
  const [form, setForm] = useState({
    name: "",
    path: "",
    dataset_id: "",
    minutes: 0,
    files: { history: "" },
    confirmed_local_access: false,
  });
  const refresh = () => api("/api/integrations/folders").then(setData);
  useEffect(() => {
    refresh().catch((e) => setError(e.message)).finally(()=>setLoading(false));
  }, []);
  const act = async (key, fn) => {
    setBusy(key);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e.message);
      await refresh().catch(()=>{});
    } finally {
      setBusy("");
    }
  };
  const template = datasets.find((d) => d.id === form.dataset_id);
  const matching=data.connections.filter(c=>c.name.toLowerCase().includes(search.toLowerCase()));
  return (
    <>
    <Collection label={uiText('Connections')} controls={<SearchControl label={uiText('Search connections')} value={search} onChange={setSearch}/>} actions={canAdmin && (
          <Button kind="primary" disabled={!!busy} onClick={() => setOpen(true)}>
            {uiText("Connect folder")}
          </Button>
        )}>
      {!open&&<ErrorBox error={error} />}
      <Table headers={[uiText('Name'),uiText('Status'),uiText('Last checked'),'']} empty={loading?uiText('Loading connections…'):!matching.length&&(search?uiText('No matching connections.'):uiText('No export folders connected. Your administrator can connect a local ERP export folder.'))}>
      {matching.map((connection) => {
        const latest=connection.checks[0];
        return <tr key={connection.id}>
          <td><strong>{connection.name}</strong><Disclosure title={uiText('Refresh history')}>
            {canAdmin&&!!connection.minutes&&<label className="ui-check"><input type="checkbox" checked={!!connection.auto_draft} disabled={!!busy} onChange={e=>act(connection.id,()=>api(`/api/integrations/folders/${connection.id}/auto-draft`,{enabled:e.target.checked}))}/>{uiText('Create drafts after input review')}<Help text={uiText('On each scheduled check, reviewed, unchanged inputs can create one draft. New files require review. Pausing stops checks and new drafts, not jobs already running. Orders are not copied and forecasts are never published automatically.')}/></label>}
            <ul>{connection.checks.map(check=><li key={check.id}>{new Date(check.checked*1000).toLocaleString(i18n.language==='fa'?'fa-IR-u-ca-gregory':'en-GB')} — {uiText(check.message)}{check.draft_message&&<span> — {uiText(check.draft_message)}</span>}</li>)}</ul>
          </Disclosure></td>
          <td>{uiText(latest?.message||'Not checked yet')}<span className="ui-record-meta">{connection.enabled?uiText('Checks every {{count}} minutes',{count:connection.minutes}):uiText('Automatic checks off')}</span>{drafts[connection.id]&&<span className="ui-record-meta" role="status">{drafts[connection.id].state==='succeeded'?uiText('This input version already has a completed forecast.'):['failed','cancelled','interrupted'].includes(drafts[connection.id].state)?uiText('This forecast stopped. Use Retry in the forecast activity bar.'):uiText('Draft requested. Follow its progress in the forecast activity bar.')} {uiText('Repeating this request will not create another copy. Orders are not copied automatically.')}</span>}</td>
          <td>{latest?new Date(latest.checked*1000).toLocaleString(i18n.language==='fa'?'fa-IR-u-ca-gregory':'en-GB'):uiText('Not checked yet')}</td>
          <td><div className="ui-record-actions">
            {canAdmin&&<Button disabled={!!busy} onClick={()=>act(connection.id,()=>api(`/api/integrations/folders/${connection.id}/check`,{}))}>{busy===connection.id?uiText('Checking…'):uiText('Check now')}</Button>}
            {connection.candidate_id&&<Button disabled={!!busy} onClick={()=>act('review',()=>onReview(connection.candidate_id))}>{connection.accepted_dataset_id?uiText('View saved data'):latest?.state==='failed'?uiText('Review last valid inputs'):uiText('Review inputs')}</Button>}
            {canAdmin&&connection.accepted_dataset_id&&<Button disabled={!!busy} onClick={()=>act(connection.id,async()=>{const job=await api(`/api/integrations/folders/candidates/${connection.candidate_id}/forecast`,{});setDrafts(v=>({...v,[connection.id]:job}));})}>{uiText('Create draft forecast')}</Button>}
            {canAdmin&&!!connection.minutes&&<Button disabled={!!busy} onClick={()=>act(connection.id,()=>api(`/api/integrations/folders/${connection.id}/enabled`,{enabled:!connection.enabled}))}>{connection.enabled?uiText('Pause'):uiText('Resume')}</Button>}
          </div></td>
        </tr>;
      })}
      </Table>
    </Collection>
    <Modal title={uiText('Connect folder')} open={open} onClose={()=>!busy&&setOpen(false)}>
      <ErrorBox error={error}/>
        <form
          className="ui-stack"
          onSubmit={(e) => {
            e.preventDefault();
            act("create", async () => {
              await api("/api/integrations/folders", {
                ...form,
                classification:template?.settings?.source_classification||'user_provided',
                files: Object.fromEntries(
                  Object.entries(form.files).filter(([, name]) => name),
                ),
              });
              setOpen(false);
            });
          }}
        >
          <Field title={uiText("Connection name")}>
            <input
              aria-label={uiText("Connection name")}
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field title={uiText("Use this reviewed mapping")}>
            <Pick
              label={uiText("Reviewed mapping")}
              value={form.dataset_id}
              options={[
                ["", uiText("Choose saved data")],
                ...datasets.filter(d=>!d.sources.operations&&!d.scenario_provenance).map((d) => [d.id, d.name]),
              ]}
              onChange={(value) =>
                setForm({ ...form, dataset_id: value, files: { history: "" } })
              }
            />
          </Field>
          <Field title={uiText("Export folder")}>
            <input
              aria-label={uiText("Export folder")}
              required
              placeholder={uiText("Absolute folder path")}
              value={form.path}
              onChange={(e) => setForm({ ...form, path: e.target.value })}
            />
            <small>{uiText("Approved locations:")}{" "}
              {data.approved_roots.join(", ") ||
                "Ask your administrator to configure one."}
            </small>
          </Field>
          {["history", "future"]
            .filter((role) => role === "history" || template?.sources[role])
            .map((role) => (
              <Field
                key={role}
                title={uiText(
                  {
                    history: "History filename",
                    future: "Future factors filename (optional)",
                    operations: "Production filename (optional)",
                  }[role]
                )}
              >
                <input
                  required={role === "history"}
                  placeholder={uiText("Exact filename, including extension")}
                  aria-label={`${role} export filename`}
                  value={form.files[role] || ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      files: { ...form.files, [role]: e.target.value },
                    })
                  }
                />
              </Field>
            ))}
          <Field title={uiText("Check for changes")}>
            <Pick
              label={uiText("Check for changes")}
              value={String(form.minutes)}
              options={[
                ["0", uiText("When I click Check now")],
                ["15", uiText("Every 15 minutes")],
                ["60", uiText("Every hour")],
                ["360", uiText("Every 6 hours")],
                ["1440", uiText("Every day")],
              ]}
              onChange={(value) => setForm({ ...form, minutes: Number(value) })}
            />
          </Field>
          <label className="ui-check">
            <input
              type="checkbox"
              required
              checked={form.confirmed_local_access}
              onChange={(e) =>
                setForm({ ...form, confirmed_local_access: e.target.checked })
              }
            />{uiText("I allow this app to read these exports from this folder.")}</label>
          <Button kind="primary" disabled={!!busy || !form.dataset_id}>
            {busy === "create" ? uiText("Connecting…") : uiText("Save connection")}
          </Button>
        </form>
    </Modal>
    </>
  );
}
