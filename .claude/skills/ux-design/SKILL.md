---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics.
license: Complete terms in LICENSE.txt
---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work - the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:
- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:
- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

## Project-Specific: Health Dashboard Design Rules

Learned from building and critiquing 10 dashboard prototypes for a multi-metric Garmin health data dashboard. These rules apply whenever designing or modifying dashboard layouts for this project.

### Must-Haves
- **Distinct color per metric** — single most important thing for multi-metric dashboards. Each of the 7-8 metrics (HR, stress, SpO2, respiration, HRV, sleep, skin temp) gets its own color that carries through summary bar, chart line, and card accent.
- **Summary bar** at top with 4-6 headline numbers — instant overview before scrolling to detail charts.
- **Equal-weight grid** (e.g., 4x2) — consistent card sizing prevents false hierarchy between metrics.
- **Secondary contextual stats** on each card — resting HR alongside avg, weekly HRV alongside nightly, sleep score alongside hours. Don't leave cards as just a chart + title.
- **High chart-line contrast** against card backgrounds — chart readability is non-negotiable. Test that lines are clearly visible on their card's background color.
- **Readable labels** — no abbreviations that force decoding (STRESS.LVL, BODY.BATT = bad).

### Don'ts
- **No green-on-black** — WCAG borderline, eye fatigue compounds across 8 metrics.
- **No pastel card backgrounds** — compete with chart lines for attention (pink line on pink bg = unreadable).
- **No pure black backgrounds** — dark navy/charcoal is fine, `#000` is not.
- **No uniform chart color** across all metrics — destroys the cross-metric comparison channel.
- **No terminal cosplay** ($ prompts, abbreviated commands) — cognitive overhead without function.
- **No inconsistent card sizes** — implies hierarchy that may not match actual use.
- **No huge headers** eating vertical space — the title is seen every page load, it doesn't need 80px.
- **No scroll-heavy layouts** — cross-metric pattern recognition requires seeing metrics simultaneously.

### Design Spectrum That Works
- **Best balance:** Dark navy/charcoal bg + colored lines + clean grid + summary bar + sub-stats
- **Also strong:** White/cream with high-contrast monospace, clean borders, equal-weight grid
- **Combine strengths:** Dark telemetry's color system + editorial's summary bar + brutalist's data density

### Font Pairings That Worked
- **Dark dashboards:** DM Mono, IBM Plex Mono, JetBrains Mono for numbers
- **Light dashboards:** Geist/Geist Mono, Source Sans 3 + Crimson Pro (serif)
- **Character fonts:** Instrument Sans, Plus Jakarta Sans, Literata (serif), Nunito

### Background Texture Techniques
- Starfield dots via `radial-gradient` with random positioning
- Noise via SVG `feTurbulence` filter
- Gradient mesh for subtle depth
