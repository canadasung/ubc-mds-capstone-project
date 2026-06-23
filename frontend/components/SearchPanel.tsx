"use client";

/**
 * SearchPanel — ports the left search column of prototype_master.py:
 *   - search form (Enter submits, like st.form)
 *   - "Database selection" collapse: per-source checkboxes
 *   - Select all / Unselect all / Suggest buttons
 *   - Live progress bar while search runs
 *   - "Did you mean?" suggestions parsed from empty results
 */

import { useState } from "react";
import {
  ActionIcon,
  Box,
  Button,
  Checkbox,
  Collapse,
  Divider,
  Group,
  Modal,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChevronDown, IconChevronRight, IconSearch } from "@tabler/icons-react";

import { useSearchStore } from "@/lib/store";
import { GROUP_LABELS, SOURCES, SOURCE_KEYS, keyForApiName, type SourceGroup } from "@/lib/sources";
import { suggest } from "@/lib/api";

const GROUP_ORDER: SourceGroup[] = ["backbone", "symbiota", "independent"];

export function SearchPanel() {
  const query = useSearchStore((s) => s.query);
  const setQuery = useSearchStore((s) => s.setQuery);
  const submit = useSearchStore((s) => s.submit);
  const selectedSources = useSearchStore((s) => s.selectedSources);
  const toggleSource = useSearchStore((s) => s.toggleSource);
  const setAllSources = useSearchStore((s) => s.setAllSources);
  const setSources = useSearchStore((s) => s.setSources);
  const isSearching = useSearchStore((s) => s.isSearching);
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const submittedSources = useSearchStore((s) => s.submittedSources);
  const cachedData = useSearchStore((s) => s.cachedData);
  const forceResubmit = useSearchStore((s) => s.forceResubmit);

  const [advancedOpen, advanced] = useDisclosure(true);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const handleSuggest = async () => {
    if (!query.trim()) {
      setSuggestError(
        "Please type in a valid search query to use automatic source suggestions."
      );
      return;
    }
    setIsSuggesting(true);
    setSuggestError(null);
    try {
      const res = await suggest(query.trim());
      if (res.sources.length === 0) {
        setSuggestError(
          "Could not identify kingdom. Please type in a valid search query to use the automatic source suggestions."
        );
        return;
      }
      const keys = res.sources.map(keyForApiName).filter((k) => SOURCE_KEYS.includes(k));
      setSources(keys);
    } catch {
      setSuggestError("Suggest request failed. Is the server running?");
    } finally {
      setIsSuggesting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSuggestError(null);

    const q = query.trim();
    if (!q) return;

    const sourcesUnchanged =
      selectedSources.length === submittedSources.length &&
      selectedSources.every((s) => submittedSources.includes(s));

    if (cachedData && q === submittedQuery && sourcesUnchanged) {
      setConfirmOpen(true);
      return;
    }

    submit();
  };

  return (
    <Stack gap="md">
      <Title order={4}>Search</Title>

      <form onSubmit={handleSubmit}>
        <Stack gap="sm">
          <TextInput
            placeholder="Enter species name (e.g. Ursus arctos)"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            leftSection={<IconSearch size={16} />}
            aria-label="Search query"
            autoComplete="off"
          />
          <Button type="submit" fullWidth loading={isSearching} disabled={isSearching}>
            Search
          </Button>
        </Stack>
      </form>

      <Divider />

      {/* Database selection */}
      <Box>
        <Button
          variant="subtle"
          fullWidth
          justify="space-between"
          rightSection={
            advancedOpen ? (
              <IconChevronDown size={16} />
            ) : (
              <IconChevronRight size={16} />
            )
          }
          onClick={advanced.toggle}
        >
          Database selection
        </Button>

        <Collapse in={advancedOpen}>
          <Stack gap="sm" mt="sm">
            <Stack gap={4}>
              <Button
                size="compact-sm"
                variant="default"
                fullWidth
                onClick={() => {
                  setSuggestError(null);
                  setAllSources(true);
                }}
              >
                Select all
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                fullWidth
                onClick={() => {
                  setSuggestError(null);
                  setAllSources(false);
                }}
              >
                Unselect all
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                fullWidth
                loading={isSuggesting}
                onClick={handleSuggest}
              >
                Suggest
              </Button>
            </Stack>

            {suggestError && (
              <Text c="red" size="xs">{suggestError}</Text>
            )}

            <Stack gap="xs">
              {GROUP_ORDER.map((group) => (
                <Box key={group}>
                  <Text size="sm" fw={600} mb={4}>
                    {GROUP_LABELS[group]}
                  </Text>
                  <Stack gap={4} pl="xs">
                    {SOURCES.filter((s) => s.group === group).map((s) => (
                      <Checkbox
                        key={s.key}
                        label={s.label}
                        size="sm"
                        checked={selectedSources.includes(s.key)}
                        onChange={() => toggleSource(s.key)}
                      />
                    ))}
                  </Stack>
                </Box>
              ))}
            </Stack>
          </Stack>
        </Collapse>
      </Box>

      <Modal
        opened={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="No changes detected"
        size="sm"
      >
        <Text size="sm">
          The query and selected sources haven't changed. Do you want to re-query
          all selected sources and refresh the results?
        </Text>
        <Group mt="lg" justify="flex-end">
          <Button variant="default" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              setConfirmOpen(false);
              forceResubmit();
            }}
          >
            Re-query all sources
          </Button>
        </Group>
      </Modal>
    </Stack>
  );
}

/** Small reusable collapse toggle for the panel header (used in page.tsx). */
export function PanelToggle({
  open,
  onClick,
}: {
  open: boolean;
  onClick: () => void;
}) {
  return (
    <Tooltip label={open ? "Collapse search panel" : "Expand search panel"}>
      <ActionIcon variant="subtle" onClick={onClick} aria-label="Toggle search panel">
        {open ? <IconChevronRight size={18} /> : <IconChevronDown size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}
