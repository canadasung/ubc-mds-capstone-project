"use client";

/**
 * Page shell — ports the top-level layout of prototype_master.py:
 * a collapsible left search panel (Mantine AppShell navbar) and a right area
 * with the view switcher + active view. No st.rerun() choreography needed.
 */

import {
  AppShell,
  Box,
  Divider,
  Group,
  ScrollArea,
  Switch,
  Title,
} from "@mantine/core";

import { PanelToggle, SearchPanel } from "@/components/SearchPanel";
import { ViewSwitcher } from "@/components/ViewSwitcher";
import { ResultsSummary } from "@/components/ResultsSummary";
import { ResultsArea } from "@/components/ResultsArea";
import { useSearchStore } from "@/lib/store";

export default function Page() {
  const panelOpen = useSearchStore((s) => s.panelOpen);
  const togglePanel = useSearchStore((s) => s.togglePanel);
  const debug = useSearchStore((s) => s.debug);
  const setDebug = useSearchStore((s) => s.setDebug);

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 320,
        breakpoint: "sm",
        collapsed: { desktop: !panelOpen, mobile: !panelOpen },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <PanelToggle open={panelOpen} onClick={togglePanel} />
            <Title order={5} style={{ whiteSpace: "nowrap" }}>
              Species Name Synonym Search
            </Title>
          </Group>
          <Switch
            label="Debug"
            size="sm"
            checked={debug}
            onChange={(e) => setDebug(e.currentTarget.checked)}
          />
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        {/* ScrollArea lets the search panel scroll when "Advanced options" is
            expanded and its content is taller than the navbar. */}
        <ScrollArea h="100%" type="auto" scrollbarSize={8}>
          <SearchPanel />
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main>
        <Box>
          <Group justify="space-between" align="center" wrap="nowrap">
            <ViewSwitcher />
            <ResultsSummary />
          </Group>
          <Divider my="md" />
          <ResultsArea />
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
