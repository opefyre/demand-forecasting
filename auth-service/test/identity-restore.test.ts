import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, chmod, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

test('offline identity review verifies a private export, refuses damage and does not print SQL',async()=>{
  const folder=await mkdtemp(join(tmpdir(),'forecast-identity-review-'));
  try {
    const sql=await readFile(new URL('../../deploy/cloudflare/migrations/0001_identity.sql',import.meta.url),'utf8');
    const path=join(folder,'identity.sql');await writeFile(path,sql,{mode:0o600});
    const hash=createHash('sha256').update(sql).digest('hex');
    const run=(expected:string)=>spawnSync(process.execPath,['--import','tsx','scripts/verify-identity-restore.ts',path,expected],{encoding:'utf8'});
    const good=run(hash);assert.equal(good.status,0);
    assert.equal(JSON.parse(good.stdout).live_database_changed,false);
    assert.equal(JSON.parse(good.stdout).replayable_credentials,0);
    const damaged=run('0'.repeat(64));assert.equal(damaged.status,1);assert.equal(damaged.stdout,'');
    await chmod(path,0o644);const exposed=run(hash);assert.equal(exposed.status,1);
    assert.doesNotMatch(exposed.stderr,/CREATE TABLE|create table|INSERT INTO/);
  } finally { await rm(folder,{recursive:true,force:true}); } // Only this test's exact disposable directory.
});
