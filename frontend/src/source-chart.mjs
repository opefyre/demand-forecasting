// Display gaps as gaps. Never invent source values for a chart.
export function sourceChart(snapshot) {
  const points = snapshot?.points || [];
  if (!points.length || !['daily', 'monthly'].includes(snapshot.frequency)) return [];
  const known = new Map(points.map(p => [p.period, p.value]));
  const last = new Date(`${points.at(-1).period}T00:00:00Z`);
  const first = new Date(`${points[0].period}T00:00:00Z`);
  const start = new Date(last);
  if (snapshot.frequency === 'daily') start.setUTCDate(start.getUTCDate() - 89);
  else { start.setUTCDate(1); start.setUTCMonth(start.getUTCMonth() - 34); start.setUTCDate(0); }
  const rows = [];
  for (let cursor = new Date(Math.max(start.getTime(), first.getTime())); cursor <= last;) {
    const period = cursor.toISOString().slice(0, 10);
    rows.push({period, value: known.get(period) ?? null});
    if (snapshot.frequency === 'daily') cursor.setUTCDate(cursor.getUTCDate() + 1);
    else { cursor.setUTCDate(1); cursor.setUTCMonth(cursor.getUTCMonth() + 2); cursor.setUTCDate(0); }
  }
  return rows;
}
