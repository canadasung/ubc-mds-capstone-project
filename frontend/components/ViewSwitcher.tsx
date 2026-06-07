"use client";

/** ViewSwitcher — ports st.segmented_control("View", ...). */

import { SegmentedControl } from "@mantine/core";
import { useSearchStore, type ViewKey } from "@/lib/store";

export function ViewSwitcher() {
  const activeView = useSearchStore((s) => s.activeView);
  const setActiveView = useSearchStore((s) => s.setActiveView);
  const debug = useSearchStore((s) => s.debug);

  const options: ViewKey[] = debug
    ? ["Table", "Timeline", "Node", "Taxonomic", "Debug"]
    : ["Table", "Timeline", "Node", "Taxonomic"];

  return (
    <SegmentedControl
      value={activeView}
      onChange={(v) => setActiveView(v as ViewKey)}
      data={options}
    />
  );
}
