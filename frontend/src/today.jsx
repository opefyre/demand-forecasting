import React, { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowClockwise, CheckCircle } from "@phosphor-icons/react";

const dueWhen = (value) =>
  new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value + "T00:00:00Z"));

export function TodayPage({
  run,
  runs,
  plans,
  chosenPlan,
  setChosenPlan,
  openRun,
  onDecision,
  api,
  ui,
  canEdit,
}) {
  const { Button, Pick, ErrorBox, Help } = ui;
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0),
    [filter, setFilter] = useState("all"),
    [workflow, setWorkflow] = useState("active"),
    [editing, setEditing] = useState(null),
    [limit, setLimit] = useState(5);
  const queue = useRef(null);
  const candidates = plans.filter(
    (p) =>
      p.run_id === run?.run_id && ["approved", "published"].includes(p.status),
  );
  const planId = candidates.some((p) => p.id === chosenPlan) ? chosenPlan : "";
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    setFilter("all");
    setWorkflow("active");
    setEditing(null);
    setLimit(5);
    const query = new URLSearchParams();
    if (run) query.set("run_id", run.run_id);
    if (planId) query.set("plan_id", planId);
    api("/api/today?" + query)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [run?.run_id, planId, plans, revision]);
  const when = (value) =>
    value
      ? new Intl.DateTimeFormat("en", {
          month: "short",
          year: "numeric",
          ...(run?.run_settings?.frequency !== "monthly"
            ? { day: "numeric" }
            : {}),
          timeZone: "UTC",
        }).format(new Date(value))
      : "Not supplied";
  const decisions = data?.decisions || [];
  const visible = decisions
    .filter(
      (d) =>
        (filter === "all" || d.kind === filter) &&
        (workflow === "all" ||
          (workflow === "active"
            ? d.tracking?.status !== "reviewed"
            : workflow === "overdue"
              ? d.tracking?.overdue
              : d.tracking?.status === workflow)),
    )
    .sort(
      (a, b) =>
        Number(Boolean(b.tracking?.overdue)) -
        Number(Boolean(a.tracking?.overdue)),
    );
  const kinds = [
    ["all", "All"],
    ["review", "Reviews"],
    ["materials", "Materials"],
    ["capacity", "Capacity"],
    ["forecast", "Forecast"],
    ["data", "Inputs"],
  ];
  return (
    <>
      <div className="page-heading">
        <h1>Today</h1>
        <Button
          kind="primary"
          disabled={!data || !decisions.length}
          onClick={() => {
            setFilter("all");
            setWorkflow("active");
            queue.current?.focus();
            queue.current?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }}
        >
          Review decisions <ArrowRight size={18} />
        </Button>
      </div>
      {run && (
        <div className="view-toolbar today-context">
          <div className="today-selector">
            <span>Forecast</span>
            <Pick
              label="Forecast"
              value={run.run_id}
              onChange={(id) => openRun(id, "today")}
              options={runs
                .filter((r) => !r.scenario_name || r.run_id === run.run_id)
                .map((r) => [
                  r.run_id,
                  `${r.name} · ${when(r.summary?.end)}${
                    typeof r.created_at === "number"
                      ? " · " +
                        new Intl.DateTimeFormat("en", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                          timeZone: run?.site?.timezone || "Asia/Tehran",
                        }).format(new Date(r.created_at * 1000))
                      : ""
                  }`,
                ])}
            />
          </div>
          <div className="today-selector">
            <span>Use quantities from</span>
            <Pick
              label="Quantities"
              value={planId || "forecast"}
              onChange={(id) => setChosenPlan(id === "forecast" ? null : id)}
              options={[
                ["forecast", "Statistical forecast"],
                ...candidates.map((p) => [p.id, p.name]),
              ]}
            />
          </div>
          <Button
            onClick={() => setRevision((v) => v + 1)}
            aria-label="Refresh decisions"
          >
            <ArrowClockwise size={18} />
          </Button>
        </div>
      )}
      <ErrorBox error={error} />
      {error && (
        <Button onClick={() => setRevision((v) => v + 1)}>Try again</Button>
      )}
      {!data && !error && <p role="status">Checking saved evidence…</p>}
      {data && (
        <>
          {data.context && (
            <>
              <div className="today-scope">
                <span>
                  {data.context.frequency} · {data.context.unit} ·{" "}
                  {data.context.status === "forecast"
                    ? "Forecast quantities"
                    : `${data.context.status} plan`}
                </span>
              </div>
              <dl className="today-metrics">
                <div>
                  <dt>
                    Historical error{" "}
                    <Help text="Total absolute forecast error divided by actual demand on the separate test window. Lower is better; this is not a promise of future accuracy." />
                  </dt>
                  <dd>
                    {data.metrics.historical_error_pct == null
                      ? "Not verified"
                      : `${data.metrics.historical_error_pct.toFixed(1)}%`}
                  </dd>
                </div>
                <div>
                  <dt>
                    Materials below target{" "}
                    <Help text="Distinct materials with at least one period below the supplied stock target. This is not a stockout probability." />
                  </dt>
                  <dd>{data.metrics.materials_at_risk ?? "Not checked"}</dd>
                </div>
                <div>
                  <dt>Lines over capacity</dt>
                  <dd>{data.metrics.constrained_lines ?? "Not checked"}</dd>
                </div>
                <div>
                  <dt>
                    Last actual period{" "}
                    <Help text="Latest period in this forecast's saved history, not the upload or calculation date." />
                  </dt>
                  <dd>{when(data.context.last_actual_period)}</dd>
                </div>
              </dl>
            </>
          )}
          <section
            className="surface today-queue"
            aria-labelledby="decision-title"
          >
            <div className="today-queue-heading">
              <h2 id="decision-title" tabIndex={-1} ref={queue}>
                {workflow === "reviewed"
                  ? "Reviewed decisions"
                  : workflow === "all"
                    ? "Review queue"
                    : "Needs attention"}{" "}
                <span className="muted">{visible.length}</span>
              </h2>
              {decisions.length > 0 && (
                <div className="today-filters">
                  <Pick
                    label="Show decisions"
                    value={filter}
                    onChange={(value) => {
                      setFilter(value);
                      setLimit(5);
                    }}
                    options={kinds.filter(
                      ([key]) =>
                        key === "all" || decisions.some((d) => d.kind === key),
                    )}
                  />
                  <Pick
                    label="Review status"
                    value={workflow}
                    onChange={(value) => {
                      setWorkflow(value);
                      setLimit(5);
                    }}
                    options={[
                      ["active", "To review"],
                      ["in_progress", "In progress"],
                      ["overdue", "Overdue"],
                      ["reviewed", "Reviewed"],
                      ["all", "All statuses"],
                    ]}
                  />
                </div>
              )}
            </div>
            {!visible.length ? (
              <div className="today-clear">
                <CheckCircle size={24} />
                <p>
                  {decisions.length
                    ? "No decisions in this view."
                    : "No flags in the checks available for this forecast."}
                </p>
              </div>
            ) : (
              <ul className="decision-list">
                {visible.slice(0, limit).map((d) => (
                  <li key={d.id}>
                    <div>
                      <div className="decision-label">
                        {kinds.find(([key]) => key === d.kind)?.[1]}
                        {d.period && ` · ${when(d.period)}`}
                        {d.affected_periods > 1 &&
                          ` · ${d.affected_periods} periods`}
                      </div>
                      <h3>{d.title}</h3>
                      <p>{d.detail}</p>
                      {(d.tracking?.owner || d.owner) && (
                        <p className="decision-owner">
                          {d.tracking?.owner || d.owner}
                          {d.tracking?.due_date &&
                            ` · Due ${dueWhen(d.tracking.due_date)}`}
                          {d.tracking?.overdue && " · Overdue"}
                          {d.tracking?.status === "in_progress" &&
                            " · In progress"}
                          {d.tracking?.status === "reviewed" && " · Reviewed"}
                        </p>
                      )}
                      {d.tracking?.evidence_changed && (
                        <p>Evidence changed — review again.</p>
                      )}
                    </div>
                    <div className="row-actions">
                      <Button
                        onClick={() => onDecision(d.action)}
                        aria-label={`Review: ${d.title}`}
                      >
                        Review <ArrowRight size={17} />
                      </Button>
                      {data.context && (
                        <Button
                          onClick={() => setEditing(d)}
                          aria-label={`Manage review: ${d.title}`}
                        >
                          {canEdit
                            ? d.tracking?.version
                              ? "Update"
                              : "Assign"
                            : "Details"}
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {visible.length > limit && (
              <div className="today-more">
                <Button onClick={() => setLimit((v) => v + 5)}>
                  Show more ({visible.length - limit} remaining)
                </Button>
              </div>
            )}
          </section>
          {data.activity.length > 0 && (
            <section
              className="today-activity"
              aria-labelledby="activity-title"
            >
              <h2 id="activity-title">Recent plan activity</h2>
              <ul>
                {data.activity.map((event, index) => (
                  <li key={`${event.plan_id}-${event.at}-${index}`}>
                    <div>
                      <button
                        className="text-btn"
                        onClick={() =>
                          onDecision({ page: "plans", plan_id: event.plan_id })
                        }
                      >
                        {event.plan_name}
                      </button>
                      <p>{event.note}</p>
                      <span className="muted">
                        {event.actor || "Owner not recorded"}
                      </span>
                    </div>
                    <time dateTime={event.at}>
                      {event.at
                        ? new Intl.DateTimeFormat("en", {
                            month: "short",
                            day: "numeric",
                            timeZone: data.site.timezone,
                          }).format(new Date(event.at))
                        : "Date not recorded"}
                    </time>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      {editing && (
        <DecisionEditor
          key={editing.id}
          decision={editing}
          context={data.context}
          ui={ui}
          api={api}
          canEdit={canEdit}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            setRevision((v) => v + 1);
          }}
        />
      )}
    </>
  );
}

function DecisionEditor({
  decision,
  context,
  ui,
  api,
  canEdit,
  onClose,
  onSaved,
}) {
  const { Modal, Field, Pick, Button, ErrorBox, Help } = ui;
  const [form, setForm] = useState({
    owner: decision.tracking?.owner || decision.owner || "",
    due_date: decision.tracking?.due_date || "",
    status: decision.tracking?.status || "open",
    note: "",
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const attempt = useRef(null);
  return (
    <Modal
      title={decision.title}
      description={decision.detail}
      open
      onClose={onClose}
      dismissible={!busy}
    >
      <form
        className="decision-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const payload = {
            ...form,
            run_id: context.run_id,
            plan_id: context.plan_id,
            decision_id: decision.id,
            evidence_token: decision.evidence_token,
            version: decision.tracking?.version || 0,
          };
          const signature = JSON.stringify(payload);
          if (attempt.current?.signature !== signature)
            attempt.current = { signature, id: crypto.randomUUID() };
          try {
            await api("/api/decisions", {
              ...payload,
              request_id: attempt.current.id,
            });
            onSaved();
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <ErrorBox error={error} />
        <Field
          title="Owner"
          help="Name of the person expected to follow up. This does not grant access or confirm they accepted the assignment."
        >
          <input
            aria-label="Review owner"
            required
            maxLength={120}
            value={form.owner}
            disabled={!canEdit || busy}
            onChange={(e) => setForm({ ...form, owner: e.target.value })}
          />
        </Field>
        <div className="form-grid two">
          <Field title="Due date">
            <input
              aria-label="Review due date"
              type="date"
              required
              value={form.due_date}
              disabled={!canEdit || busy}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })}
            />
          </Field>
          <Field title="Status">
            <Pick
              label="Review status to save"
              value={form.status}
              disabled={!canEdit || busy}
              onChange={(value) => setForm({ ...form, status: value })}
              options={[
                ["open", "To do"],
                ["in_progress", "In progress"],
                ["reviewed", "Reviewed"],
              ]}
            />
          </Field>
        </div>
        <p className="muted">
          Reviewed means a decision was recorded. It does not change forecast or
          supply quantities.
        </p>
        {canEdit && (
          <Field title="Action or decision">
            <textarea
              aria-label="Action or decision"
              required
              minLength={3}
              maxLength={2000}
              rows={3}
              value={form.note}
              disabled={busy}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
            />
          </Field>
        )}
        {decision.tracking?.history?.length > 0 && (
          <details className="decision-history">
            <summary>Review history</summary>
            <ul>
              {[...decision.tracking.history].reverse().map((event, index) => (
                <li key={index}>
                  <strong>
                    {event.owner} · {event.status.replaceAll("_", " ")}
                  </strong>
                  <p>{event.note}</p>
                  <small>
                    {event.actor.name} · {new Date(event.at).toLocaleString()} ·
                    Due {dueWhen(event.due_date)}
                  </small>
                </li>
              ))}
            </ul>
          </details>
        )}
        <div className="row-actions">
          <Button type="button" disabled={busy} onClick={onClose}>
            Close
          </Button>
          {canEdit && (
            <Button kind="primary" disabled={busy}>
              {busy ? "Saving…" : "Save review"}
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}
