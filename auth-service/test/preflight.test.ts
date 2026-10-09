import test from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { mkdtempSync, writeFileSync, chmodSync, symlinkSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { configuration, validateEnvironmentFile } from '../src/env.js';
import { deploymentChecks } from '../src/preflight.js';

const settings = () => ({
  DEMANDLAB_AUTH_MODE: 'better_auth', DEMANDLAB_PUBLIC_ORIGIN: 'https://forecast.example.test',
  DEMANDLAB_AUTH_SERVICE_URL: 'http://127.0.0.1:8011',
  BETTER_AUTH_SECRET: randomBytes(32).toString('hex'),
  DEMANDLAB_AUTH_BRIDGE_SECRET: randomBytes(32).toString('hex'),
  DEMANDLAB_AUTH_DATABASE_URL: 'postgresql://localhost/dedicated_auth',
  SMTP_HOST: 'mail.example.test', SMTP_FROM: 'forecast@example.test',
});

test('valid settings are not mistaken for verified deployment', () => {
  const report=deploymentChecks(settings());
  assert(report.configuration_ok); assert.equal(report.deployment_verified,false);
  assert(report.pending.some(s=>s.includes('four roles')));
  assert(report.pending.some(s=>s.includes('backups')));
});

test('local settings require explicit local-check option', () => {
  const env={...settings(),DEMANDLAB_PUBLIC_ORIGIN:'http://127.0.0.1:8010',DEMANDLAB_AUTH_DEV_MAIL:'true'};
  assert(!deploymentChecks(env).configuration_ok);
  assert(deploymentChecks(env,true).configuration_ok);
  assert(!deploymentChecks({...env,DEMANDLAB_AUTH_MODE:'local'},true).configuration_ok);
});

test('private bridge cannot point outside the supplied loopback service', () => {
  const credentialURL=new URL('http://127.0.0.1:8011');
  credentialURL.username='synthetic'; credentialURL.password=randomBytes(16).toString('hex');
  for(const url of ['https://identity.example.test','http://127.0.0.1:8011/internal',
    credentialURL.href,'http://127.0.0.1:9000','not-a-url'])
    assert(!deploymentChecks({...settings(),DEMANDLAB_AUTH_SERVICE_URL:url}).configuration_ok);
});

test('malformed settings never print secret values', () => {
  const env=settings();
  const report=deploymentChecks({...env,DEMANDLAB_PUBLIC_ORIGIN:env.BETTER_AUTH_SECRET});
  const output=JSON.stringify(report);
  assert(!report.configuration_ok);
  assert(!output.includes(env.BETTER_AUTH_SECRET)); assert(!output.includes(env.DEMANDLAB_AUTH_BRIDGE_SECRET));
});

test('database, SMTP port and credential pairs fail closed', () => {
  for(const origin of [' https://forecast.example.test','https://FORECAST.example.test','https://forecast.example.test:443'])
    assert.throws(()=>configuration({...settings(),DEMANDLAB_PUBLIC_ORIGIN:origin}));
  assert.equal(configuration({...settings(),DEMANDLAB_PUBLIC_ORIGIN:'https://forecast.example.test/'}).origin,'https://forecast.example.test');
  for(const url of ['https://private.example/password','postgresql://localhost/','secret-text'])
    assert.throws(()=>configuration({...settings(),DEMANDLAB_AUTH_DATABASE_URL:url}));
  for(const port of ['0','65536','587.1','NaN'])
    assert.throws(()=>configuration({...settings(),SMTP_PORT:port}));
  assert.throws(()=>configuration({...settings(),SMTP_USER:'user'}));
  assert.throws(()=>configuration({...settings(),SMTP_PASSWORD:randomBytes(16).toString('hex')}));
  assert.throws(()=>configuration({...settings(),GOOGLE_CLIENT_ID:'client'}));
});

test('secret files must be private regular files, never symlinks', () => {
  const directory=mkdtempSync(join(tmpdir(),'demandlab-preflight-'));
  const file=join(directory,'settings'), link=join(directory,'link');
  try {
    writeFileSync(file,'synthetic settings',{mode:0o600});
    validateEnvironmentFile(file);
    symlinkSync(file,link); assert.throws(()=>validateEnvironmentFile(link));
    assert.throws(()=>validateEnvironmentFile(directory));
    if(process.platform !== 'win32') {
      chmodSync(file,0o644); assert.throws(()=>validateEnvironmentFile(file));
    }
  } finally { rmSync(directory,{recursive:true}); }
});
