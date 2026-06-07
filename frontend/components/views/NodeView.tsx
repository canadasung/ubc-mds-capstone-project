"use client";

/**
 * Node View — ports view_node.py.
 *
 * Replaces the pyvis HTML iframe with a native React Flow graph:
 *   [Query] → [Source] → [name / synonym nodes …]
 * Clicking a node that carries a URL opens it in a new tab.
 */

import { useCallback, useMemo } from "react";
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
import { useSearchStore } from "@/lib/store";
import { buildNodeGraph, type GraphNode } from "@/lib/transforms";

type NodeData = {
  label: string;
  full?: string;
  url: string | null;
  kind: GraphNode["kind"];
};

const KIND_STYLE: Record<GraphNode["kind"], React.CSSProperties> = {
  query: { background: "#ffffff", border: "2px solid #333", fontWeight: 700 },
  source: { background: "#eeeeee", border: "2px solid #333", fontWeight: 600 },
  name: { background: "#ffffff", border: "2px solid #555", fontStyle: "italic" },
};

function GraphNodeBox({ data }: NodeProps) {
  const d = data as NodeData;
  return (
    <div
      style={{
        padding: "8px 12px",
        borderRadius: 6,
        minWidth: 140,
        textAlign: "center",
        whiteSpace: "pre-line",
        fontSize: 12,
        fontFamily: "monospace",
        cursor: d.url ? "pointer" : "default",
        boxShadow: "2px 2px 6px rgba(0,0,0,0.15)",
        ...KIND_STYLE[d.kind],
      }}
      title={
        d.kind === "source"
          ? (d.full ?? d.label)
          : (d.url ?? "(no direct link available)")
      }
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      {d.label}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { box: GraphNodeBox };

export function NodeView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);

  const { nodes, edges } = useMemo(() => {
    const g = buildNodeGraph(records, query);
    const rfNodes: Node[] = g.nodes.map((n) => ({
      id: n.id,
      type: "box",
      position: { x: n.x, y: n.y },
      data: { label: n.label, full: n.full, url: n.url, kind: n.kind } satisfies NodeData,
      draggable: false,
    }));
    const rfEdges: Edge[] = g.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "smoothstep",
      style: { stroke: "#aaa" },
    }));
    return { nodes: rfNodes, edges: rfEdges };
  }, [records, query]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const url = (node.data as NodeData).url;
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  }, []);

  if (records.length === 0) {
    return <Text c="dimmed">No results to graph.</Text>;
  }

  return (
    <div style={{ width: "100%", height: 680, border: "1px solid #e9ecef", borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#fafafa" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
