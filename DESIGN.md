---
name: Rex Explorer
description: Force-directed Last.fm artist similarity explorer
colors:
  bg-base: "#0d0d0d"
  bg-surface: "#161616"
  bg-input: "#1a1a1a"
  bg-elevated: "#222222"
  bg-hover: "#262626"
  bg-chip: "#252525"
  border-panel: "#2e2e2e"
  border-control: "#333333"
  border-chip: "#383838"
  border-row: "#2a2a2a"
  text-primary: "#ffffff"
  text-body: "#e0e0e0"
  text-display: "#d0d0d0"
  text-tag: "#c8c8c8"
  text-muted: "#aaaaaa"
  text-secondary: "#888888"
  accent-vinyl-red: "#e05a54"
  accent-vinyl-red-hover: "#f07a74"
  amber-border: "#3a2e18"
  amber-focus: "#6a5228"
  amber-placeholder: "#5a4820"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "22px"
    fontWeight: 300
    lineHeight: 1.2
    letterSpacing: "0.1em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  bio:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    letterSpacing: "0.02em"
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    letterSpacing: "0.02em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "18px"
components:
  input-search:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-body}"
    rounded: "{rounded.lg}"
    padding: "10px 34px 10px 14px"
  input-connect:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-body}"
    rounded: "{rounded.lg}"
    padding: "10px 34px 10px 14px"
  panel:
    backgroundColor: "{colors.bg-surface}"
    rounded: "{rounded.xl}"
    padding: "0"
  chip-tag:
    backgroundColor: "{colors.bg-chip}"
    textColor: "{colors.text-tag}"
    rounded: "{rounded.sm}"
    padding: "3px 9px"
  control-button:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-tag}"
    rounded: "{rounded.md}"
    size: "36px"
  link-external:
    textColor: "{colors.accent-vinyl-red}"
---

# Design System: Rex Explorer

## 1. Overview

**Creative North Star: "The Late Library"**

rex-explorer is a card catalog you wander after hours. The graph is the protagonist, and every visible surface around it is the room that holds the catalog: dim, warm in feel if not in temperature, the brass lamp on the desk and nothing else lit. The user is alone, headphones on, no one else awake. The interface volunteers nothing it does not have to. Discovery is the reward; the chrome refuses to compete with it.

The system explicitly rejects four houses. It is not a SaaS dashboard (no card grids, no hero metrics, no blue-by-default). It is not a Spotify clone (no green accent, no album-art rails, no "Made for You"). It is not an AI demo (no gradient text, no glassmorphism, no neon). And it is not Web 2.0 social (no likes, no follower counts, no trending). Where the path of least resistance points toward any of those, the answer is to do less.

**Key Characteristics:**
- Dark surfaces that absorb attention instead of reflecting it.
- Tinted neutrals carrying ~95% of the pixels; one accent (Faded Vinyl Red) under 5%.
- A single elevated surface (the detail-panel / landing-popup) carries shadow; everything else is flat.
- Type does the heavy lifting. Hierarchy through scale and weight, not color.
- Persistent-open lifted panels — body content stays visible by default so voice / dictation users can read it without hovering.

## 2. Colors

A single-accent palette: warm-tinted near-black neutrals with one muted coral-red action color used on under 5% of any screen. The neutrals carry the room; the accent is reserved for destructive actions and external escape hatches.

### Primary
- **Faded Vinyl Red** (`#e05a54`): the only chromatic color in the system. Used on (a) the Clear Chain button border + label on hover, (b) the "View on Last.fm →" external link, and (c) by extension any future destructive action or external-handoff. Hover state lifts to `#f07a74`. The color reads as worn analog ink, not a UI alert.

### Neutral
- **Hall** (`#0d0d0d`): the body background. The room.
- **Catalog Card** (`#161616`): elevated panel surfaces — detail-panel and landing-popup. The lifted plane.
- **Drawer** (`#1a1a1a`): inputs, search results dropdowns, control buttons, loading indicator. The interactive plane.
- **Brass Edge** (`#222222`): the placeholder background behind the artist hero image while it loads.
- **Hover Wash** (`#262626`): result-list and control-button hover state.
- **Chip Stock** (`#252525`): the tag chip background (for genres / mood).
- **Hairline Steel** (`#2e2e2e`): the panel border. 1px, never wider.
- **Wire** (`#333333`): input and control borders.
- **Chip Edge** (`#383838`): tag chip border.
- **Row Rule** (`#2a2a2a`): the divider that appears under the detail-panel header on hover.

### Text Neutrals
- **Lamp White** (`#ffffff`): hero artist names, loud titles. Reserved.
- **Reading White** (`#e0e0e0`): default body text in inputs and the detail panel listener line.
- **Display White** (`#d0d0d0`): the wide-tracked uppercase display ("REX EXPLORER") at landing and in the disclaimer popup. Slightly receded by design — the title is a sign on the wall, not a logo.
- **Tag Text** (`#c8c8c8`): genre chip labels.
- **Quiet Gray** (`#aaaaaa`): bio prose in the slide-up body.
- **Index Gray** (`#888888`): hints, secondary buttons, the "Find connection from…" hint, the tagline ("Explore the world around any artist") at landing.

### Path-Find Accent (functional, not decorative)
- **Amber Trace** (`#3a2e18` border, `#6a5228` focus, `#5a4820` placeholder): the chain-find input uses an amber-family border family to distinguish "I am looking for a path" from "I am searching the catalog". This is functional differentiation, not palette expansion. Treat it as a sibling to the primary search input, not a new role.

### Named Rules

**The One Voice Rule.** Faded Vinyl Red appears on under 5% of any screen, ever. It signals destructive intent or external handoff and nothing else. If it starts decorating a header or a divider, it has lost its meaning.

**The Tinted Neutral Rule.** Every "black" and "white" in this system is tinted toward warmth. There is no `#000` and no `#fff` outside the existing `#ffffff` for hero artist names (which sits on a darkened gradient and does not feel pure). Future neutrals must keep the warm cast.

**The Amber Border Rule.** Amber-family borders are reserved for the chain-find input and any future "trace a path" affordance. Do not use amber as decoration, accent, or text color.

## 3. Typography

**Display Font:** system stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`).
**Body Font:** same.
**Label / Caption Font:** same.

The system uses a single sans-serif family — the platform's native UI font — across every level. The character of the type comes from weight and tracking contrast, not from font selection. Display is light and wide; headlines are bold and tight; body is regular at 14px. The pairing reads as a librarian's handwriting on index cards: consistent hand, deliberate weights.

### Hierarchy
- **Display** (300, 22px, line-height 1.2, letter-spacing 0.1em, uppercase, with text-shadow for depth): the "REX EXPLORER" wordmark in the landing search panel and in the landing disclaimer popup header. Two contexts only.
- **Headline** (700, 20px, line-height 1.2, white, with text-shadow): the artist name in the detail-panel hero.
- **Body** (400, 14px, line-height 1.5): default body text in inputs and the listener-count line.
- **Bio** (400, 13px, line-height 1.65, color Quiet Gray): the slide-up artist biography.
- **Label** (400, 12px, letter-spacing 0.02em): the search tagline, the connect-hint, the loading indicator, the listener counts in result rows, the external "View on Last.fm →" link.
- **Caption** (400, 11–11.5px, letter-spacing 0.02em): the genre tag chips and the listener-count secondary text inside search results.

### Named Rules

**The Two-Display-Surfaces Rule.** Display type (the wide-tracked uppercase wordmark) appears in exactly two places: the landing search panel and the landing-popup header. It does not show up as section headers, modal titles, or empty-state hero text. If a third use appears, the rule has been broken — collapse to Headline.

**The Quiet-Bio Rule.** Bio prose is set at 13px / 1.65 — looser than body, smaller than body. The looseness invites reading; the smaller size keeps the bio subordinate to the artist name and tags above it. Do not bump bio to body size.

## 4. Elevation

The system is flat by default with one lifted surface. Body, graph canvas, search inputs, controls, and chips all sit on the base plane with 1px borders for separation. The only elements that carry shadow are the lifted panels: the detail-panel and the landing-popup. Both use the same shadow value, both sit at the same elevation, and there is no second elevation tier.

The graph itself never carries shadow. Force-directed nodes float on the base plane; depth in the graph comes from animation (force simulation) and color, not from shadow.

### Shadow Vocabulary
- **Lifted Panel** (`box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6)`): used on the detail-panel and the landing-popup. Long, soft, low-opacity — the shadow of a heavy book set on a desk in low light. Diffuse; does not feel digital.

### Named Rules

**The One-Elevation Rule.** There is one shadow in this system, used on two surfaces. New floating elements (modals, tooltips, command palettes) must either reuse this exact shadow value or stay flat with a 1px border. Do not introduce a second elevation tier.

**The No-Glow Rule.** The accent color does not carry a glow, halo, or blur effect, anywhere. Faded Vinyl Red is a flat ink on flat paper; there is no light source within the UI.

## 5. Components

### Search Inputs
The two inputs (primary search, connect / chain-find) share shape and differ only in border color family.

- **Shape:** 8px corner radius (`{rounded.lg}`), 1px border.
- **Primary search:** Drawer background, Wire border. Focus shifts the border to `#666` — a quiet pop, no glow, no shadow.
- **Connect search:** Drawer background, Amber Trace border (`#3a2e18`). Focus shifts the border to `#6a5228`. Placeholder is `#5a4820`. The amber is functional differentiation, not theming.
- **Padding:** `10px 34px 10px 14px` — the right padding reserves space for the inline clear (×) button.
- **Clear button:** absolute-positioned (×), Spine Gray, becomes Quiet Gray on hover. No background, no border. Hit zone is 32×32 with the 15px glyph centered, so a dictation user can reach it without precise pointer work.
- **Result dropdown:** flush continuation of the input — same width, no top border, bottom corners 8px. Items are 8px / 14px padded rows, name on left, listener count (Caption / Spine Gray) on right. Hover row is Hover Wash.

### Lifted Panels (detail-panel, landing-popup)
The signature surface of the system. Both share frame, position, and shadow; they differ in interior structure.

- **Frame:** 600px wide, 12px corner radius, Catalog Card background, 1px Hairline Steel border, Lifted Panel shadow. Pinned to bottom-left at 18px / 18px.
- **Header:** holds the title (Display for landing-popup, Headline + listener count for detail-panel) and any always-visible status. A persistent 1px Row Rule divider sits below it, separating header from body.
- **Body:** persistent-open by default. Bio prose, links, and disclaimer copy are always visible — no hover-to-reveal gesture. The doctrine change is deliberate: voice and dictation users cannot hover, and the panel's job is to keep information available.
- **Inner padding:** 12px top / 16px sides / 16px bottom.
- **Close button:** 36×36 circle (sized for voice/dictation reach), semi-transparent Hall background, fades from 0.7 to 1.0 opacity on hover. Top-right, 8px inset. Used on the detail-panel only; the landing-popup is auto-dismissed by graph activation, no close.

### Tag Chips
Genre / mood labels in the detail panel.

- **Shape:** 4px corner radius, 1px Chip Edge border.
- **Background:** Chip Stock.
- **Text:** Tag Text, 11.5px, letter-spacing 0.02em.
- **Padding:** 3px 9px.
- **State:** display-only. No hover state, no selection — these are read, not clicked.

### Control Buttons (zoom in / out / center)
Bottom-right cluster, vertical stack. Only visible after a graph becomes active.

- **Shape:** 36×36 square, 6px corner radius, 1px Wire border.
- **Background:** Drawer.
- **Text / icon:** Tag Text, 18px glyph.
- **Hover:** background lifts to Hover Wash, text to Lamp White.
- **Tooltip:** appears to the left of the button on hover, light pill (`#e8e8e8` background, `#111` text, 13px / 500 weight, 5px radius). Inverse colors from the rest of the system — these are momentary callouts, not part of the room.

### Clear-Chain Button
The single accented secondary action.

- **Shape:** 6px corner radius, 1px Wire border, transparent background.
- **Text:** Index Gray, 12px.
- **Hover:** text and border both shift to Faded Vinyl Red. The accent is earned by the destructive intent.

### External Link ("View on Last.fm →")
- **Color:** Faded Vinyl Red, 12px / 500 weight, letter-spacing 0.01em, no underline at rest.
- **Hover:** lifts to Faded Vinyl Red Hover, underline appears.
- **The arrow** (→) is part of the label, not a separate icon. It signals the external handoff.

### Loading Indicator
Top-right pill. Drawer background, Wire border, 6px radius, Index Gray text at 12px. No spinner, no animation. Presence is the signal.

### Named Rules

**The Two-Inputs-One-Shape Rule.** Search and connect share radius, padding, and shape. They differ only in border family (Wire vs. Amber Trace). New inputs must inherit this shape; do not introduce a third radius for inputs.

**The Persistent-Open Rule.** Lifted panels show their full content by default. Body never collapses on rest. Voice and dictation users cannot reach hover-only content, and the panel's job is to keep information available, not to hide it behind a gesture. New panel-shaped components inherit this pattern.

## 6. Do's and Don'ts

### Do:
- **Do** keep Faded Vinyl Red (#e05a54) under 5% of any screen. Reserve for destructive actions and external handoffs.
- **Do** use the system font stack across every level. Hierarchy comes from weight (300 / 400 / 700) and scale (22 / 20 / 14 / 13 / 12 / 11.5), not from font selection.
- **Do** keep the lifted-panel shadow at exactly `0 8px 32px rgba(0, 0, 0, 0.6)`. New panels reuse this value or stay flat.
- **Do** pair every hover-only reveal with a non-hover path: keyboard focus, tap-to-toggle, or persistent state. The primary user dictates input — hover-only is inaccessible.
- **Do** tint every neutral toward warmth. The room is dim and lamp-lit, not industrial.
- **Do** keep lifted panels persistent-open. Header and body are both visible at rest; body content does not collapse.
- **Do** keep the graph itself shadowless. Force-directed nodes float on the base plane.
- **Do** carry text-shadow on the display wordmark (`0 0 24px #0d0d0d, 0 0 48px #0d0d0d`) so it reads cleanly over the background animated graph at landing.

### Don't:
- **Don't** build SaaS dashboard patterns. No card grids of identical tiles, no hero-metric templates ("8.2M listeners" + "↑ 12%" + accent line), no blue-default UI chrome.
- **Don't** mimic Spotify. No green accent, no sidebar of album-art tiles, no "Made for You" rail. The dominant music app's conventions are off-limits.
- **Don't** ship the AI demo aesthetic. No gradient text (`background-clip: text` on a gradient), no glassmorphism (decorative blur), no neon-on-black, no "magical" overstated motion.
- **Don't** import Web 2.0 social patterns. No likes, follower counts, comments, share buttons, or trending lists. The user is alone in the library.
- **Don't** use side-stripe borders. `border-left` / `border-right` greater than 1px as a colored accent is forbidden. Use full 1px borders, background tints, or leading numbers / icons.
- **Don't** introduce a second elevation tier. One shadow, two surfaces. New floating UI is either flat with a 1px border or reuses the Lifted Panel shadow exactly.
- **Don't** color the accent with a glow, halo, or `box-shadow` ring. Faded Vinyl Red is flat ink.
- **Don't** use em dashes in copy. Commas, colons, semicolons, periods, parentheses. Also not `--`.
- **Don't** introduce a third input radius. Search and connect both use 8px. New inputs inherit.
- **Don't** widen the panel border. 1px, Hairline Steel, always.
- **Don't** scale display type beyond its two existing surfaces (landing search panel, landing popup header). Use Headline (20 / 700) for new prominent titles.
- **Don't** reach for a modal as the first thought. Exhaust inline disclosure (slide-up body, in-line panel) first. Modals are usually laziness.
