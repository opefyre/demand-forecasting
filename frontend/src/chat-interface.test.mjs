import test,{after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import postcss from 'postcss';
import * as Tooltip from '@radix-ui/react-tooltip';

const compiler=await createServer({configFile:false,root:process.cwd(),
  server:{middlewareMode:true,hmr:false,ws:false,watch:null},appType:'custom',
  optimizeDeps:{noDiscovery:true,include:[]},cacheDir:'/private/tmp/demandlab-chat-interface-cache'});
after(()=>compiler.close());
const {ChatSurface,ChatMessage,CHAT_EXAMPLES,composerShouldSend}=await compiler.ssrLoadModule('/src/ui-chat.jsx');
const locale=await compiler.ssrLoadModule('/src/localization.mjs');
const {AppSidebar,readSidebarPreference,saveSidebarPreference}=await compiler.ssrLoadModule('/src/ui-sidebar.jsx');
const {ChatHistory}=await compiler.ssrLoadModule('/src/ui-chat-history.jsx');
const {mascotRhythm}=await compiler.ssrLoadModule('/src/assistant-mascot.jsx');
const {MotionPresence}=await compiler.ssrLoadModule('/src/ui-motion.jsx');
const base={value:'',onChange:()=>{},onSend:()=>{},sourceName:'Synthetic history',onNewChat:()=>{}};
const render=props=>renderToStaticMarkup(React.createElement(ChatSurface,{...base,...props}));

test('shared notification presence has an accessible open state and no empty closed element',()=>{
  const notification=present=>React.createElement(MotionPresence,{present},React.createElement('div',{className:'toast',role:'status'},'Saved'));
  assert.match(renderToStaticMarkup(notification(true)),/data-state="open" aria-hidden="false"/);
  assert.equal(renderToStaticMarkup(notification(false)),'');
});

test('new chat has one composer, one tools button, one heading and three examples',()=>{
  const html=render({active:false});
  assert.match(html,/ui-chat-empty/);assert.equal((html.match(/<textarea/g)||[]).length,1);
  assert.equal((html.match(/aria-label="Add data &amp; tools"/g)||[]).length,1);
  assert.equal((html.match(/<h1/g)||[]).length,1);
  for(const example of CHAT_EXAMPLES)assert.ok(html.includes(example));
  assert.doesNotMatch(html,/Ask here|New chat|Choose sales history|ui-chat-transcript|ai-source-picker/);
  assert.match(html,/<button type="submit"[^>]+disabled=""/);
});

test('new-chat greeting reuses the animated mascot without adding text or a background disk',()=>{
  const html=render({active:false});
  assert.match(html,/ui-chat-welcome-character" aria-hidden="true"/);
  assert.match(html,/class="ui-mascot"/);
  assert.equal((html.match(/class="ui-mascot"/g)||[]).length,1);
  assert.doesNotMatch(render({active:true}),/ui-chat-welcome-character/);
});
test('conversation replaces the welcome and examples while retaining the same composer',()=>{
  const html=render({active:true,children:React.createElement('p',null,'Synthetic reply'),value:'Next question'});
  assert.match(html,/ui-chat-active/);assert.match(html,/role="log"/);assert.match(html,/Synthetic reply/);
  assert.match(html,/New chat/);assert.doesNotMatch(html,/ui-chat-suggestions|<h1/);
  assert.equal((html.match(/<textarea/g)||[]).length,1);
});
test('in-flight message is visible without inventing an assistant answer',()=>{
  const html=render({active:true,pending:'Forecast 6 months',busy:true});
  assert.match(html,/Forecast 6 months/);assert.match(html,/role="status"/);
  assert.match(html,/<textarea[^>]+disabled=""/);assert.doesNotMatch(html,/ui-chat-suggestions/);
});
test('both message sides use the same bubble/avatar component, including pending replies',()=>{
  const user=renderToStaticMarkup(React.createElement(ChatMessage,{side:'user'},'Customer A'));
  const assistant=renderToStaticMarkup(React.createElement(ChatMessage,{},'Saved result'));
  assert.match(user,/ui-chat-message-user/);assert.match(assistant,/ui-chat-message-assistant/);
  for(const html of[user,assistant]){assert.match(html,/ui-chat-avatar/);assert.match(html,/role="img"/);assert.match(html,/ui-chat-bubble/);}
  assert.match(user,/<svg/);
  assert.match(assistant,/<svg[^>]+class="ui-mascot"/);
  assert.match(assistant,/ui-mascot-eye/);
  assert.doesNotMatch(assistant,/<img/);
  const pending=render({active:true,pending:'Forecast 6 months',busy:true});
  assert.equal((pending.match(/class="ui-chat-avatar"/g)||[]).length,2);
});
test('Enter sends, Shift+Enter and composition keep editing',()=>{
  assert.equal(composerShouldSend({key:'Enter'}),true);
  for(const event of[{key:'Enter',shiftKey:true},{key:'Enter',nativeEvent:{isComposing:true}},{key:'Enter',keyCode:229},{key:'x'}])assert.equal(composerShouldSend(event),false);
});
test('chat layout fixes physical sides independently from Persian text direction',async()=>{
  for(const language of['en','fa']){
    await locale.changeInterfaceLanguage(language);
    const html=render({active:true,children:[React.createElement(ChatMessage,{key:'user',side:'user'},'سلام'),React.createElement(ChatMessage,{key:'assistant'},'پاسخ')],pending:'Next question'});
    assert.match(html,/class="ui-chat-transcript" dir="ltr"/);
    assert.equal((html.match(/ui-chat-message (?:ui-chat-message-user|ui-chat-message-assistant)"[^>]*dir="ltr"/g)||[]).length,4);
    assert.equal((html.match(/class="ui-chat-bubble" dir="auto"/g)||[]).length,4);
  }
  await locale.changeInterfaceLanguage('en');
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  assert.match(css,/\.ui-chat-message \{[^}]*align-self:flex-start;[^}]*max-width:var\(--chat-bubble-measure\)/);
  assert.match(css,/\.ui-chat-message-user \{align-self:flex-end;flex-direction:row-reverse;/);
});
test('assistant character has no background disk while user identity retains its background',async()=>{
  const tokens=await readFile(new URL('tokens.css',import.meta.url),'utf8');
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  assert.match(tokens,/--chat-avatar-bg:\s*transparent;/);
  assert.match(css,/\.ui-chat-avatar \{[^}]+background:var\(--chat-avatar-bg\)/);
  assert.match(css,/\.ui-chat-message-user \.ui-chat-avatar \{background:var\(--chat-message-user-bg\)/);
});
test('mascot uses continuous eye paths, independent motion and a reduced-motion fallback',async()=>{
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  const tree=postcss.parse(css);
  const morph=tree.nodes.find(node=>node.type==='atrule'&&node.name==='keyframes'&&node.params==='mascot-eyes');
  const paths=[];morph.walkDecls('d',declaration=>paths.push(declaration.value));
  assert.equal(paths.length,2);assert.notEqual(paths[0],paths[1]);
  assert.deepEqual(paths[0].match(/[MCZ]/g),paths[1].match(/[MCZ]/g));
  assert.doesNotMatch(css,/steps\(/);
  for(const animation of['mascot-breathe','mascot-wave','mascot-glance'])assert.ok(css.includes('@keyframes '+animation));
  assert.match(css,/@media \(prefers-reduced-motion:reduce\)\s*\{\s*\.ui-mascot \* \{animation:none;/);
  const component=await readFile(new URL('assistant-mascot.jsx',import.meta.url),'utf8');
  assert.match(component,/IntersectionObserver/);assert.match(component,/visibilitychange/);
  assert.doesNotMatch(component,/setInterval|requestAnimationFrame|style=/);
});
test('multiple mascot instances have separate gradient identities',()=>{
  const html=renderToStaticMarkup(React.createElement('div',{},React.createElement(ChatMessage,{},'One'),React.createElement(ChatMessage,{},'Two')));
  const ids=[...html.matchAll(/id="([^"]+-(?:body|limb))"/g)].map(match=>match[1]);
  assert.equal(ids.length,4);assert.equal(new Set(ids).size,4);
});

test('mascot speed is 20% faster and each part has an independent clock',async()=>{
  const tokens=await readFile(new URL('tokens.css',import.meta.url),'utf8');
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  assert.match(tokens,/--mascot-speed:\s*1\.2;/);
  const durations=[...tokens.matchAll(/--mascot-[a-z-]+-duration:\s*calc\(([\d.]+)s \/ var\(--mascot-speed\)\)/g)].map(match=>Number(match[1]));
  assert.equal(durations.length,8);assert.equal(new Set(durations).size,8);
  assert.equal(6/(6/1.2),1.2);
  for(const name of['head','mouth','blink','hand-rest'])assert.ok(css.includes('@keyframes mascot-'+name));
  assert.match(css,/ui-mascot-hand-rest[^}]+var\(--mascot-left-hand-duration\)/);
  assert.match(css,/ui-mascot-face[^}]+var\(--mascot-glance-duration\)/);
});
test('curl and mouth morphs preserve matching path segments and the body silhouette',async()=>{
  const tokens=await readFile(new URL('tokens.css',import.meta.url),'utf8');
  for(const part of['head','mouth']){
    const paths=[...tokens.matchAll(new RegExp('--mascot-'+part+'-[a-z]+: path\\("([^"\\n]+)"\\);','g'))].map(match=>match[1]);
    assert.equal(paths.length,3);
    for(const path of paths.slice(1))assert.deepEqual(path.match(/[MCZ]/g),paths[0].match(/[MCZ]/g));
    if(part==='head')for(const path of paths.slice(1))assert.equal(path.slice(path.indexOf('C33 27')),paths[0].slice(paths[0].indexOf('C33 27')));
  }
});
test('instance rhythms vary without timers, random rendering or inline CSS',()=>{
  const variants=['a','b','c'].map(mascotRhythm);
  assert.equal(new Set(variants).size,3);
  for(const id of['welcome','assistant-42','a']){assert.equal(mascotRhythm(id),mascotRhythm(id));assert.ok([0,1,2].includes(mascotRhythm(id)));}
});
test('new chat chrome and examples are translated without changing data names',async()=>{
  await locale.changeInterfaceLanguage('fa');
  const html=render({active:false});
  assert.match(html,/چه چیزی را پیش‌بینی/);assert.match(html,/افزودن داده و ابزار/);
  assert.match(html,/۶ ماه آینده/);assert.match(html,/داده‌های فروش من/);
  assert.doesNotMatch(html,/Ask about your sales|Try asking|Forecast the next/);
  await locale.changeInterfaceLanguage('en');
});
test('chat and menu appearance has one global owner, with no old composer overrides',async()=>{
  const root=new URL('./',import.meta.url);
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.css')&&f!=='ui-framework.css')){
    postcss.parse(await readFile(new URL(file,root),'utf8')).walkRules(rule=>{
      assert.doesNotMatch(rule.selector,/\.ui-(?:chat|menu)\b/,file);
      assert.doesNotMatch(rule.selector,/\.ai-(?:chat|welcome|composer|attach|source-picker)\b/,file);
      assert.doesNotMatch(rule.selector,/\.ai-message\b/,file);
    });
  }
  const css=await readFile(new URL('ui-framework.css',root),'utf8');
  assert.match(css,/\.ui-chat-active \{grid-template-rows:auto minmax\(0,1fr\) auto;/);
  assert.match(css,/\.ui-chat-transcript[^}]+overflow:auto/);
  assert.match(css,/\.ai-message th,\.ai-message td \{[^}]*white-space:normal/);
  const source=await readFile(new URL('ui-chat.jsx',root),'utf8');
  assert.match(source,/DropdownMenu\.Root dir=\{interfaceDirection\(\)\}/);
  assert.match(source,/modal=\{false\}/);
  assert.match(source,/onChange\(uiText\(example\)\);\s*input\.current\?\.focus\(\)/);
  assert.doesNotMatch(source,/style=|Paperclip|CaretDown|model-picker/);
});
test('menus and dialogs share one dismissable-layer version, avoiding stuck click blockers',async()=>{
  const lock=JSON.parse(await readFile(new URL('../package-lock.json',import.meta.url),'utf8'));
  const layers=Object.entries(lock.packages).filter(([path])=>path.endsWith('node_modules/@radix-ui/react-dismissable-layer'));
  assert.equal(layers.length,1);
});

test('sidebar retains accessible icon labels and correct page selection in both states',()=>{
  const Icon=()=>React.createElement('svg',{'aria-hidden':true});
  for(const collapsed of[false,true]){
    const html=renderToStaticMarkup(React.createElement(Tooltip.Provider,{},React.createElement(AppSidebar,{collapsed,page:'forecast',items:[['today','Home',Icon],['demand','Forecast',Icon]],onToggle:()=>{},onNavigate:()=>{}})));
    assert.match(html,/aria-label="Home"/);assert.match(html,/aria-label="Forecast" aria-current="page"/);
    assert.match(html,new RegExp('aria-expanded="'+!collapsed+'"'));
    assert.match(html,new RegExp('aria-label="'+(collapsed?'Expand sidebar':'Collapse sidebar')+'"'));
  }
});
test('sidebar remembers its collapsed preference and tolerates unavailable storage',()=>{
  const values=new Map(),storage={getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)};
  assert.equal(readSidebarPreference(storage),false);saveSidebarPreference(storage,true);assert.equal(readSidebarPreference(storage),true);
  saveSidebarPreference(storage,false);assert.equal(readSidebarPreference(storage),false);
  const blocked={getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}};
  assert.equal(readSidebarPreference(blocked),false);assert.doesNotThrow(()=>saveSidebarPreference(blocked,true));
});
test('chat history is a separate labelled list with real titles, selection and pagination',()=>{
  const html=renderToStaticMarkup(React.createElement(ChatHistory,{chats:[{id:'chat1',head_id:'head1',title:'Synthetic forecast'}],activeHead:'head1',nextOffset:50}));
  assert.match(html,/aria-label="Chat history"/);assert.match(html,/aria-current="true"/);
  assert.match(html,/Synthetic forecast/);assert.match(html,/Show older chats/);
  assert.equal((html.match(/>New chat</g)||[]).length,1);
  assert.doesNotMatch(html,/Pinned|Projects|saved calculations/);
});
test('chat history empty, loading and failure states do not invent conversations',()=>{
  for(const [props,label]of[[{},'No chats yet'],[{loading:true},'Loading chats…'],[{error:true},'Could not load chats.']]){
    const html=renderToStaticMarkup(React.createElement(ChatHistory,{chats:[],...props}));assert.ok(html.includes(label));assert.doesNotMatch(html,/ui-chat-history-item/);
  }
});
test('history chrome translates but user-authored titles stay untouched',async()=>{
  await locale.changeInterfaceLanguage('fa');
  const html=renderToStaticMarkup(React.createElement(ChatHistory,{chats:[{id:'c',head_id:'h',title:'Customer input'}]}));
  assert.match(html,/گفت‌وگوها/);assert.match(html,/Customer input/);assert.doesNotMatch(html,/>New chat</);
  await locale.changeInterfaceLanguage('en');
});
