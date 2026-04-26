# Design System Documentation: The Digital Architect

## 1. Overview & Creative North Star

### The Creative North Star: "The Observational Void"
This design system moves away from the "neon-on-black" tropes of 80s synthwave. Instead, it adopts a **Cyber-noir** philosophy: a high-end, architectural approach where the UI feels like a sophisticated terminal found within a deep-space research vessel. It is designed for the "Digital Architect"—users who live in their IDEs and dashboards for hours. 

We achieve a "High-End Editorial" feel by breaking the rigid, boxed-in nature of standard dashboards. We use **intentional asymmetry**, allowing elements to breathe within a vast, dark canvas. By prioritizing tonal depth over structural lines, the interface feels less like a website and more like a projected holographic interface.

**Key Principles:**
*   **Atmospheric Depth:** Use layers of darkness to create a sense of infinite space.
*   **Luminous Intent:** Color is never decorative; it is a signal. Light should feel "emitted" from the screen.
*   **Optical Comfort:** Every token is tuned to prevent retinal fatigue during long-duration immersion.

---

## 2. Colors

The palette is anchored in `#0a0c10` (Obsidian), providing a near-perfect black that reduces light bleed. 

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning. Boundaries must be defined solely through background color shifts or subtle tonal transitions. To separate a sidebar from a main feed, transition from `surface` to `surface_container_low`. 

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. Nesting should follow a "Light-to-Dark" recession for depth:
*   **Level 0 (Base):** `surface` (#111318) - The infinite background.
*   **Level 1 (Sections):** `surface_container_low` (#1a1c20) - Large layout blocks.
*   **Level 2 (Cards):** `surface_container` (#1e2024) - Primary interaction zones.
*   **Level 3 (Popovers):** `surface_container_high` (#282a2e) - Elements that sit "closest" to the user.

### The "Glass & Gradient" Rule
Floating elements (Modals, Tooltips) must use **Glassmorphism**. Apply `surface_container` with 60% opacity and a `backdrop-filter: blur(12px)`. 
*   **Signature Texture:** For primary CTAs or AI headers, use a subtle linear gradient from `primary` (#9cefff) to `primary_container` (#00daf3) at a 135-degree angle to provide a sense of "liquid energy."

---

## 3. Typography

**Primary Typeface:** Manrope. 
A modern geometric sans-serif that balances tech-efficiency with human readability.

*   **Display (Large/Medium/Small):** Use for high-impact data points or section intros. Set with `-0.02em` letter spacing to feel "locked in."
*   **Headline (Large/Medium/Small):** Used for primary navigation titles. Always in `on_surface`.
*   **Body (Large/Medium):** The workhorse. Set in `on_surface_variant` (#bac9cc) to reduce the harsh contrast of pure white-on-black.
*   **Label (Medium/Small):** Used for metadata, AI status tags, and micro-copy. 

**Editorial Hierarchy:** Contrast `Display-sm` (tight, bold) against `Body-md` (wide line-height, muted color) to create an authoritative, sophisticated layout.

---

## 4. Elevation & Depth

### The Layering Principle
Depth is achieved through **Tonal Layering**. If you need to separate two pieces of content, do not reach for a divider. Move one element to `surface_container_lowest` (#0c0e12) to create a "sunken" well, or `surface_bright` (#37393e) to create a "raised" platform.

### Ambient Shadows
For floating panels, use "The Architect’s Shadow":
*   **Color:** `primary` (#00daf3) at 5% opacity.
*   **Blur:** 40px.
*   **Spread:** -5px.
This creates a subtle "glow" rather than a shadow, mimicking light reflecting off a surface.

### The "Ghost Border" Fallback
Where containment is functionally required (e.g., input fields), use a **Ghost Border**: `outline_variant` (#3b494c) at 20% opacity. For active AI states, this border transitions into a **Glowing Pulse** using `primary`.

---

## 5. Components

### AI Interaction States (Signature Component)
*   **Thinking:** The container border uses a CSS "conic-gradient" animation between `primary` and `secondary`, blurred at 2px to create a soft, rotating aura.
*   **Skill Invocation:** A `hexagonal pattern` overlay (opacity 0.05) fades in over the container, with a `scanline overlay` moving vertically to indicate active processing.

### Buttons
*   **Primary:** Solid `primary_container` background with `on_primary_container` text. No border.
*   **Secondary:** `surface_container_highest` background with `secondary` text. 
*   **Tertiary:** Ghost style. No background. `on_surface_variant` text that glows to `primary` on hover.

### Inputs & Text Areas
*   **Base:** `surface_container_lowest` background. 
*   **Active:** Border becomes `primary` at 40% opacity with a 2px outer "neon" glow.
*   **Error:** Background shifts to a subtle 5% tint of `error`.

### Cards & Lists
**Forbid divider lines.** Use 24px - 32px of vertical whitespace to denote separation. For list items, use a subtle hover state change to `surface_container_high` with a 2px `primary` vertical "accent bar" on the left edge.

---

## 6. Do's and Don'ts

### Do
*   **Use Asymmetry:** Place high-level stats off-center to create visual interest.
*   **Embrace the Void:** Let large sections of the screen remain `surface` (#111318) to rest the user's eyes.
*   **Use Muted Slate:** Always use `on_surface_variant` for long-form reading to prevent "halving" (visual ghosting).

### Don't
*   **No Hard Dividers:** Never use a solid 1px line to separate content.
*   **No Pure White:** Avoid `#ffffff`. The brightest text should be `on_surface` (#e2e2e8).
*   **No Sharp Corners:** Stick to the **Roundedness Scale**. Use `md` (0.375rem) for cards and `full` for status chips. This softens the "cyber" look, making it feel premium rather than aggressive.
*   **No High-Frequency Patterns:** Use the hexagonal pattern sparingly (only in AI active states) to avoid visual noise.

---

## 7. Motion & Feedback
Transitions should be "Optical & Organic."
*   **State Changes:** 300ms Ease-Out.
*   **AI Pulse:** A breathing animation (opacity 0.4 to 0.8) on `primary` borders to indicate the system is "alive."
*   **Scanlines:** A subtle 2% opacity overlay that moves at a very slow rate (60s loop) to provide a "hardware" texture to the digital space.