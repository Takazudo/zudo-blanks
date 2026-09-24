import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { Script } from 'node:vm';
import { build } from 'esbuild';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=process.env.PCB_PREVIEW_PYTHON || path.join(root,'.venv','bin','python');
const gen=spawnSync(python,[path.join(root,'scripts','build_geometry.py')],{cwd:root,stdio:'inherit'});
if(gen.status!==0)process.exit(gen.status||1);
const js=await build({entryPoints:[path.join(root,'src','viewer.js')],bundle:true,write:false,minify:true,format:'iife',target:'es2020',legalComments:'eof'});
const code=js.outputFiles[0].text.replaceAll('</script','<\\/script');
const [shell,style,raw]=await Promise.all([
  readFile(path.join(root,'src','shell.html'),'utf8'),
  readFile(path.join(root,'src','style.css'),'utf8'),
  readFile(path.join(root,'assets','geometry.json'),'utf8'),
]);
for(const marker of ['<!--STYLE-->','<!--DATA-->','<!--APP-->'])if(!shell.includes(marker))throw new Error('Missing shell marker '+marker);
const data=JSON.parse(raw);
const out=path.join(root,'dist');await mkdir(out,{recursive:true});
const entries=[{name:'index.html',id:null,variant:null},
 ...data.designs.map(d=>({name:`${d.number}-${d.id}.html`,id:d.id,variant:d.variantId||null})),
 ...data.designs.flatMap(d=>(d.variants||[]).map(v=>({name:`${d.number}-${d.id}-${v.variantId}.html`,id:d.id,variant:v.variantId})))];
for(const entry of entries){
 // Callback replacements preserve literal $&, $` and $' sequences in the bundle.
 const html=shell.replace('<!--STYLE-->',()=>`<style>${style}</style>`)
  .replace('<!--DATA-->',()=>`<script>globalThis.PCB_ART_DATA=${raw.replaceAll('<','\\u003c')};globalThis.PCB_INITIAL_DESIGN=${JSON.stringify(entry.id)};globalThis.PCB_INITIAL_VARIANT=${JSON.stringify(entry.variant)};</script>`)
  .replace('<!--APP-->',()=>`<script>${code}</script>`);
 const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
 if(scripts.length!==2)throw new Error(`Unexpected inline script count: ${entry.name}`);
 for(const script of scripts)new Script(script[1],{filename:entry.name});
 await writeFile(path.join(out,entry.name),html);
 console.log(`${entry.name}: ${(Buffer.byteLength(html)/1024/1024).toFixed(2)} MiB (fully offline)`);
}
