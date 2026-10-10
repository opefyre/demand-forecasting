// Offline-only review. Never connects to D1 or replaces the live identity store.
import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';

async function main() {
  const [path, expected] = process.argv.slice(2);
  if (!path || !/^[a-f0-9]{64}$/.test(expected || '')) throw new Error('Provide a private export and its expected SHA-256.');
  const info = await stat(path);
  if (!info.isFile() || info.size > 64 * 1024 ** 2 || (info.mode & 0o077)) throw new Error('Use a private, bounded export file.');
  const bytes = await readFile(path);
  if (createHash('sha256').update(bytes).digest('hex') !== expected) throw new Error('Export checksum does not match.');
  const sql = bytes.toString('utf8');
  // Official D1 exports do not need attached files or executable extensions.
  if (/\b(?:ATTACH|DETACH)\b|load_extension\s*\(/i.test(sql)) throw new Error('Unsupported export.');
  const db = new DatabaseSync(':memory:', { allowExtension: false });
  try {
    db.exec(sql);
    const counts = () => Object.fromEntries(['user', 'organization', 'member', 'twoFactor'].map(table =>
      [table, Number(db.prepare(`SELECT count(*) AS n FROM "${table}"`).get()!.n)]));
    const before = counts();
    if (db.prepare('PRAGMA integrity_check').get()!.integrity_check !== 'ok' ||
        db.prepare('PRAGMA foreign_key_check').all().length) throw new Error('Identity integrity check failed.');
    // Only this in-memory review copy: restored sessions/tokens cannot replay.
    db.exec(`BEGIN;
      DELETE FROM demandlab_session_mfa; DELETE FROM demandlab_session_company;
      DELETE FROM "session"; DELETE FROM "verification";
      UPDATE apikey SET enabled=0; UPDATE demandlab_key_bindings SET revoked=1;
      UPDATE invitation SET status='canceled' WHERE status='pending';
      UPDATE account SET accessToken=NULL,refreshToken=NULL,idToken=NULL,
        accessTokenExpiresAt=NULL,refreshTokenExpiresAt=NULL;
      COMMIT;`);
    if (JSON.stringify(counts()) !== JSON.stringify(before)) throw new Error('Recovery altered identity ownership.');
    const replayable = Number(db.prepare('SELECT count(*) AS n FROM "session"').get()!.n) +
      Number(db.prepare('SELECT count(*) AS n FROM verification').get()!.n) +
      Number(db.prepare('SELECT count(*) AS n FROM apikey WHERE enabled=1').get()!.n) +
      Number(db.prepare('SELECT count(*) AS n FROM account WHERE accessToken IS NOT NULL OR refreshToken IS NOT NULL OR idToken IS NOT NULL').get()!.n);
    if (replayable) throw new Error('Restored authority was not paused.');
    console.log(JSON.stringify({ verified: true, counts: before, replayable_credentials: replayable,
      mfa_enabled: Number(db.prepare('SELECT count(*) AS n FROM "user" WHERE twoFactorEnabled=1').get()!.n),
      live_database_changed: false }));
  } finally { db.close(); }
}
// Never emit SQL, credential values or native SQL error text.
main().catch(() => { console.error('Identity restore verification failed; live data was not changed.'); process.exitCode = 1; });
