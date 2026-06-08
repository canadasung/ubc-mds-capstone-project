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
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { Text } from "@mantine/core";

import { useFilteredRecords } from "@/lib/hooks";
import { buildRelationsGraph, type GraphNode } from "@/lib/transforms";

type RelNodeData = {
  label: string;
  full?: string;
  url: string | null;
  kind: GraphNode["kind"];
};

const HoverContext = createContext<string | null>(null);

const KIND_STYLE: Record<"source" | "genus" | "name", React.CSSProperties> = {
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
  name: {
    background: "#ffffff",
    border: "1px solid #adb5bd",
    fontStyle: "italic",
    minWidth: 180,
    textAlign: "left",
  },
};

function RelNode({ data }: NodeProps) {
  const d = data as RelNodeData;
  const hoveredLabel = useContext(HoverContext);
  const highlighted = d.kind === "name" && hoveredLabel !== null && d.label === hoveredLabel;
  const style = KIND_STYLE[d.kind as "source" | "genus" | "name"] ?? KIND_STYLE.name;
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

const nodeTypes = { rel: RelNode };

export function RelationsView() {
  const { records } = useFilteredRecords();
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);

  const baseGraph = useMemo(() => buildRelationsGraph(records), [records]);

  const { nodes, edges } = useMemo(() => {
    const rfNodes: Node[] = baseGraph.nodes.map((n) => ({
      id: n.id,
      type: "rel",
      position: { x: n.x, y: n.y },
      data: {
        label: n.label,
        full: n.full,
        url: n.url,
        kind: n.kind,
      } satisfies RelNodeData,
      draggable: false,
    }));
    const rfEdges: Edge[] = baseGraph.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "smoothstep",
      style: { stroke: "#adb5bd" },
    }));
    return { nodes: rfNodes, edges: rfEdges };
  }, [baseGraph]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const url = (node.data as RelNodeData).url;
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  }, []);

  const onNodeMouseEnter = useCallback((_: React.MouseEvent, node: Node) => {
    const d = node.data as RelNodeData;
    if (d.kind === "name") setHoveredLabel(d.label);
  }, []);

  const onNodeMouseLeave = useCallback(() => setHoveredLabel(null), []);

  if (records.length === 0) {
    return <Text c="dimmed">No results to display.</Text>;
  }

  return (
    <HoverContext.Provider value={hoveredLabel}>
    <div style={{ width: "100%", height: 680, border: "1px solid #e9ecef", borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
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
    </HoverContext.Provider>
  );
}
