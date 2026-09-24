---
name: notebook
description: Build or extend the local Notion-style documentation notebook (books > chapters > pages) that lives at "documentation and logging/notebook/notebook.html". Use whenever the user asks to explain/document a system, feature, or codebase area as a saved reference, or says "add this to the notebook" / "put this in a book" / "explain X neatly". Not for one-off chat explanations or throwaway artifacts.
---

# Notebook — local Notion-style documentation system

One self-contained HTML file, no server, no external dependencies, no internet
required to open it. Opens via double-click / `file://`. Looks and feels like
Notion. Reviewer should not be able to tell it isn't Notion.

**Canonical file:** `/mnt/c/Users/lenovo/Desktop/documentation and logging/notebook/notebook.html`

(WSL path: `/mnt/c/Users/lenovo/Desktop/documentation and logging/notebook/notebook.html` — this is the Windows Desktop folder per the project's tracker-folder convention, NOT inside the `Manda` repo.)

There is **one file for the whole system**, containing **many books**. Do not
create a new HTML file per request. Every new explanation is a new chapter (or
new page inside an existing chapter) inside the right book, appended to the
same file.

## Structure: Book → Chapter → Page

- **Book** = a subject area (e.g. "Compliance", "FinOps", "RunBooks"). Create
  a new book only when the topic genuinely doesn't belong under an existing
  one — ask if unsure.
- **Chapter** = one session/topic's worth of explanation inside a book (e.g.
  "Full App Walkthrough — 2026-09-23"). Roughly: one chapter per distinct
  thing the user asked to have explained/documented.
- **Page** = one screen of content inside a chapter. Every chapter follows
  this page pattern:
  1. **Overview / KPI page** (first) — real codebase numbers (file count,
     LOC, model count, endpoint count, tool/agent count, migrations,
     providers) presented as stat tiles. Never fabricate numbers — compute
     them with `find`/`grep`/`wc` against the actual repo before writing this
     page.
  2. **Content pages** (however many the topic needs) — the actual
     explanation, one coherent sub-topic per page (e.g. "Data Model", "Scan
     Lifecycle", "Agent Architecture", "API Surface").
  3. **Summary page** (last) — condensed recap, the "if you only read one
     page" page.

## Editing on follow-up asks

When the user asks for more (new topic, more detail, a correction):
1. Read the current `notebook.html` (it's one file — just Read it, or the
   relevant slice via grep for `const NOTEBOOK` / book id).
2. Decide: new book, new chapter in existing book, or new/edited page in
   existing chapter.
3. Edit the `NOTEBOOK` JS data object in place (see Data model below) — do
   not regenerate the whole file from scratch. Use targeted `Edit` calls.
4. Never delete existing books/chapters/pages unless the user explicitly asks
   to remove something.

## Content requirements (non-negotiable, per user preference)

- **Explain with real-life analogies.** Every non-trivial mechanism gets a
  concrete real-world comparison (e.g. explain a scan queue like an airport
  security line, explain a factory pattern like ordering the right adapter
  plug for your country). Not decorative — the analogy should actually carry
  the technical point.
- **Detailed, not skimmed.** The user explicitly wants depth over brevity.
  Err toward more explanation, more examples, real code/CLI snippets pulled
  from the actual repo (never invented).
- **Diagrams required** for anything with steps, flow, or multiple
  interacting parts (scan lifecycle, agent handoff, request flow). Hand-drawn
  / Excalidraw-style look — see Diagrams below.
- **Real content only.** No lorem ipsum, no placeholder numbers, no invented
  API responses. Pull real field names, real endpoint paths, real file:line
  references from the codebase (use `graphify` first if `graphify-out/`
  exists for that repo, per the monorepo CLAUDE.md).

## File format contract

Single `.html` file, fully self-contained:

- **No external CDN, no Google Fonts, no internet dependency of any kind.**
  This file must open and render correctly with the machine offline, next
  year, on a fresh browser profile. Use system font stacks
  (`ui-serif`/Georgia for headings, `ui-sans-serif`/`system-ui` for body,
  `ui-monospace` for code) — layered CSS can still look sharp without a
  webfont.
- All CSS and JS inline in the one file.
- Light + dark theme both defined (`prefers-color-scheme`), token-based, per
  general artifact design fundamentals — this is a doc people reopen for
  years, respect their OS theme.

## Data model (JS, inline in the file)

```js
const NOTEBOOK = {
  books: [
    {
      id: "compliance",           // stable kebab-case id, used in URL hash + sidebar state
      title: "Compliance",
      icon: "shield",             // one of the inline icon keys defined in the file's icon set
      chapters: [
        {
          id: "compliance-walkthrough-2026-09-23",
          title: "Full App Walkthrough",
          date: "2026-09-23",
          pages: [
            { id: "overview", title: "Overview & KPIs", kind: "kpi",     html: "..." },
            { id: "data-model", title: "Data Model",     kind: "content", html: "..." },
            // ...more content pages...
            { id: "summary", title: "Summary",           kind: "summary", html: "..." }
          ]
        }
      ]
    }
  ]
};
```

`html` fields are hand-authored HTML strings (headings, paragraphs, code
blocks, stat-tile grids, diagram containers) — not markdown, not templated.

## Sidebar (left, Notion/OneNote-style)

- Fixed-width column, collapsible on narrow viewports.
- Recursive tree: Book (expand/collapse) → Chapter (expand/collapse) → Page
  (click to open). Chevron rotates on expand, smooth height transition
  (measure `scrollHeight`, animate `max-height`), active page highlighted.
- Simple client-side search box at top filtering by page/chapter/book title.
- Small icon per book; icon set is a handful of inline SVGs defined once in
  the file (no icon font, no emoji-as-icon-system — emoji is fine as
  occasional inline content flavor, not as the nav icon system since it
  renders inconsistently across OSes).

## Diagrams — hand-drawn / Excalidraw look, no library

Don't pull in `rough.js` or any CDN (breaks the offline contract). Instead,
define one reusable inline SVG `<filter>` (`feTurbulence` +
`feDisplacementMap`) applied to plain SVG rects/paths/arrows to get a sketchy,
hand-drawn wobble — genuinely close to Excalidraw's look, zero dependencies.
Build a small reusable JS helper (`drawFlowchart(container, nodes, edges)`)
so future pages can declare a flowchart as data (`{nodes:[...], edges:[...]}`)
instead of hand-writing SVG paths every time.

## KPI / stat tiles

Big-number tiles (value + label + optional short sub-label), laid out in a
responsive grid, one clear accent per tile category (not a rainbow). Numbers
must be computed from the real repo, cited inline (e.g. "54 `@tool` functions
across 3 cloud providers — counted via `grep -ro '@tool'`").

## What NOT to do

- Don't use the `Artifact` tool for this — it publishes to claude.ai, not a
  local file. This must be a real file on disk written with `Write`/`Edit`.
- Don't create a new file per topic — one file, append to it.
- Don't skip the KPI or Summary page even for a small ask — the chapter
  template is fixed.
- Don't fabricate metrics, code snippets, or examples.
