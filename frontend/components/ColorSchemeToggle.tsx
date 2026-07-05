"use client";

import { ActionIcon, Tooltip, useMantineColorScheme } from "@mantine/core";
import { IconMoon, IconSun } from "@tabler/icons-react";

/**
 * Light/dark mode toggle. Mantine persists the chosen scheme to localStorage
 * automatically (via MantineProvider's default colorSchemeManager), so the
 * choice survives page reloads. Uses Mantine's own `toggleColorScheme()`
 * rather than hand-rolled flip logic, since it also briefly disables CSS
 * transitions during the swap to avoid a visible flash as every themed
 * element's background/border changes at once.
 *
 * Both icons are always rendered and switched purely via CSS
 * ([data-mantine-color-scheme] in globals.css), rather than conditionally on
 * a hook value, so server and client markup are always identical. Branching
 * the icon choice on a color-scheme hook's value during render would
 * mismatch for a returning visitor who previously chose dark: the server has
 * no access to localStorage and always assumes the default (light), while
 * the client's first render already sees the persisted "dark" value,
 * causing a hydration error.
 */
export function ColorSchemeToggle() {
  const { toggleColorScheme } = useMantineColorScheme();

  return (
    <Tooltip label="Toggle color scheme">
      <ActionIcon variant="subtle" onClick={toggleColorScheme} aria-label="Toggle color scheme">
        <IconSun className="color-scheme-icon-light" size={18} />
        <IconMoon className="color-scheme-icon-dark" size={18} />
      </ActionIcon>
    </Tooltip>
  );
}
