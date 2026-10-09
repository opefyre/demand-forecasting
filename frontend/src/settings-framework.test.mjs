import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import postcss from 'postcss';

let server,Panel,UnitSettings,AISettings,LanguageSettings,RecurringForecasts,SettingsWorkspace;
before(async()=>{
  server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
  ({Panel}=await server.ssrLoadModule('/src/ui-layout.jsx'));
  ({UnitSettings}=await server.ssrLoadModule('/src/units.jsx'));
  ({AISettings}=await server.ssrLoadModule('/src/ai-settings.jsx'));
  ({LanguageSettings}=await server.ssrLoadModule('/src/language-settings.jsx'));
  ({RecurringForecasts}=await server.ssrLoadModule('/src/recurring-forecasts.jsx'));
  ({SettingsWorkspace}=await server.ssrLoadModule('/src/settings-workspace.jsx'));
});
after(async()=>{await server?.close();});
const ui={Button:({children,...props})=>React.createElement('button',props,children),Field:({title,children})=>React.createElement('div',{className:'field'},title,children),Pick:({label})=>React.createElement('button',{'aria-label':label}),ErrorBox:()=>null,Help:()=>null,Table:()=>null,Modal:()=>null};
const common={api:async()=>({}),ui,runs:[],datasets:[],canAdmin:true,access:{mode:'local'},workspace:{site:{}},fmt:String,date:String};
test('all Settings destinations render the same panel/header/title/body contract',()=>{
  const panes=[React.createElement(SettingsWorkspace,common),React.createElement(UnitSettings,common),React.createElement(AISettings,{...common,expanded:true}),React.createElement(LanguageSettings,common),React.createElement(RecurringForecasts,{...common,settings:true}),React.createElement(Panel,{title:'Access'},'Access content')];
  for(const pane of panes){const html=renderToStaticMarkup(pane);
    assert.match(html,/<section class="ui-panel">/);
    assert.match(html,/<header class="ui-panel-header">/);
    assert.match(html,/<h2 class="ui-panel-title">/);
    assert.match(html,/<div class="ui-stack">/);
    assert.doesNotMatch(html,/class="(?:units-section|settings-section|site-form|ai-setting-list|recurring-settings|language-settings)/);
  }
});
test('Settings uses global primitives rather than dedicated appearance classes',async()=>{
  for(const file of['settings-workspace.jsx','units.jsx','language-settings.jsx','ai-settings.jsx']){
    const text=await readFile(new URL(file,import.meta.url),'utf8');
    assert.match(text,/from ['"]\.\/ui-layout\.jsx['"]/);
    assert.doesNotMatch(text,/className=["'](?:settings-|units-|unit-rule|unit-equation|site-form|ai-setting|ai-call|language-settings|inventory-actions|section-heading)/);
    assert.doesNotMatch(text,/<h2>/);
  }
});
test('shared component appearance has one owner, with no per-page overrides',async()=>{
  const root=new URL('./',import.meta.url),issues=[];
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.css')&&f!=='ui-framework.css')){
    postcss.parse(await readFile(new URL(file,root),'utf8')).walkRules(rule=>{
      if(/\.ui-(?:panel|stack|grid|actions|field-group|definition-list|subnav|content-column|list-row|list-body|check|disclosure|table-note)\b/.test(rule.selector))issues.push(file+': '+rule.selector);
      if(/\.(?:units-section|unit-rule|unit-equation|site-form|settings-nav|settings-content|settings-layout|language-settings|recurring-settings|recurring-fields|recurring-row|recurring-actions)\b/.test(rule.selector))issues.push(file+': obsolete rule '+rule.selector);
    });
  }assert.deepEqual(issues,[]);
});
test('panel typography, spacing and responsive forms use semantic global tokens',async()=>{
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  for(const token of['panel-padding','panel-padding-compact','panel-radius','component-gap','field-gap','action-gap','heading-gap','type-heading-section','type-body','type-label','weight-heading','line-heading','line-body','measure-form'])assert.ok(css.includes('var(--'+token+')'),token);
  assert.match(css,/\.ui-grid-two,\.ui-grid-three \{grid-template-columns:1fr;/);
  assert.match(css,/\.ui-stack \.field,\.ui-grid \.field \{margin:0;/);
});
