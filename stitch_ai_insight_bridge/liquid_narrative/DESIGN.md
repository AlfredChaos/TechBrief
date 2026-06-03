---
name: Liquid Narrative
colors:
  surface: '#fcf8fb'
  surface-dim: '#dcd9dc'
  surface-bright: '#fcf8fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f5'
  surface-container: '#f0edef'
  surface-container-high: '#eae7ea'
  surface-container-highest: '#e4e2e4'
  on-surface: '#1b1b1d'
  on-surface-variant: '#414755'
  inverse-surface: '#303032'
  inverse-on-surface: '#f3f0f2'
  outline: '#717786'
  outline-variant: '#c1c6d7'
  surface-tint: '#005bc1'
  primary: '#0058bc'
  on-primary: '#ffffff'
  primary-container: '#0070eb'
  on-primary-container: '#fefcff'
  inverse-primary: '#adc6ff'
  secondary: '#bc000a'
  on-secondary: '#ffffff'
  secondary-container: '#e2241f'
  on-secondary-container: '#fffbff'
  tertiary: '#9e3d00'
  on-tertiary: '#ffffff'
  tertiary-container: '#c64f00'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a41'
  on-primary-fixed-variant: '#004493'
  secondary-fixed: '#ffdad5'
  secondary-fixed-dim: '#ffb4aa'
  on-secondary-fixed: '#410001'
  on-secondary-fixed-variant: '#930005'
  tertiary-fixed: '#ffdbcc'
  tertiary-fixed-dim: '#ffb595'
  on-tertiary-fixed: '#351000'
  on-tertiary-fixed-variant: '#7c2e00'
  background: '#fcf8fb'
  on-background: '#1b1b1d'
  surface-variant: '#e4e2e4'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  article-body:
    fontFamily: Noto Serif
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  article-body-cn:
    fontFamily: Noto Serif SC
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.8'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 48px
  xl: 80px
  container-max: 1120px
  gutter: 24px
---

## Brand & Style
The design system is a premium, bilingual content ecosystem inspired by Apple’s Human Interface Guidelines, evolved through a "Liquid Glass" lens. It balances the precision of high-end editorial design with the expressive energy of "Dopamine Gradients." 

The core aesthetic relies on deep translucency, layered depth, and structural clarity. It aims to evoke a sense of calm authority and professional curation. The UI feels like physical glass sheets floating over a shifting spectrum of light, where vibrant color is used surgically to guide attention and reward interaction.

**Design Style: Glassmorphism / Modern Apple-Inspired**
- **Surfaces:** High-index background blurs and semi-transparent fills.
- **Accents:** Vivid, multi-color gradients used for highlights rather than primary fills.
- **Tone:** Professional, sophisticated, and intentionally spacious.

## Colors
The palette centers on "System Neutrals" to ensure content readability, punctuated by "Dopamine Gradients" that simulate light refraction.

- **Primary Neutrals:** Use #F9F9FB for light mode and #1C1C1E for dark mode. Text should maintain a 7:1 contrast ratio against these backgrounds.
- **Glass Fills:** Use semi-transparent whites (Light) or deep grays (Dark) with a `backdrop-filter: blur(20px)`.
- **Gradients:** Use the Dopamine Gradients exclusively for 1px borders, progress bars, active states, and decorative "blooms" located in the corners of containers. These should feel like light leaking through the edges of a glass pane.

## Typography
This design system employs a dual-stack approach to accommodate English and Simplified Chinese while maintaining an editorial feel.

- **UI Elements:** Use **Inter** (as a proxy for SF Pro) for all functional UI components, labels, and navigation. 
- **Content:** Use **Noto Serif** for article body text to provide a literary, premium reading experience.
- **Bilingual Strategy:** For Chinese text, increase the line-height by 10-15% compared to English to account for the visual density of glyphs. Headlines in Chinese should use a slightly heavier weight to maintain visual impact.
- **Hierarchy:** Use large, confident displays for titles with tight letter spacing, contrasted by generous leading in the body copy.

## Layout & Spacing
The layout follows a "Breathing Grid" philosophy—prioritizing white space (negative space) to reduce cognitive load.

- **Desktop:** A 12-column fixed grid centered in the viewport, with a maximum width of 1120px. 
- **Mobile:** A single-column fluid layout with 20px side margins.
- **Spacing Rhythm:** Use a base-8 increment. Containers and article sections should be separated by `lg` (48px) or `xl` (80px) units to create a clear "stage" for the content.
- **Safe Areas:** Cards and glass containers should utilize `md` (24px) internal padding to ensure text does not feel cramped against the rounded corners.

## Elevation & Depth
Depth is created through "Tonal Stacking" and backdrop effects rather than traditional drop shadows.

1.  **Level 0 (Base):** The solid background color (#F9F9FB).
2.  **Level 1 (Surface):** Glassmorphic containers with 1px semi-transparent borders. Use `box-shadow: 0 4px 30px rgba(0, 0, 0, 0.05)`.
3.  **Level 2 (Active/Floating):** Modals and dropdowns. Use a stronger blur (30px) and a subtle 1px "inner highlight" at the top edge to simulate thickness.
4.  **Dopamine Glow:** Apply a very soft, high-radius colored outer glow (shadow-color derived from the gradient) to primary call-to-action elements to make them appear to emit light.

## Shapes
The shape language is defined by "Continuous Curvature" (Squircular influence).

- **Standard Containers:** Use `rounded-lg` (16px) for most content cards and secondary surfaces.
- **Feature Cards:** Use `rounded-xl` (24px) for hero elements and large content clusters.
- **Interactive Elements:** Buttons and tags use a "Pill" shape (fully rounded) to contrast against the more architectural card shapes.
- **Borders:** All glass elements must have a 1px border. In light mode, use `rgba(255,255,255,0.4)`; in dark mode, use `rgba(255,255,255,0.1)`.

## Components
- **Buttons:** Primary buttons should use a Dopamine Gradient background with white text. Secondary buttons should be glassmorphic with a 1px gradient border.
- **Cards:** Utilize "Corner Blooms"—a subtle radial gradient glow in the top-right or bottom-left corner of the card that only appears on hover.
- **Search Inputs:** Full-width glass bar with a blurred background. The cursor/caret should use a primary accent color.
- **Article Lists:** Use a clean, borderless list style with generous vertical spacing. Metadata (date, category) should use the `label-caps` typography style in a muted gray.
- **Bilingual Toggle:** A small, pill-shaped switch that uses a subtle glass blur, ensuring the active language is highlighted with a soft drop shadow.
- **Progress Indicators:** Linear bars at the top of articles should use a Dopamine Gradient to show reading progress.