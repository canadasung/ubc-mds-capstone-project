/**
 * Mantine CSS custom properties, named once so a typo becomes a compile-time
 * reference error instead of a silently-ignored `var()` (which falls back to
 * unset/inherit with no build error, lint warning, or visual-diff signal).
 *
 * Used by components that hand-style elements with inline `style` props
 * (e.g. the Relations and Timeline views' custom graph/timeline rendering)
 * rather than Mantine's own styled components, which resolve these
 * automatically. Values are Mantine's own variable names; see
 * https://mantine.dev/styles/css-variables/ for the full list.
 */
export const MANTINE_BODY = "var(--mantine-color-body)";
export const MANTINE_TEXT = "var(--mantine-color-text)";
export const MANTINE_DIMMED = "var(--mantine-color-dimmed)";
export const MANTINE_DEFAULT_BORDER = "var(--mantine-color-default-border)";
export const MANTINE_DEFAULT_HOVER = "var(--mantine-color-default-hover)";
export const MANTINE_BLUE_6 = "var(--mantine-color-blue-6)";
export const MANTINE_BLUE_LIGHT = "var(--mantine-color-blue-light)";
