import {t as uiText} from './localization.mjs';
import React, { useEffect, useRef, useState } from "react";
import {Stack,Grid,Actions} from './ui-layout.jsx';

export function WeatherContext({ api, ui, fmt }) {
  const locationInput = useRef(null);
  const { Button, Field, Pick, Table, ErrorBox } = ui;
  const [snapshots, setSnapshots] = useState([]);
  const [selected, setSelected] = useState("");
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (editing) locationInput.current?.focus();
  }, [editing]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    location_name: "",
    latitude: "",
    longitude: "",
    start: "",
    end: "",
    share_coordinates: false,
  });
  useEffect(() => {
    api("/api/weather")
      .then((data) => setSnapshots(data.snapshots))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  const snapshot = snapshots.find((row) => row.id === selected) || snapshots[0];
  const update = (key, value) =>
    setForm((previous) => ({
      ...previous,
      [key]: value,
      share_coordinates: key === "share_coordinates" ? value : false,
    }));
  async function fetchWeather(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await api("/api/weather/refresh", {
        ...form,
        latitude: form.latitude === "" ? null : Number(form.latitude),
        longitude: form.longitude === "" ? null : Number(form.longitude),
      });
      setSnapshots((previous) => [
        next,
        ...previous.filter((row) => row.id !== next.id),
      ]);
      setSelected(next.id);
      setEditing(false);
      setForm((previous) => ({ ...previous, share_coordinates: false }));
      setMessage(
        next.cache_reused
          ? "Using the saved copy from the last 24 hours; no new request was sent."
          : "Weather history saved. Your forecast has not been changed.",
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Stack>
      <Actions>
        {!editing && (
          <Button
            onClick={() => {
              setEditing(true);
              setError("");
              setMessage("");
            }}
          >
            Choose location & dates
          </Button>
        )}
      </Actions>
      <ErrorBox error={error} />
      {message && (
        <p className="inline-message" role="status">
          {message}
        </p>
      )}
      {loading && <p role="status">Loading saved weather…</p>}
      {editing && (
        <form className="ui-stack" onSubmit={fetchWeather}>
          <Field
            title="Location name"
            help="Use the actual plant or a clearly named comparison location. A city name does not identify the factory coordinates."
          >
            <input
              aria-label="Weather location name"
              ref={locationInput}
              required
              minLength={3}
              maxLength={120}
              value={form.location_name}
              onChange={(e) => update("location_name", e.target.value)}
            />
          </Field>
          <Grid>
            <Field
              title="Latitude"
              help="Decimal degrees from −90 to 90. No factory location is guessed."
            >
              <input
                aria-label="Weather latitude"
                required
                type="number"
                step="any"
                min="-90"
                max="90"
                value={form.latitude}
                onChange={(e) => update("latitude", e.target.value)}
              />
            </Field>
            <Field title="Longitude" help="Decimal degrees from −180 to 180.">
              <input
                aria-label="Weather longitude"
                required
                type="number"
                step="any"
                min="-180"
                max="180"
                value={form.longitude}
                onChange={(e) => update("longitude", e.target.value)}
              />
            </Field>
            <Field title="From">
              <input
                aria-label="Weather start date"
                required
                type="date"
                min="1981-01-01"
                value={form.start}
                onChange={(e) => update("start", e.target.value)}
              />
            </Field>
            <Field title="Through">
              <input
                aria-label="Weather end date"
                required
                type="date"
                value={form.end}
                onChange={(e) => update("end", e.target.value)}
              />
            </Field>
          </Grid>
          <p className="muted">
            Historical dates only, up to 10 years per request. Recent readings
            can be delayed or revised.
          </p>
          <label className="ui-check">
            <input
              type="checkbox"
              required
              checked={form.share_coordinates}
              onChange={(e) => update("share_coordinates", e.target.checked)}
            />
            <span>
              Send these coordinates and dates to NASA POWER. My files, sales
              and location name will stay local.
            </span>
          </label>
          <Actions>
            <Button
              kind="primary"
              type="submit"
              disabled={busy || !form.share_coordinates}
            >
              {busy ? "Fetching weather…" : "Fetch weather history"}
            </Button>
            <Button
              type="button"
              disabled={busy}
              onClick={() => setEditing(false)}
            >{uiText("Cancel")}</Button>
          </Actions>
        </form>
      )}
      {!loading && !snapshot && !editing && (
        <p className="muted">
          No weather is connected yet. Tehran is the client city; the factory’s
          exact coordinates still need confirmation.
        </p>
      )}
      {snapshot && !editing && (
        <>
          <Field
            title="Saved weather"
            help="Each saved copy keeps the location, dates and exact provider response. Earlier copies remain available."
          >
            <Pick
              label="Saved weather snapshot"
              value={snapshot.id}
              options={snapshots.map((row) => [
                row.id,
                `${row.request.location_name} · ${row.request.start} – ${row.request.end} · ${new Date(row.captured_at).toLocaleString()}`,
              ])}
              onChange={setSelected}
            />
          </Field>
          <dl className="review-list">
            <div>
              <dt>Location</dt>
              <dd>
                {snapshot.request.location_name} · {snapshot.request.latitude},{" "}
                {snapshot.request.longitude}
              </dd>
            </div>
            <div>
              <dt>Saved</dt>
              <dd>{new Date(snapshot.captured_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt>Latest temperature</dt>
              <dd>{snapshot.quality.T2M.latest_reading || "Unavailable"}</dd>
            </div>
            <div>
              <dt>Latest rainfall</dt>
              <dd>
                {snapshot.quality.PRECTOTCORR.latest_reading || "Unavailable"}
              </dd>
            </div>
          </dl>
          <p className="muted">
            Historical grid estimates, not a factory sensor or future forecast.
            Days use UTC, not Tehran local time. Not added to your demand
            forecast.
          </p>
          <details className="help-details">
            <summary>Coverage and source</summary>
            <Table headers={["Reading", "Available days", "Missing days"]}>
              {Object.entries(snapshot.quality).map(([key, q]) => (
                <tr key={key}>
                  <td>{key === "T2M" ? "Temperature" : "Rainfall"}</td>
                  <td>{q.valid_days}</td>
                  <td>{q.missing_days}</td>
                </tr>
              ))}
            </Table>
            <p>
              Missing readings stay blank. Monthly values are shown only when
              every day of that calendar month is available. Recently
              downloaded, revised history cannot be treated as information known
              in older forecast tests.
            </p>
            <p>
              <a href={snapshot.source_url} target="_blank" rel="noreferrer">
                NASA POWER documentation ↗
              </a>{" "}
              ·{" "}
              <a href={snapshot.license_url} target="_blank" rel="noreferrer">
                Usage and attribution ↗
              </a>
            </p>
            <p>{snapshot.attribution}</p>
          </details>
          <details className="help-details">
            <summary>Monthly values</summary>
            <Table
              headers={[
                "Month (UTC)",
                "Mean temperature (°C)",
                "Total rainfall (mm)",
              ]}
            >
              {snapshot.monthly.map((row) => (
                <tr key={row.period}>
                  <td>{row.period.slice(0, 7)}</td>
                  <td>
                    {row.T2M === null ? "Incomplete month" : fmt(row.T2M, 2)}
                  </td>
                  <td>
                    {row.PRECTOTCORR === null
                      ? "Incomplete month"
                      : fmt(row.PRECTOTCORR, 2)}
                  </td>
                </tr>
              ))}
            </Table>
          </details>
          <Actions>
            <a className="btn" href={`/api/weather/${snapshot.id}/export`}>
              Download daily readings
            </a>
            <Button
              onClick={() => {
                setForm({ ...snapshot.request, share_coordinates: false });
                setEditing(true);
                setMessage("");
              }}
            >
              Update date range
            </Button>
          </Actions>
        </>
      )}
    </Stack>
  );
}
