import { defineConfig } from "@takazudo/zfb/config";
import { zudoDoc } from "@takazudo/zudo-doc/config";

export default defineConfig({
  ...zudoDoc({
    siteName: "zudo-blanks",
    favicon: "/img/favicon.ico",
    siteDescription: "Blank panel PCB designs for modular synthesizers",
    siteUrl: "https://zudo-blanks.zudolab.dev",
    base: "/",
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
    assetViewerIndex: true,
    assetViewerIndexing: false,
    agentExport: false,
    mcp: false,
    adapter: "@takazudo/zfb-adapter-cloudflare",
    siteTreeNavSecondary: ["claude", "claude-md", "claude-skills", "archive"],
    home: {
      wide: true,
      introMarkdown: "Blank panels, layered PCB art and practical source files for modular synthesizers.\n\n[Browse panels](/docs/panels/) · [Explore 3D & files](/docs/models/)",
    },
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
      { label: "Panels", path: "/docs/panels/", categoryMatch: "panels" },
      { label: "3D & Files", path: "/docs/models/", categoryMatch: "models" },
      { label: "Manufacturing", path: "/docs/manufacturing/", categoryMatch: "manufacturing" },
      { label: "Guides", path: "/docs/guides/", categoryMatch: "guides" },
      { label: "About", path: "/docs/overview/", children: [
        { label: "About the project", path: "/docs/overview/", categoryMatch: "overview" },
        { label: "Contributor resources", path: "/docs/claude/", categoryMatch: "claude" },
        { label: "Historical references", path: "/docs/archive/", categoryMatch: "archive" },
      ] },
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
});
