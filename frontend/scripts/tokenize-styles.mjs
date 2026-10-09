// Migration/audit helper. Emits a patch; never writes source files itself.
import{readFileSync,readdirSync,existsSync}from'node:fs';
import postcss from'postcss';
import{createHash}from'node:crypto';
const root=new URL('../src/',import.meta.url);
const files=readdirSync(root).filter(f=>f.endsWith('.css')&&!['tokens.css','design-system.css'].includes(f));
const declarations=new Map();
const previousPath=new URL('tokens.css',root),previous=existsSync(previousPath)?readFileSync(previousPath,'utf8'):null;
const oldTokens=new Map();
if(previous)postcss.parse(previous).walkDecls(d=>oldTokens.set(d.prop,d.value));
const nearest=(n,scale)=>scale.reduce((a,b)=>Math.abs(n-b)<Math.abs(n-a)?b:a);
const semantic={
  '#5ee800':'color-accent','#48c400':'color-accent-hover','#2a6d08':'color-accent-ink','#f1ffea':'color-accent-soft',
  '#fff':'color-surface','#ffffff':'color-surface','#111':'color-ink','#111111':'color-ink',
  '#202020':'color-text','#686868':'color-muted','#f2f2f2':'color-soft',
  '4px':'space-1','8px':'space-2','12px':'space-3','16px':'space-4','20px':'space-5','24px':'space-6','32px':'space-8','48px':'space-12',
};
function token(value,prop){
  let normal=value.trim().replace(/#[A-Fa-f0-9]+/g,v=>v.toLowerCase());
  let match=normal.match(/^var\((--[^)]+)\)$/);
  for(let depth=0;match&&oldTokens.has(match[1])&&depth<4;depth++){
    normal=oldTokens.get(match[1]);match=normal.match(/^var\((--[^)]+)\)$/);
  }
  if(/^\d+(\.\d+)?px$/.test(normal)&&prop==='font-size')normal=nearest(parseFloat(normal),[13,14,16,18,20,24,28,32,40,48])+'px';
  if(/^\d+(\.\d+)?px$/.test(normal)&&/radius/.test(prop))normal=nearest(parseFloat(normal),[4,8,12,16,24])+'px';
  if(/padding|margin|gap/.test(prop))normal=normal.replace(/(?<![-\d.])\d+(?:\.\d+)?px\b/g,v=>nearest(parseFloat(v),[2,4,8,12,16,20,24,32,40,48,64])+'px');
  if(prop==='font-weight'&&/^\d+$/.test(normal))normal=nearest(Number(normal),[400,500,600,700]).toString();
  const category=prop==='font-family'?'font-family':/color|fill|stroke/.test(prop)?'color':/font-size/.test(prop)?'type':/font-weight/.test(prop)?'weight':/padding|margin|gap/.test(prop)?'space':/radius/.test(prop)?'radius':/shadow/.test(prop)?'shadow':'layout';
  const publicName=normal.startsWith('#')?semantic[normal]:category==='space'?semantic[normal]:null;
  const name=publicName||(prop==='font-family'?'font-family-'+(normal.startsWith('Vazirmatn')?'fa':'ui'):prop==='font-size'&&/^\d+px$/.test(normal)?'type-'+parseFloat(normal):category+'-'+createHash('sha256').update(normal).digest('hex').slice(0,8));
  declarations.set(name,normal);return 'var(--'+name+')';
}
let patch='*** Begin Patch\n';
for(const file of files){
  const source=readFileSync(new URL(file,root),'utf8'),tree=postcss.parse(source);
  tree.walkDecls(d=>{
    if(d.parent.type==='atrule'&&d.parent.name==='font-face')return;
    if(d.prop.startsWith('--')){d.value=token(d.value,d.prop);return;}
    // Keywords (flex/grid/auto/none), zero and percentages are layout semantics,
    // not an independent visual scale. All paint, dimensions, timing and fonts move.
    if(!/(?:#[\da-f]{3,8}|\b(?:rgba?|hsla?)\(|\b(?:white|black)\b|(?:\d|\.)+(?:px|rem|em|vh|vw|ms|s)\b)/i.test(d.value)&&!['font-weight','line-height','opacity','fill-opacity','letter-spacing'].includes(d.prop)&&!/^var\(--[a-z\d-]+\)$/.test(d.value))return;
    d.value=token(d.value,d.prop);
  });
  const next=tree.toString();
  if(next!==source)patch+='*** Update File: frontend/src/'+file+'\n@@\n'+source.trimEnd().split('\n').map(l=>'-'+l).join('\n')+'\n'+next.trimEnd().split('\n').map(l=>'+'+l).join('\n')+'\n';
}
const content='/* One registry for all authored visual values. Semantic public tokens first. */\n:root {\n  --canvas: #f4f4f4;\n  --bg: var(--canvas);\n  --surface-soft: var(--color-soft);\n'+[...declarations].sort(([a],[b])=>a.localeCompare(b)).map(([name,value])=>'  --'+name+': '+value+';').join('\n')+'\n  --chart-forecast: var(--color-accent-ink);\n  --chart-history: var(--color-muted);\n  --chart-expected: #a6b79e;\n  --chart-range: #dce5d7;\n  --chart-grid: var(--color-soft);\n}\n';
patch+=(previous?'*** Update File: frontend/src/tokens.css\n@@\n'+previous.trimEnd().split('\n').map(l=>'-'+l).join('\n')+'\n':'*** Add File: frontend/src/tokens.css\n')+content.trimEnd().split('\n').map(l=>'+'+l).join('\n')+'\n*** End Patch';
console.log(patch);
