import { defineConfig } from "zfb/config";
import { zudoDoc } from "@takazudo/zudo-doc/config";

// The package owns routes, MDX components, schema, layout, and styling.
// Keep the initializer package, TypeScript config, pages, and CSS imports.
// The source bundle checked framework documentation on 2026-09-24 UTC.
export default defineConfig(
  zudoDoc({
    siteName: "PCB Art — Fabrication Notes",
    siteDescription: "Revision 5 source and manufacturing review for five layered PCB art designs",
    defaultLocale: "en",
    entryDocSlug: "overview/project",
    githubUrl: false,
    editUrl: false,
    llmsTxt: true,
    cjkFriendly: true,
    sidebarResizer: true,
    sidebarToggle: true,
    tocToggle: true,
    imageEnlarge: true,
    assetViewer: false,
    docHistory: false,
    bodyFootUtilArea: { docHistory: false, viewSourceLink: false },
    home: {
      wide: true,
      introMarkdown: [
        "# Layered PCB art, ready for review",
        "",
        "Spider Nest, Coral Vault, Fault Line, Kumiko Void, and Woven Maze.",
        "",
        "Revision 5 geometry, editable native boards, layer resources, and open manufacturing questions.",
        "",
        "[Project status](/docs/overview/project) · [Continue in KiCad](/docs/manufacturing/kicad) · [Open review items](/docs/manufacturing/open-items)",
        "",
        "![Five design previews](/assets/pcb-art/images/pcb-art-previews-overview.png)",
      ].join("\n"),
    },
    headerNav: [
      { label: "Overview", path: "/docs/overview", categoryMatch: "overview" },
      { label: "Designs", path: "/docs/designs", categoryMatch: "designs" },
      { label: "Engineering", path: "/docs/engineering", categoryMatch: "engineering" },
      { label: "Manufacturing review", path: "/docs/manufacturing", categoryMatch: "manufacturing" },
      { label: "Assembly", path: "/docs/assembly", categoryMatch: "assembly" },
      { label: "Handoff", path: "/docs/handoff", categoryMatch: "handoff" },
    ],
    headerRightItems: [
      { type: "component", component: "theme-toggle" },
      { type: "component", component: "search" },
    ],
    footer: { links: [], copyright: "Takazudo Modular · PCB Art / Revision 5" },
  }),
);
