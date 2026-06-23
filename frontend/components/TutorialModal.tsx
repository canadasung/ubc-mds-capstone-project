"use client";

import { useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  Group,
  List,
  Modal,
  Stack,
  Stepper,
  Text,
  Title,
} from "@mantine/core";

const COOKIE_NAME = "tutorial_dismissed";

function setDismissedCookie() {
  const expires = new Date(Date.now() + 365 * 864e5).toUTCString();
  document.cookie = `${COOKIE_NAME}=1; expires=${expires}; path=/; SameSite=Lax`;
}

export function hasTutorialCookie(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie.split("; ").some((c) => c.startsWith(`${COOKIE_NAME}=`));
}

const STEPS: { label: string; title: string; body: React.ReactNode }[] = [
  {
    label: "Welcome",
    title: "Welcome to Species Name Synonym Search",
    body: (
      <Stack gap="sm">
        <Text>
          This tool helps you discover all synonyms for a species name
          across multiple biodiversity databases.
        </Text>
        <Text>
          It was developed as part of UBC Master of Data Science's capstone project,
          in partnership with the Beaty Biodiversity Museum, to support curators who
          work with biological collections.
        </Text>
        <Text size="sm" c="dimmed">
          Click <strong>Next</strong> to learn how to use the tool.
        </Text>
      </Stack>
    ),
  },
  {
    label: "Search",
    title: "Step 1 — Enter a Species Name",
    body: (
      <Stack gap="sm">
        <Text>
          Use the search panel on the left to type in a scientific species name (e.g.{" "}
          <em>Podospora anserina</em> or <em>Amanita muscaria</em>), select the databases to
          query, then click <strong>Search</strong>.
        </Text>
        <Text>
          If you aren&apos;t sure which sources to query, we recommend using the
          &ldquo;suggest&rdquo; button to automatically select relevant sources by the kingdom
          of your search query, rather than querying all sources.
        </Text>
      </Stack>
    ),
  },
  {
    label: "Results",
    title: "Step 2 — Explore the Results",
    body: (
      <Stack gap="sm">
        <Text>After searching, switch between views using the tabs at the top of the results area:</Text>
        <List size="sm" spacing={6}>
          <List.Item>
            <strong>Overview</strong>: all synonyms returned from the search and which sources list each one
          </List.Item>
          <List.Item>
            <strong>Relations</strong>: an interactive graph of synonyms grouped by genus and/or species
          </List.Item>
          <List.Item>
            <strong>Timeline</strong>: a chronological view of when names were published and by whom
          </List.Item>
          <List.Item>
            <strong>Taxonomy</strong>: a table view to compare taxonomic classification from different sources
          </List.Item>
          <List.Item>
            <strong>Detail</strong>: detailed search results from all databases, with an option to download results as a CSV file
          </List.Item>
        </List>
      </Stack>
    ),
  },
  {
    label: "Done",
    title: "Step 3 — Go To Original Sources",
    body: (
      <Stack gap="sm">
        <Text>
          That&apos;s it! All views include links back to the websites that the information was
          retrieved from using APIs, which you can visit for more detailed information.
        </Text>
        <Text>
          You can re-open this tutorial at any time by clicking the <strong>Tutorial</strong>{" "}
          button in the top-right corner of the header.
        </Text>
      </Stack>
    ),
  },
];

export function TutorialModal({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) {
  const [step, setStep] = useState(0);
  const [doNotShow, setDoNotShow] = useState(false);

  const isLast = step === STEPS.length - 1;

  const handleClose = () => {
    if (doNotShow) setDismissedCookie();
    setStep(0);
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={<Title order={4}>{STEPS[step].title}</Title>}
      size="xl"
      overlayProps={{ backgroundOpacity: 0.45, blur: 3 }}
      centered
    >
      <Stack gap="xl">
        <Stepper active={step} size="sm" allowNextStepsSelect={false}>
          {STEPS.map((s, i) => (
            <Stepper.Step key={i} label={s.label} />
          ))}
        </Stepper>

        <Box mih={160}>{STEPS[step].body}</Box>

        <Group justify="space-between" align="center">
          <Checkbox
            label="Do not show this again"
            checked={doNotShow}
            onChange={(e) => setDoNotShow(e.currentTarget.checked)}
            size="sm"
          />
          <Group gap="sm">
            {step > 0 && (
              <Button variant="default" onClick={() => setStep((s) => s - 1)}>
                Back
              </Button>
            )}
            {isLast ? (
              <Button onClick={handleClose}>Start Exploring</Button>
            ) : (
              <Button onClick={() => setStep((s) => s + 1)}>Next</Button>
            )}
          </Group>
        </Group>
      </Stack>
    </Modal>
  );
}
