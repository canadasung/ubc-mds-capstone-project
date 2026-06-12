"use client";

/**
 * SearchPanel — ports the left search column of prototype_master.py:
 *   - search form (Enter submits, like st.form)
 *   - "Database selection" collapse: per-source checkboxes
 *   - Select all / Unselect all / Suggest buttons
 *   - "Did you mean?" suggestions parsed from a 404 response
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
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChevronDown, IconChevronRight, IconSearch } from "@tabler/icons-react";

import { useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { GROUP_LABELS, SOURCES, type SourceGroup } from "@/lib/sources";
import { ApiError } from "@/lib/types";

const FUNGI_SOURCES = ["gbif", "col", "genbank", "index_fungorum", "mushroomobs", "symbiota_mycoportal", "symbiota_lichen"];
const PLANTAE_SOURCES = ["gbif", "col", "genbank", "tropicos", "symbiota_bryophyte", "symbiota_cch2", "symbiota_sernec", "symbiota_nansh", "symbiota_swbiodiversity", "symbiota_macroalgae", "symbiota_pterido", "symbiota_neherbaria", "symbiota_midatlantic"];
const ANIMALIA_SOURCES = ["gbif", "col", "genbank"];

const SUGGEST_MAP: Record<string, string[]> = {
  "podospora anserina": FUNGI_SOURCES,
  "amanita muscaria": FUNGI_SOURCES,
  "taraxacum officinale": PLANTAE_SOURCES,
  "ergates spiculatus": ANIMALIA_SOURCES,
  "ursus arctos": ANIMALIA_SOURCES,
};

function mockSuggest(query: string): string[] | null {
  return SUGGEST_MAP[query.trim().toLowerCase()] ?? null;
}

const GROUP_ORDER: SourceGroup[] = ["backbone", "symbiota", "independent"];

export function SearchPanel() {
  const query = useSearchStore((s) => s.query);
  const setQuery = useSearchStore((s) => s.setQuery);
  const submit = useSearchStore((s) => s.submit);
  const selectedSources = useSearchStore((s) => s.selectedSources);
  const toggleSource = useSearchStore((s) => s.toggleSource);
  const setAllSources = useSearchStore((s) => s.setAllSources);
  const setSources = useSearchStore((s) => s.setSources);

  const [advancedOpen, advanced] = useDisclosure(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const search = useSearch();
  const error = search.error as ApiError | null;

  const handleSuggest = () => {
    const sources = mockSuggest(query);
    if (!sources) {
      setSuggestError(
        "Could not identify kingdom. Please type in a valid search query to use the automatic source suggestions."
      );
      return;
    }
    setSuggestError(null);
    setSources(sources);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSuggestError(null);
    submit();
  };

  return (
    <Stack gap="md">
      <Title order={4}>Search</Title>

      <form onSubmit={handleSubmit}>
        <Stack gap="sm">
          <TextInput
            placeholder="Enter species name (e.g. Podospora anserina)"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            leftSection={<IconSearch size={16} />}
            aria-label="Search query"
          />
          <Button type="submit" fullWidth loading={search.isFetching}>
            Search
          </Button>
        </Stack>
      </form>

      {/* Error + "Did you mean?" */}
      {error && (
        <Box>
          <Text c="red" size="sm">
            {error.message}
          </Text>
          {error.available && error.available.length > 0 && (
            <Box mt="xs">
              <Text size="sm" mb={4}>
                Did you mean:
              </Text>
              <Group gap="xs">
                {error.available.map((s) => (
                  <Button
                    key={s}
                    size="compact-xs"
                    variant="light"
                    onClick={() => {
                      setQuery(s);
                      // submit on next tick so the store has the new query
                      setTimeout(submit, 0);
                    }}
                  >
                    {s}
                  </Button>
                ))}
              </Group>
            </Box>
          )}
        </Box>
      )}

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
