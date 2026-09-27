import { defineConfig } from "zfb/config";
import { zudoDoc } from "@takazudo/zudo-doc/config";

export default defineConfig({
  ...zudoDoc({
    siteName: "zudo-blanks",
    favicon: "/img/favicon.ico",
    siteDescription: "Blank panel PCB designs for modular synthesizers",
    siteUrl: "https://takazudomodular.com",
    base: "/pj/zblanks/",
    githubUrl: "https://github.com/Takazudo/zudo-blanks",
    onBrokenMarkdownLinks: "error",
    llmsTxt: true,
    sidebarResizer: true,
    sidebarToggle: true,
    tocToggle: true,
    imageEnlarge: true,
    dynamicPageTransition: true,
    docHistory: true,
    assetViewer: true,
    claudeResources: {
      claudeDir: "../.claude",
      projectRoot: ".",
      scanRoot: "..",
    },
    footer: {
      links: [],
      copyright: "Copyright © 2026 Takazudo. Built with zudo-doc.",
    },
    headerNav: [
      { label: "Overview", path: "/docs/overview", categoryMatch: "overview" },
      { label: "Catalog", path: "/docs/catalog", categoryMatch: "catalog" },
      { label: "Manufacturing", path: "/docs/manufacturing", categoryMatch: "manufacturing" },
      { label: "Workflow", path: "/docs/workflow", categoryMatch: "workflow" },
      { label: "How-to", path: "/docs/how-to", categoryMatch: "how-to" },
      { label: "Claude", path: "/docs/claude", categoryMatch: "claude" },
    ],
    headerRightItems: [
      {
        type: "component",
        component: "theme-toggle",
      },
      {
        type: "component",
        component: "search",
      },
    ],
  }),
  // Netlify copies dist/ into /pj/zblanks/. Keep public files flat in dist/
  // so deployed URLs have one base prefix and the built-image checker resolves them.
  copyPublicWithBase: false,
});
