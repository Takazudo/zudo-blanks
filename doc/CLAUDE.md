# doc/ - Docusaurus Documentation Site

## Sidebar Structure

The documentation uses 4 sidebar sections defined in `/doc/sidebars.js`:

- **overviewSidebar** - Project overview
- **howToSidebar** - How-to guides
- **miscSidebar** - Miscellaneous
- **inboxSidebar** - INBOX (temporary workspace)

## Adding New Documentation Pages

1. Create `.md` or `.mdx` file in appropriate `/doc/docs/` subdirectory
2. Add the doc ID to the corresponding sidebar array in `/doc/sidebars.js`
3. If creating a new category, add corresponding entry in sidebar config

## Development Commands

```bash
cd doc
pnpm install          # Install dependencies
pnpm start            # Dev server (port 43621, zblanks.localhost)
pnpm run check        # Run typecheck + lint + format check
pnpm run build        # Production build
```
