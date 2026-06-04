import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

export default defineConfig({
  site: "https://modellens.pages.dev",
  base: "/docs",
  integrations: [
    starlight({
      title: "Model Lens",
      description: "Observability-first platform for local AI — trace, replay, compare, and understand how models behave on your hardware.",
      logo: {
        src: "./src/assets/logo.svg",
      },
      social: {
        github: "https://github.com/kevinjobin1/model-lens",
      },
      head: [
        {
          tag: "link",
          attrs: { rel: "icon", href: "/docs/favicon.svg", type: "image/svg+xml" },
        },
      ],
      customCss: ["./src/styles/custom.css"],
      sidebar: [
        {
          label: "Getting Started",
          items: [
            { label: "Introduction", slug: "" },
            { label: "Quick Start", slug: "getting-started" },
            { label: "Vision", slug: "vision" },
            { label: "Architecture", slug: "architecture" },
            { label: "Roadmap", slug: "roadmap" },
          ],
        },
        {
          label: "Guides",
          collapsed: false,
          items: [
            { label: "Providers", slug: "guides/providers" },
            { label: "Benchmarks", slug: "guides/benchmarks" },
            { label: "Skills", slug: "guides/skills" },
            { label: "Prompt Packs", slug: "guides/prompt-packs" },
            { label: "Trace Replay", slug: "guides/replay" },
          ],
        },
        {
          label: "Reference",
          collapsed: false,
          items: [
            { label: "CLI Commands", slug: "reference/cli" },
            { label: "Run Schema", slug: "reference/run-schema" },
            { label: "Event Schema", slug: "reference/event-schema" },
            { label: "Provider Contract", slug: "reference/provider-contract" },
            { label: "Design System", slug: "design" },
          ],
        },
        {
          label: "Contributing",
          items: [
            { label: "Contributor Guide", slug: "contributing" },
            { label: "Changelog", slug: "changelog" },
          ],
        },
      ],
      editLink: {
        baseUrl: "https://github.com/kevinjobin1/model-lens/edit/main/apps/docs/",
      },
      lastUpdated: true,
      favicon: "/docs/favicon.svg",
    }),
  ],
});
