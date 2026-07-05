"use client";

/**
 * Page shell — ports the top-level layout of prototype_master.py:
 * a collapsible left search panel (Mantine AppShell navbar) and a right area
 * with the view switcher + active view. No st.rerun() choreography needed.
 */

import { useEffect, useState } from "react";
import {
  AppShell,
  Box,
  Button,
  Divider,
  Group,
  ScrollArea,
  Title,
} from "@mantine/core";
import { IconInfoCircle } from "@tabler/icons-react";

import { PanelToggle, SearchPanel } from "@/components/SearchPanel";
import { ViewSwitcher } from "@/components/ViewSwitcher";
import { ResultsSummary } from "@/components/ResultsSummary";
import { ResultsArea } from "@/components/ResultsArea";
import { TutorialModal, hasTutorialCookie } from "@/components/TutorialModal";
import { ColorSchemeToggle } from "@/components/ColorSchemeToggle";
import { useSearchStore } from "@/lib/store";
import { useLiveSearchEffect } from "@/lib/hooks";

export default function Page() {
  // Registered once here so only a single SSE connection is ever opened.
  useLiveSearchEffect();

  const panelOpen = useSearchStore((s) => s.panelOpen);
  const togglePanel = useSearchStore((s) => s.togglePanel);

  const [tutorialOpen, setTutorialOpen] = useState(false);

  useEffect(() => {
    if (!hasTutorialCookie()) {
      setTutorialOpen(true);
    }
  }, []);

  return (
    <>
      <TutorialModal opened={tutorialOpen} onClose={() => setTutorialOpen(false)} />
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
          <Group h="100%" px="md" gap="sm" justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap">
              <PanelToggle open={panelOpen} onClick={togglePanel} />
              <Title order={5} style={{ whiteSpace: "nowrap" }}>
                Species Name Synonym Search
              </Title>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <ColorSchemeToggle />
              <Button
                size="compact-sm"
                variant="subtle"
                leftSection={<IconInfoCircle size={16} />}
                onClick={() => setTutorialOpen(true)}
              >
                Tutorial
              </Button>
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Navbar p="md">
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
    </>
  );
}
