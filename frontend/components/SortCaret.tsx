"use client";

/** Triangular sort-direction indicator for table column headers. */
export function SortCaret({ dir }: { dir: "asc" | "desc" | null }) {
  const base = {
    display: "inline-block",
    width: 0,
    height: 0,
    borderLeft: "4px solid transparent",
    borderRight: "4px solid transparent",
    marginLeft: 4,
  } as const;
  if (dir === "asc") return <span style={{ ...base, borderBottom: "5px solid currentColor" }} />;
  if (dir === "desc") return <span style={{ ...base, borderTop: "5px solid currentColor" }} />;
  return <span style={{ ...base, borderTop: "5px solid currentColor", opacity: 0.25 }} />;
}

/** Inline-flex style for an unstyled sort button inside a Table.Th. */
export const SORT_BTN_STYLE = {
  display: "inline-flex",
  alignItems: "center",
  fontSize: "inherit",
  fontWeight: "inherit",
} as const;

/** Cycles a column through asc → desc → unsorted. */
export function nextSortState<K extends string>(
  prev: { key: K; dir: "asc" | "desc" } | null,
  key: K,
): { key: K; dir: "asc" | "desc" } | null {
  if (!prev || prev.key !== key) return { key, dir: "asc" };
  if (prev.dir === "asc") return { key, dir: "desc" };
  return null;
}
