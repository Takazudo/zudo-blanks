#!/usr/bin/env python3
"""Check overlay file links, frontmatter and header/category consistency; no zudo-doc build."""
from pathlib import Path
import argparse
import json
import re


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overlay',type=Path,default=Path(__file__).resolve().parent.parent/'docs-overlay')
    parser.add_argument('--skip-assets',action='store_true')
    args=parser.parse_args()
    root=args.overlay.resolve(); content=root/'src/content/docs'
    errors=[]; documents=sorted(content.rglob('*.mdx')); link_count=0
    for p in documents:
        s=p.read_text()
        if not s.startswith('---\n') or '\n---\n' not in s[4:]:
            errors.append(f'{p.name}: missing frontmatter'); continue
        front,body=s[4:].split('\n---\n',1)
        for key in ('title','description','sidebar_position'):
            if not re.search(rf'^{key}:',front,re.M): errors.append(f'{p.name}: missing {key}')
        prose=re.sub(r'```[\s\S]*?```','',body)
        if re.search(r'^# ',prose,re.M): errors.append(f'{p.name}: body H1 duplicates title')
        for target in re.findall(r'\]\(([^)\s]+)\)',prose):
            if target.startswith(('http:','https:','#','mailto:')): continue
            target=target.split('#',1)[0].split('?',1)[0];link_count+=1
            if target.startswith('/assets/'):
                if not args.skip_assets and not (root/'public'/target.lstrip('/')).is_file():
                    errors.append(f'{p.relative_to(content)}: missing {target}')
            elif target.endswith(('.md','.mdx')):
                if not (p.parent/target).resolve().is_file():errors.append(f'{p.relative_to(content)}: missing {target}')
        for category in re.findall(r'<CategoryNav category="([^"]+)"',body):
            if category != p.parent.name: errors.append(f'{p.name}: CategoryNav mismatch')
    config=(root/'zfb.config.ts').read_text()
    categories=sorted(re.findall(r'categoryMatch: "([^"]+)"',config))
    expected=sorted(p.name for p in content.iterdir() if p.is_dir())
    if categories!=expected: errors.append(f'Header categories {categories} != {expected}')
    report={'passed':not errors,'scope':'Static MDX/resource consistency, not a zudo-doc compile','documents':len(documents),'localLinks':link_count,'categories':categories,'assetsChecked':not args.skip_assets,'errors':errors}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(bool(errors))

if __name__=='__main__': main()
