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
    background: "#e8f4fd",
    border: "2px solid #228be6",
    fontWeight: 600,
    minWidth: 160,
    textAlign: "center",
  },
  genus: {
    background: "#f8f9fa",
    border: "1.5px solid #74c0fc",
    fontWeight: 500,
    fontStyle: "italic",
    minWidth: 140,
    textAlign: "center",
  },
  species: {
    background: "#ffffff",
    border: "1px solid #adb5bd",
    fontStyle: "italic",
    minWidth: 180,
    textAlign: "left",
  },
};

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
    ? { background: "#d0ebff", border: "2px solid #228be6" }
    : {};
  return (
    <div
      style={{
        padding: "5px 12px",
        borderRadius: 6,
        whiteSpace: "pre-line",
        fontSize: 12,
        fontFamily: "monospace",
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

function GenusToSpeciesEdge({ sourceX, sourceY, targetX, targetY }: EdgeProps) {
  const elbowX = useContext(GenusElbowContext);
  const ex = Math.max(sourceX + 8, elbowX);
  const d = `M${sourceX},${sourceY} H${ex} V${targetY} H${targetX}`;
  return <path d={d} stroke="#adb5bd" strokeWidth={1} fill="none" className="react-flow__edge-path" />;
}

function SourceToGenusEdge({ sourceX, sourceY, targetX, targetY }: EdgeProps) {
  const ex = Math.max(sourceX + 8, SOURCE_GENUS_ELBOW_X);
  const d = `M${sourceX},${sourceY} H${ex} V${targetY} H${targetX}`;
  return <path d={d} stroke="#adb5bd" strokeWidth={1} fill="none" className="react-flow__edge-path" />;
}

const nodeTypes = { rel: RelNode };
const edgeTypes = { gnedge: GenusToSpeciesEdge, sgnedge: SourceToGenusEdge };

const NAME_COLUMN_WIDTH = 200;
const GENUS_COLUMN_WIDTH = 160;

export function RelationsView() {
  const { records } = useFilteredRecords();
  const [hoveredLabel, setHoveredLabel] = useState<HoverState>(null);
  const [alignByName, setAlignByName] = useState(false);
  const [alignByGenus, setAlignByGenus] = useState(false);

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
      style: { stroke: "#adb5bd" },
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
      <Group>
        <Switch
          label="Align genus"
          size="sm"
          checked={alignByGenus}
          onChange={(e) => setAlignByGenus(e.currentTarget.checked)}
        />
        <Switch
          label="Align species"
          size="sm"
          checked={alignByName}
          onChange={(e) => setAlignByName(e.currentTarget.checked)}
        />
      </Group>
    <div style={{ width: "100%", height: 680, border: "1px solid #e9ecef", borderRadius: 8 }}>
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
        <Background color="#fafafa" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
    </Stack>
    </HoverContext.Provider>
    </GenusElbowContext.Provider>
  );
}
