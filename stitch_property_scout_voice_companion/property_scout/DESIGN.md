---
name: Property Scout
colors:
  surface: rgba(255, 255, 255, 0.88)
  surface-dim: '#dddad2'
  surface-bright: '#fdf9f1'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f7f3eb'
  surface-container: '#f1ede5'
  surface-container-high: '#ece8e0'
  surface-container-highest: '#e6e2da'
  on-surface: '#1c1c17'
  on-surface-variant: '#3f4946'
  inverse-surface: '#31302b'
  inverse-on-surface: '#f4f0e8'
  outline: '#6f7976'
  outline-variant: '#bec9c5'
  surface-tint: '#0e6a5b'
  primary: '#005145'
  on-primary: '#ffffff'
  primary-container: '#0f6b5c'
  on-primary-container: '#99e8d5'
  inverse-primary: '#86d5c3'
  secondary: '#50625d'
  on-secondary: '#ffffff'
  secondary-container: '#d3e7e0'
  on-secondary-container: '#566863'
  tertiary: '#3c4a43'
  on-tertiary: '#ffffff'
  tertiary-container: '#53625b'
  on-tertiary-container: '#cdddd4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a2f2de'
  primary-fixed-dim: '#86d5c3'
  on-primary-fixed: '#00201a'
  on-primary-fixed-variant: '#005144'
  secondary-fixed: '#d3e7e0'
  secondary-fixed-dim: '#b7cbc4'
  on-secondary-fixed: '#0d1f1b'
  on-secondary-fixed-variant: '#394a45'
  tertiary-fixed: '#d6e6dd'
  tertiary-fixed-dim: '#bacac1'
  on-tertiary-fixed: '#101e19'
  on-tertiary-fixed-variant: '#3b4a43'
  background: '#fdf9f1'
  on-background: '#1c1c17'
  surface-variant: '#e6e2da'
  muted: '#5C6B64'
  user-bubble: '#E8F2EF'
  assistant-bubble: '#FFFDF9'
  error-text: '#8A2F2F'
  error-bg: '#FDEEEE'
  recording-red: '#EF4444'
typography:
  display-lg:
    fontFamily: Libre Caslon Text
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.2'
  display-lg-mobile:
    fontFamily: Libre Caslon Text
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Libre Caslon Text
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-sm:
    fontFamily: Libre Caslon Text
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: 0.05em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.5'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  max-width: 1200px
---

## Brand & Style

The design system is anchored in a "Lifestyle-First" philosophy, prioritizing a precise and calm user experience over the sheer volume of listings. The aesthetic follows a **Humanist Minimalism** approach, utilizing a "warm paper" digital environment to evoke trust and high-end concierge service. It moves away from generic tech aesthetics toward an editorial, citation-backed atmosphere that feels like a curated architectural journal.

The emotional response should be one of stability and clarity. By using a grounded color palette and structured, non-bubbly shapes, the interface positions itself as a reliable advisor. The tone is sophisticated yet approachable, designed to reduce the anxiety of high-stakes real estate decisions through transparency and technical precision.

## Colors

The palette is derived from organic, professional tones that suggest quality and longevity.

- **Primary (Eucalyptus Teal):** The signature brand color, used for primary actions, success states, and the "Connect" status.
- **Background (Warm Paper):** A textured, non-white base that provides a comfortable reading environment and a premium, analog feel.
- **Surface:** Semi-transparent white used for cards and overlays to allow the warmth of the background to subtly bleed through.
- **Ink (Secondary):** A deep, near-black forest green used for high-contrast text and structural definition.
- **Muted:** A desaturated sage used for secondary information and metadata.
- **Chat Interface:** Distinctive, soft hues differentiate participants—cool mint for users and a warm cream for the assistant.

## Typography

This system employs a tripartite typographic hierarchy to categorize information types:

- **Editorial Serif (Libre Caslon Text):** Used for headlines, property titles, and society names. This adds character and an authoritative, premium tone.
- **Functional Sans (Inter):** The primary workhorse for the UI, body text, and chat bubbles. It ensures maximum legibility and a clean, modern interface.
- **Technical Mono (JetBrains Mono):** Reserved for quantitative and system-level data, including rent values, match scores, and unique property IDs.

All rent values must be formatted in the INR currency standard (e.g., ₹32,000) using the monospace font to emphasize precision.

## Layout & Spacing

The layout philosophy follows a **Fixed Grid** approach to maintain editorial control over content density and white space.

- **Desktop:** 12-column grid within a 1200px max-width container. Gutters are set at 24px with 40px outer margins.
- **Tablet:** 8-column grid with 16px gutters and 24px margins.
- **Mobile:** 4-column grid with 12px gutters and 16px margins. 

The vertical rhythm is based on an 8px scale. Spacing between related components should use `sm` (16px), while major sections are separated by `lg` (40px) or `xl` (64px) to ensure a calm, uncluttered feel.

## Elevation & Depth

This system avoids soft, diffused shadows in favor of **Structural Outlines**. Depth is communicated through:

- **Borders:** Instead of shadows, use 1px solid borders using the Ink color (#1C2A24) at 12% opacity. This creates a crisp, architectural boundary.
- **Tonal Layering:** The primary background is the base. Pure White surfaces (88% opacity) provide the next level of elevation for cards and modals.
- **Active States:** Interactive focus is denoted by a 1px solid Eucalyptus Teal border, ensuring clear affordance without adding visual bulk.

## Shapes

The shape language is structured and professional. A strict **0-4px radius** is applied to all primary containers and cards to avoid a "bubbly" or overly consumer-tech appearance.

- **Standard Radius:** 4px (Soft) for cards, inputs, and primary containers.
- **Small Radius:** 2px for nested elements or small UI components.
- **Pills:** Only reserved for specialized "Phase Badges" and the "Mic Button" to signify their unique interactive or status-driven nature.

## Components

- **Rent Display:** Always rendered in JetBrains Mono with the ₹ symbol and proper comma separators.
- **Mic Button:** A perfect circle that pulses with a `recording-red` glow when active, providing immediate tactile feedback during voice search.
- **Phase Badges:** Styled as small pills with `label-caps` typography in uppercase. These use a light Eucalyptus Teal background for positive phases.
- **Citation Rows:** A structured block containing a linked Serif title, a small Mono topic chip, and an Inter snippet. This reinforces the "citation-backed" principle.
- **Chat Bubbles:** User bubbles use a subtle Teal tint with right alignment; Assistant bubbles use a warm cream tint with left alignment. Both utilize 4px rounded corners.
- **Buttons:** Primary buttons use solid Eucalyptus Teal with white text. They should have a 4px corner radius and use the `label-caps` style for text.
- **Status Indicators:** Success/Connect utilizes the primary Eucalyptus Teal; Errors use a specific red (#8A2F2F) text on a soft red (#FDEEEE) background container.