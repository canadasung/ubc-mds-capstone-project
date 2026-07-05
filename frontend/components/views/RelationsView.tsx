"use client";

/**
 * Relations View — folder-style tree layout, one tree per source.
 *
 * Layout:  [Source A]  ──  [synonym 1]
 *                     ──  [synonym 2]
 *                     ──  [synonym 3]
 *
 *          [Source B]  ──  [synonym 1]
 *                     ──  [synonym 2]
 *
 * No root/query node. Clicking a synonym node opens its source URL.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import {
  Background,
  ControlButton,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { Group, Stack, Switch, Text } from "@mantine/core";
import { useFullscreen } from "@mantine/hooks";

import { useFilteredRecords } from "@/lib/hooks";
import { buildRelationsGraph, type GraphNode } from "@/lib/transforms";

type RelNodeData = {
  label: string;
  full?: string;
  url: string | null;
  kind: GraphNode["kind"];
  nodeWidth?: number;
};

type HoverState = { label: string; kind: "species" | "genus" } | null;
const HoverContext = createContext<HoverState>(null);

const KIND_STYLE: Record<"source" | "genus" | "species", React.CSSProperties> = {
  source: {
    background: "var(--mantine-color-body)",
    border: "1px solid var(--mantine-color-default-border)",
    fontWeight: 600,
    minWidth: 160,
    textAlign: "center",
  },
  genus: {
    background: "var(--mantine-color-body)",
    border: "1px solid var(--mantine-color-default-border)",
    fontWeight: 500,
    fontStyle: "italic",
    minWidth: 140,
    textAlign: "center",
  },
  species: {
    background: "var(--mantine-color-default-hover)",
    border: "1.5px solid var(--mantine-color-blue-6)",
    fontStyle: "italic",
    minWidth: 180,
    textAlign: "left",
  },
};

/**
 * Render a single graph node box (a source, genus, or species name).
 *
 * The box style is chosen by the node's kind. A species or genus node is
 * highlighted when its label matches the currently hovered node, and a node that
 * carries a URL shows a pointer cursor. Hidden left and right handles let React
 * Flow attach the connecting edges.
 *
 * Parameters
 * ----------
 * data : RelNodeData
 *     The node payload: label, kind, optional full name, url, and width override.
 */
function RelNode({ data }: NodeProps) {
  const d = data as RelNodeData;
  const hovered = useContext(HoverContext);
  const highlighted =
    hovered !== null &&
    (d.kind === "species" || d.kind === "genus") &&
    d.kind === hovered.kind &&
    d.label === hovered.label;
  const style = KIND_STYLE[d.kind as "source" | "genus" | "species"] ?? KIND_STYLE.species;
  const widthOverride = d.nodeWidth !== undefined ? { minWidth: d.nodeWidth, width: d.nodeWidth } : {};
  const highlightOverride = highlighted
    ? { background: "var(--mantine-color-blue-light)", border: "2px solid var(--mantine-color-blue-6)" }
    : {};
  return (
    <div
      style={{
        padding: "5px 12px",
        borderRadius: 6,
        whiteSpace: "pre-line",
        fontSize: 12,
        fontFamily: "monospace",
        color: "var(--mantine-color-text)",
        cursor: d.url ? "pointer" : "default",
        boxShadow: "1px 2px 4px rgba(0,0,0,0.1)",
        ...style,
        ...widthOverride,
        ...highlightOverride,
      }}
      title={d.kind === "genus" ? undefined : (d.full ?? d.label)}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      {d.label}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

// X coordinate where all genus→species edges make their vertical turn.
// Genus nodes sit at x=280 with minWidth=140, so their right handle is ~420.
// 490 puts the elbow between that right edge and the base species column at 560.
const GENUS_ELBOW_X = 490;
const GenusElbowContext = createContext<number>(GENUS_ELBOW_X);

// X coordinate where all source→genus edges make their vertical turn (when genus is aligned).
// Source nodes sit at x=0 with minWidth=160, so their right handle is ~160.
// 220 puts the elbow between that right edge and the base genus column at 280.
const SOURCE_GENUS_ELBOW_X = 220;

/**
 * Render a right-angle "elbow" edge between two nodes.
 *
 * The path runs horizontally from the source to a shared turn column, then
 * vertically to the target's row, then horizontally into the target. Routing
 * every sibling edge through the same turn column (``elbowX``) keeps the
 * connectors aligned into a tidy bracket. The turn is clamped to just past the
 * source so it never bends backwards.
 *
 * Parameters
 * ----------
 * sourceX, sourceY, targetX, targetY : number
 *     Endpoint coordinates supplied by React Flow.
 * elbowX : number
 *     X coordinate of the vertical turn.
 */
function ElbowEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  elbowX,
}: {
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  elbowX: number;
}) {
  const ex = Math.max(sourceX + 8, elbowX);
  const d = `M${sourceX},${sourceY} H${ex} V${targetY} H${targetX}`;
  return (
    <path
      d={d}
      stroke="var(--mantine-color-default-border)"
      strokeWidth={1}
      fill="none"
      className="react-flow__edge-path"
    />
  );
}

/**
 * Genus-to-species edge: an elbow whose turn column comes from context, so it
 * shifts right when the genus column is aligned and widened.
 */
function GenusToSpeciesEdge({ sourceX, sourceY, targetX, targetY }: EdgeProps) {
  const elbowX = useContext(GenusElbowContext);
  return <ElbowEdge sourceX={sourceX} sourceY={sourceY} targetX={targetX} targetY={targetY} elbowX={elbowX} />;
}

/**
 * Source-to-genus edge: an elbow turning at the fixed source/genus column, used
 * only when the genus column is aligned.
 */
function SourceToGenusEdge({ sourceX, sourceY, targetX, targetY }: EdgeProps) {
  return (
    <ElbowEdge
      sourceX={sourceX}
      sourceY={sourceY}
      targetX={targetX}
      targetY={targetY}
      elbowX={SOURCE_GENUS_ELBOW_X}
    />
  );
}

const nodeTypes = { rel: RelNode };
const edgeTypes = { gnedge: GenusToSpeciesEdge, sgnedge: SourceToGenusEdge };

const NAME_COLUMN_WIDTH = 200;
const GENUS_COLUMN_WIDTH = 160;

/**
 * Relations view: a React Flow graph of each source's synonyms, grouped by genus.
 *
 * Nodes are laid out by the transform layer; two switches optionally align all
 * genus nodes (and all species nodes) into shared columns for easier comparison,
 * which also shifts the species column and edge elbows to keep the brackets
 * tidy. Hovering a genus or species highlights every matching node; clicking a
 * node opens its source page. The graph canvas has zoom, fit-view, and a
 * fullscreen toggle.
 */
export function RelationsView() {
  const { records } = useFilteredRecords();
  const [hoveredLabel, setHoveredLabel] = useState<HoverState>(null);
  const [alignByName, setAlignByName] = useState(false);
  const [alignByGenus, setAlignByGenus] = useState(false);

  // Fullscreen toggle for the graph canvas (browser Fullscreen API on the
  // wrapper). React Flow auto-resizes to fill the container as it grows.
  const {
    ref: fullscreenRef,
    toggle: toggleFullscreen,
    fullscreen,
  } = useFullscreen<HTMLDivElement>();

  const baseGraph = useMemo(() => buildRelationsGraph(records), [records]);

  const { nodes, edges, genusElbowX } = useMemo(() => {
    function buildLabelToX(kind: "species" | "genus", colWidth: number, fallbackX: number) {
      const kindNodes = baseGraph.nodes.filter((n) => n.kind === kind);
      const freq = new Map<string, number>();
      for (const n of kindNodes) freq.set(n.label, (freq.get(n.label) ?? 0) + 1);
      const sortedLabels = [...freq.keys()].sort((a, b) => (freq.get(b) ?? 0) - (freq.get(a) ?? 0));
      const baseX = kindNodes[0]?.x ?? fallbackX;
      return new Map(sortedLabels.map((label, i) => [label, baseX + i * colWidth]));
    }

    const nameLabelToX = alignByName ? buildLabelToX("species", NAME_COLUMN_WIDTH, 560) : null;
    const genusLabelToX = alignByGenus ? buildLabelToX("genus", GENUS_COLUMN_WIDTH, 280) : null;
    const genusOffset = genusLabelToX ? (genusLabelToX.size - 1) * GENUS_COLUMN_WIDTH : 0;

    // ~7.2px per char in monospace 12px + 24px horizontal padding (12px each side)
    const CHAR_PX = 7.2;
    const H_PAD = 24;
    const maxLabelWidth = (kind: "genus" | "species") => {
      const labels = baseGraph.nodes.filter((n) => n.kind === kind).map((n) => n.label.length);
      return labels.length > 0 ? Math.max(...labels) * CHAR_PX + H_PAD : undefined;
    };
    const genusNodeWidth = maxLabelWidth("genus");
    const nameNodeWidth = maxLabelWidth("species");

    const rfNodes: Node[] = baseGraph.nodes.map((n) => ({
      id: n.id,
      type: "rel",
      position: {
        x:
          n.kind === "genus" && genusLabelToX
            ? (genusLabelToX.get(n.label) ?? n.x)
            : n.kind === "species"
            ? (nameLabelToX ? (nameLabelToX.get(n.label) ?? n.x) : n.x) + genusOffset
            : n.x,
        y: n.y,
      },
      data: {
        label: n.label,
        full: n.full,
        url: n.url,
        kind: n.kind,
        nodeWidth: n.kind === "genus" ? genusNodeWidth : n.kind === "species" ? nameNodeWidth : undefined,
      } satisfies RelNodeData,
      draggable: false,
    }));
    const speciesNodeIds = new Set(baseGraph.nodes.filter((n) => n.kind === "species").map((n) => n.id));
    const genusNodeIds = new Set(baseGraph.nodes.filter((n) => n.kind === "genus").map((n) => n.id));

    const rfEdges: Edge[] = baseGraph.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: speciesNodeIds.has(e.target)
        ? "gnedge"
        : alignByGenus && genusNodeIds.has(e.target)
        ? "sgnedge"
        : "smoothstep",
      style: { stroke: "var(--mantine-color-default-border)" },
    }));
    const genusElbowX = GENUS_ELBOW_X + genusOffset;

    return { nodes: rfNodes, edges: rfEdges, genusElbowX };
  }, [baseGraph, alignByName, alignByGenus]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const url = (node.data as RelNodeData).url;
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  }, []);

  const onNodeMouseEnter = useCallback((_: React.MouseEvent, node: Node) => {
    const d = node.data as RelNodeData;
    if (d.kind === "species" || d.kind === "genus")
      setHoveredLabel({ label: d.label, kind: d.kind });
  }, []);

  const onNodeMouseLeave = useCallback(() => setHoveredLabel(null), []);

  return (
    <GenusElbowContext.Provider value={genusElbowX}>
    <HoverContext.Provider value={hoveredLabel}>
    <Stack gap="xs">
      <Group justify="space-between" wrap="nowrap">
        <Text style={{ flex: 1 }}>
          Clicking a species name opens its page on the source website.
        </Text>
        <Group style={{ flex: 1 }} justify="flex-end">
          <Switch
            label="Align genus"
            size="md"
            checked={alignByGenus}
            onChange={(e) => setAlignByGenus(e.currentTarget.checked)}
          />
          <Switch
            label="Align species"
            size="md"
            checked={alignByName}
            onChange={(e) => setAlignByName(e.currentTarget.checked)}
          />
        </Group>
      </Group>
    <div
      ref={fullscreenRef}
      style={{
        width: "100%",
        height: fullscreen ? "100vh" : 680,
        border: "1px solid var(--mantine-color-default-border)",
        borderRadius: fullscreen ? 0 : 8,
        background: "var(--mantine-color-body)",
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="var(--mantine-color-default-border)" />
        <Controls showInteractive={false}>
          <ControlButton
            onClick={toggleFullscreen}
            title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
            aria-label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              {fullscreen ? (
                <>
                  <polyline points="4 14 10 14 10 20" />
                  <polyline points="20 10 14 10 14 4" />
                  <line x1="14" y1="10" x2="21" y2="3" />
                  <line x1="3" y1="21" x2="10" y2="14" />
                </>
              ) : (
                <>
                  <polyline points="15 3 21 3 21 9" />
                  <polyline points="9 21 3 21 3 15" />
                  <line x1="21" y1="3" x2="14" y2="10" />
                  <line x1="3" y1="21" x2="10" y2="14" />
                </>
              )}
            </svg>
          </ControlButton>
        </Controls>
      </ReactFlow>
    </div>
    </Stack>
    </HoverContext.Provider>
    </GenusElbowContext.Provider>
  );
}
