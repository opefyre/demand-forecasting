import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createServer} from 'vite';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {fa} from './locales/fa.mjs';
let server,Settings,NotificationSettings,notificationPayload,notificationEvents,deliveryStates;
before(async()=>{
  server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
  ({SettingsWorkspace:Settings}=await server.ssrLoadModule('/src/settings-workspace.jsx'));
  ({NotificationSettings,notificationPayload,notificationEvents,deliveryStates}=await server.ssrLoadModule('/src/notification-settings.jsx'));
});
after(async()=>{await server?.close();});
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),Field:()=>null,Pick:()=>null,Table:()=>null,Modal:()=>null,ErrorBox:()=>null};
const common={api:async()=>({}),ui,canAdmin:true,access:{mode:'better_auth',user:{role:'admin'}},date:String};
test('notification settings are visible only to company administrators',()=>{
  assert.match(renderToStaticMarkup(React.createElement(Settings,common)),/>Notifications</);
  for(const props of[{canAdmin:false},{access:{mode:'local'}}])assert.doesNotMatch(renderToStaticMarkup(React.createElement(Settings,{...common,...props})),/>Notifications</);
});
test('notification payload excludes stored secrets, company IDs and response metadata',()=>{
  const form={id:'one',version:2,name:'Ops',provider:'slack',destination:'Ops channel',language:'en',events:['forecast_ready'],enabled:true,confirmed:true,
    template:'',template_language:'en_US',eligible:false,webhook:'',token:'',recipient:'',sender_id:'',credential_configured:true,archived:false,company_id:'wrong'};
  const payload=notificationPayload(form);
  for(const key of['id','archived','credential_configured','company_id','webhook','token','recipient','sender_id'])assert.equal(Object.hasOwn(payload,key),false,key);
  assert.equal(payload.version,2);assert.equal(notificationPayload({...form,webhook:'new'}).webhook,'new');
});
test('notifications reuse shared collections, menus, fixed dialogs and fields with no private styling',async()=>{
  const source=await readFile(new URL('notification-settings.jsx',import.meta.url),'utf8');
  for(const element of['Stack','Collection','ConnectionRecord','ActionMenu','PageTabs','DefinitionList','FieldGroup','Grid'])assert.match(source,new RegExp('<'+element+'\\b'));
  assert.doesNotMatch(source,/style=|\.css['"]|localStorage|company_id/);
  assert.equal([...source.matchAll(/<Modal /g)].length,3);
  assert.equal([...source.matchAll(/<Modal[^>]+ fixed /g)].length,3);
  assert.match(source,/duplicate_confirmed:duplicates/);assert.match(source,/crypto.randomUUID/);
  assert.match(renderToStaticMarkup(React.createElement(NotificationSettings,common)),/class="ui-stack"/);
});
test('authored notification labels, events and receipt states have Persian translations',async()=>{
  const source=await readFile(new URL('notification-settings.jsx',import.meta.url),'utf8');
  for(const match of source.matchAll(/\bt\((["'])([^"']+)\1/g))assert.ok(fa[match[2]],match[2]);
  for(const label of [...Object.values(notificationEvents),...Object.values(deliveryStates)])assert.ok(fa[label],label);
});
