import type { JSX } from "@takazudo/zfb/zudo-react/jsx-runtime";
import { routeContext } from "virtual:zudo-doc-route-context";
import {
  createRouteContext,
  type RouteContextPayload,
} from "@takazudo/zudo-doc/route-context";
import { createChrome } from "@takazudo/zudo-doc/chrome";
import { DocHistoryBoundary as DocHistory } from "@takazudo/zudo-doc/doc-history-area";
import { defineChromeBindings } from "@takazudo/zudo-doc/chrome-bindings";
import { chromeBindings } from "virtual:zudo-doc-chrome-bindings";
import migratedDocHistoryMeta from "../../.zfb/migrated-doc-history-meta.json";

const ctx = routeContext as unknown as RouteContextPayload;
const routeCtx = createRouteContext(ctx);
const { renderDocPage } = createChrome(routeCtx, {
  ...chromeBindings,
  ...defineChromeBindings({
    DocHistory,
    // Explicit prior paths supplement Git's rename heuristic for this migration.
    // Native chrome renders the metadata; unaffected pages keep package values.
    docHistoryMeta: {
      ...chromeBindings.docHistoryMeta,
      ...migratedDocHistoryMeta,
    },
  }),
});

export const frontmatter = { title: "Docs" };

export function paths(): Array<{ params: { slug: string[] }; props: unknown }> {
  const locale = routeCtx.defaultLocale;
  const source = routeCtx.resolveNavSource(locale, undefined);
  return routeCtx.buildDocRouteEntries({
    source,
    locale,
    routeSig: `docs;${locale}`,
  }).map((item) => ({
    params: { slug: item.slugParams },
    props: item.props,
  }));
}

type PageArgs = { params: { slug: string[] } } & Record<string, unknown>;

export default function DocsPage(props: PageArgs): JSX.Element {
  return renderDocPage(props as never, {
    locale: routeCtx.defaultLocale,
    docHistoryContentDir: routeCtx.settings.docsDir,
  });
}
