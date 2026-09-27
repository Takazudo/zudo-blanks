#!/usr/bin/env python3
"""Create a NEW official zudo-doc scaffold and apply this handoff's overlay."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path,help='New directory. Existing destinations are not modified.')
    parser.add_argument('--print-command',action='store_true',help='Print initializer arguments and exit without writing.')
    args = parser.parse_args()
    handoff = Path(__file__).resolve().parent.parent
    overlay = handoff/'docs-overlay'
    destination = args.destination.expanduser().resolve()
    command = ['pnpm','create','zudo-doc',str(destination),'--name','zudo-pcb-art-doc','--yes','--lang','ja','--no-i18n','--pm','pnpm','--no-install','--no-git','--no-doc-history']
    if args.print_command:
        print(json.dumps(command,ensure_ascii=False,indent=2))
        return
    if destination.exists():
        parser.error('Destination already exists. Choose a new directory or merge the overlay manually.')
    if not overlay.is_dir():
        parser.error('docs-overlay is missing beside documentation/.')
    if shutil.which('node') is None or shutil.which('pnpm') is None:
        parser.error('Install Node.js 22+ and pnpm, then rerun this command.')
    version = subprocess.check_output(['node','--version'],text=True).strip()
    if int(version.lstrip('v').split('.')[0]) < 22:
        parser.error('Node.js 22+ is required by the verified zudo-doc instructions.')
    # shell=False: destination is always passed as one argument, including spaces.
    subprocess.run(command, check=True)
    if not (destination/'package.json').is_file() or not (destination/'zfb.config.ts').is_file():
        raise RuntimeError('Initializer output did not contain expected project files. Review before proceeding.')
    starter = destination/'src/content/docs'
    (destination/'handoff-backup').mkdir(parents=True,exist_ok=True)
    if starter.exists():
        backup = destination/'handoff-backup/initializer-docs'
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(starter),str(backup))
    shutil.copy2(destination/'zfb.config.ts', destination/'handoff-backup/initializer-zfb.config.ts')
    shutil.copytree(overlay,destination,dirs_exist_ok=True)
    subprocess.run([sys.executable,str(handoff/'documentation/copy_site_assets.py'),str(destination)],check=True)
    print('\nOverlay applied. Run the following in the created directory:')
    print('pnpm install\npnpm check\npnpm build\npnpm dev')
    print('No install, build, git commit, deployment, or upload was performed by this helper.')

if __name__ == '__main__':
    main()
