// Mechanical migration of authored UI text. Never rewrite values, handlers,
// customer/SKU data, source headings, storage keys, routes or API payloads.
import {readFile,writeFile} from 'node:fs/promises';
import {parsers} from 'prettier/plugins/babel';
import {fa} from '../src/locales/fa.mjs';

const labelProps=new Set(['title','label','help','text','description','placeholder','aria-label','empty']);
export async function localizeSource(source){
  const ast=await parsers.babel.parse(source), edits=[], keys=[];
  const translated=value=>Object.hasOwn(fa,value);
  function visit(node,ancestors=[]){
    if(!node||typeof node!=='object')return;
    const parent=ancestors.at(-1);
    if(node.type==='JSXText'){
      const value=node.value.replace(/\s+/g,' ').trim();
      if(value)keys.push(value);
      if(translated(value)){
        const inline=!node.value.includes('\n');
        const leading=inline&&/^\s/.test(node.value)?"{' '}":'';
        const trailing=inline&&/\s$/.test(node.value)?"{' '}":'';
        edits.push([node.start,node.end,`${leading}{uiText(${JSON.stringify(value)})}${trailing}`]);
      }
    }
    if(node.type==='StringLiteral'){
      let eligible=false,wrap=false;
      if(parent?.type==='JSXAttribute'&&(labelProps.has(parent.name.name)||
        (parent.name.name==='name'&&['Line','Bar'].includes(ancestors.at(-2)?.name?.name)))){eligible=true;wrap=true;}
      if(parent?.type==='JSXExpressionContainer'&&ancestors.at(-2)?.type!=='JSXAttribute')eligible=true;
      if(parent?.type==='ConditionalExpression'&&(parent.consequent===node||parent.alternate===node)){
        // Only a rendered branch, never state/default values or event handlers.
        let rendered=false;
        for(const p of ancestors.toReversed()){
          if(['ArrowFunctionExpression','FunctionExpression','CallExpression','ObjectProperty'].includes(p.type))break;
          if(p.type==='JSXAttribute'){rendered=labelProps.has(p.name.name);break;}
          if(p.type==='JSXExpressionContainer'){
            const holder=ancestors[ancestors.indexOf(p)-1];
            rendered=holder?.type==='JSXAttribute'?(labelProps.has(holder.name.name)||holder.name.name==='headers'):true;
            break;
          }
        }
        eligible=rendered;
      }
      const attribute=ancestors.findLast(p=>p.type==='JSXAttribute');
      if(parent?.type==='ArrayExpression'&&attribute){
        const comparison=ancestors.some(p=>p.type==='CallExpression'&&['includes','indexOf'].includes(p.callee?.property?.name));
        if(!comparison&&attribute.name.name==='headers')eligible=true;
        if(!comparison&&attribute.name.name==='options'&&parent.elements.length===2&&parent.elements[1]===node)eligible=true;
      }
      if(parent?.type==='CallExpression'&&parent.callee?.name==='mapping'&&[2,3].includes(parent.arguments.indexOf(node)))eligible=true;
      if(eligible){keys.push(node.value);if(translated(node.value))edits.push([node.start,node.end,`${wrap?'{':''}uiText(${JSON.stringify(node.value)})${wrap?'}':''}`]);}
    }
    for(const [key,value] of Object.entries(node)){
      if(['loc','comments','tokens','extra'].includes(key))continue;
      if(Array.isArray(value)){
        for(const child of value)if(child?.type)visit(child,[...ancestors,node]);
      }else if(value?.type)visit(value,[...ancestors,node]);
    }
  }
  visit(ast);
  // Parsing may expose duplicate comment metadata, but edits must be disjoint.
  edits.sort((a,b)=>b[0]-a[0]);
  for(let i=0;i<edits.length-1;i++)if(edits[i+1][1]>edits[i][0])throw new Error('Overlapping UI edits.');
  for(const [start,end,replacement] of edits)source=source.slice(0,start)+replacement+source.slice(end);
  if(edits.length&&!source.includes('t as uiText'))source="import {t as uiText} from './localization.mjs';\n"+source;
  return {source,count:edits.length,keys:[...new Set(keys)].filter(k=>/[a-z]/i.test(k))};
}
if(process.argv.includes('--list')){
  const files=process.argv.slice(process.argv.indexOf('--list')+1),keys=new Set();
  for(const file of files)for(const key of (await localizeSource(await readFile(file,'utf8'))).keys)if(!Object.hasOwn(fa,key))keys.add(key);
  console.log(JSON.stringify([...keys],null,2));
}
if(process.argv.includes('--write')){
  for(const file of process.argv.slice(process.argv.indexOf('--write')+1)){
    if(!/^src\/[a-z-]+\.jsx$/.test(file))throw new Error('Choose a frontend JSX file.');
    const result=await localizeSource(await readFile(file,'utf8'));
    await writeFile(file,result.source);console.log(file,result.count);
  }
}
