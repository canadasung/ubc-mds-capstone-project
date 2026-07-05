"use client";

import { ActionIcon, Tooltip, useMantineColorScheme, useComputedColorScheme } from "@mantine/core";
import { IconMoon, IconSun } from "@tabler/icons-react";

/**
 * Light/dark mode toggle. Mantine persists the chosen scheme to localStorage
 * automatically (via MantineProvider's default colorSchemeManager), so the
 * choice survives page reloads.
 */
export function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computedColorScheme = useComputedColorScheme("light");

  const toggle = () =>
    setColorScheme(computedColorScheme === "dark" ? "light" : "dark");

  return (
    <Tooltip label={computedColorScheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
      <ActionIcon variant="subtle" onClick={toggle} aria-label="Toggle color scheme">
        {computedColorScheme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}
