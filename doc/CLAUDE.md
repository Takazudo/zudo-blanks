# doc/ - zudo-doc Documentation Site

This is a static zudo-doc project. Node.js 22 or newer and pnpm 10 are required. Published content is English.

## Content and navigation

Write pages under `src/content/docs/`. Each directory has an `index.mdx` for its category. Add top-level sections to `headerNav` in `zfb.config.ts`. Preserve old URLs or add a redirect in the Netlify staging step and the route map in root `README.md`. Use relative links between MDX pages; root-relative MDX links bypass the configured base path.

Claude resource pages are generated during build from the repository root `CLAUDE.md` files and project `.claude/skills` via `claudeResources` in `zfb.config.ts`. Do not edit generated `claude-*` pages. Do not publish machine-global skills.

## Commands

```bash
cd doc
pnpm install --frozen-lockfile
pnpm dev             # http://localhost:4321/pj/zblanks/
pnpm check           # zfb checks
pnpm check:links -- --strict-absolute --strict-anchors
pnpm build           # static output in dist/
pnpm preview         # preview built site
```
