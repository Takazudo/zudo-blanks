import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { Script } from 'node:vm';
import { build } from 'esbuild';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const js=await build({entryPoints:[path.join(root,'src','viewer.js')],bundle:true,write:false,minify:true,format:'iife',target:'es2020',legalComments:'eof'});
const code=js.outputFiles[0].text.replaceAll('</script','<\\/script');
const [shell,style,raw]=await Promise.all([
  readFile(path.join(root,'src','shell.html'),'utf8'),
  readFile(path.join(root,'src','style.css'),'utf8'),
  readFile(path.join(root,'assets','geometry.json'),'utf8'),
]);
const expectedGeometryHash='00835f3a5db6cec4806d0747d274c7c65dff0e1f0f0a8c79316b488f6e5c870e';
const actualGeometryHash=createHash('sha256').update(raw).digest('hex');
if(actualGeometryHash!==expectedGeometryHash)throw new Error(`Frozen Revision 5 geometry changed: ${actualGeometryHash}`);
for(const marker of ['<!--STYLE-->','<!--DATA-->','<!--APP-->'])if(!shell.includes(marker))throw new Error('Missing shell marker '+marker);
const data=JSON.parse(raw);
// Only display copy is localized; canonical geometry and source hashes stay intact.
const descriptions={
 'spider-nest':['An irregular web reaching the sides and mounting supports','Eight layers of shifted radial strands and cross strands reveal a red back board.'],
 'coral-vault':['Flowing nested cavities','Eight layers narrow at uneven depths, with gold accents on selected black boards.'],
 'fault-line':['An asymmetric descending rift','Nine layers alternate rounded and angular cliffs over a red and black depth sequence.'],
 'kumiko-void':['Angular Asanoha lattice','Nine layers combine a cut lattice with flat gold and black facets. Wide is the selected set; standard is a reference-only alternative.'],
 'woven-maze':['Distinct paths at each depth','Nine layers weave seven different lower maze paths between the top and the black floor.'],
};
const checkLabels=['Connected board after cutouts','Continuous upper and lower edges','Dimensions and rail clearance'];
function localizeDesign(design){
 const [subtitle,description]=descriptions[design.id];
 design.subtitle=subtitle;design.description=description;
 design.notes=[description,'This is the Revision 5 visual design model. Manufacturing-adjusted native boards and local CAM evidence are linked from the documentation site.'];
 if(design.variantId)design.variantLabel=design.variantId==='wide'?'Wide · selected':'Standard · reference only';
 for(const [i,check] of (design.checks||[]).entries()){
  check.label=checkLabels[i]||`Geometry check ${i+1}`;
  check.detail='Source geometry validation; see the manufacturing records for native KiCad and CAM results.';
 }
 for(const layer of design.layers){
  layer.nameJa=layer.name;
  layer.note=`${layer.name} layer, ${layer.finish==='mask-only'?'no exposed decorative copper':layer.finish==='enig-fill'?'full ENIG finish':'ENIG artwork'}.`;
  layer.finishLabel=layer.finish==='mask-only'?'No exposed copper':layer.finish==='enig-fill'?'Full ENIG':'ENIG art';
 }
 for(const variant of design.variants||[])localizeDesign(variant);
}
for(const design of data.designs)localizeDesign(design);
const localizedRaw=JSON.stringify(data);
const out=path.join(root,'dist');await mkdir(out,{recursive:true});
const entries=[{name:'index.html',id:null,variant:null},
 ...data.designs.map(d=>({name:`${d.number}-${d.id}.html`,id:d.id,variant:d.variantId||null})),
 ...data.designs.flatMap(d=>(d.variants||[]).map(v=>({name:`${d.number}-${d.id}-${v.variantId}.html`,id:d.id,variant:v.variantId})))];
for(const entry of entries){
 // Callback replacements preserve literal $&, $` and $' sequences in the bundle.
 const html=shell.replace('<!--STYLE-->',()=>`<style>${style}</style>`)
  .replace('<!--DATA-->',()=>`<script>globalThis.PCB_ART_DATA=${localizedRaw.replaceAll('<','\\u003c')};globalThis.PCB_INITIAL_DESIGN=${JSON.stringify(entry.id)};globalThis.PCB_INITIAL_VARIANT=${JSON.stringify(entry.variant)};</script>`)
  .replace('<!--APP-->',()=>`<script>${code}</script>`);
 const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
 if(scripts.length!==2)throw new Error(`Unexpected inline script count: ${entry.name}`);
 for(const script of scripts)new Script(script[1],{filename:entry.name});
 await writeFile(path.join(out,entry.name),html);
 console.log(`${entry.name}: ${(Buffer.byteLength(html)/1024/1024).toFixed(2)} MiB (fully offline)`);
}
