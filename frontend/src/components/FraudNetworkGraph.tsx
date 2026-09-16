import { useEffect, useRef } from "react";
import ForceGraph2D, { type ForceGraphMethods, type NodeObject } from "react-force-graph-2d";
import type { NetworkEdge, NetworkNode } from "../types";

export const NODE_COLORS: Record<string, string> = {
  customer: "#0f172a",
  device: "#2563eb",
  ip: "#059669",
  transaction: "#7c3aed",
  location: "#ea580c",
};

export const RISK_COLORS: Record<string, string> = {
  LOW: "#16a34a",
  MEDIUM: "#d97706",
  HIGH: "#dc2626",
  CRITICAL: "#991b1b",
};

const LEGEND_ITEMS: { type: string; label: string }[] = [
  { type: "customer", label: "Customer" },
  { type: "device", label: "Device" },
  { type: "ip", label: "IP" },
  { type: "transaction", label: "Transaction" },
  { type: "location", label: "Location" },
];

export function FraudNetworkLegend() {
  return (
    <p className="text-xs text-slate-500 mb-3 dark:text-slate-400">
      {LEGEND_ITEMS.map((item, i) => (
        <span key={item.type} className={i > 0 ? "ml-3" : ""}>
          <span className="inline-block w-2 h-2 rounded-full mr-1" style={{ background: NODE_COLORS[item.type] }}></span>
          {item.label}
        </span>
      ))}
      {" — drag to pan, scroll to zoom, click a node for details"}
    </p>
  );
}

export default function FraudNetworkGraph({
  nodes,
  edges,
  height = 320,
  onNodeClick,
}: {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  height?: number;
  onNodeClick?: (node: NetworkNode) => void;
}) {
  const fgRef = useRef<ForceGraphMethods>();

  useEffect(() => {
    // Give the simulation a moment then fit the graph nicely in view.
    const timer = setTimeout(() => fgRef.current?.zoomToFit(400, 40), 300);
    return () => clearTimeout(timer);
  }, [nodes, edges]);

  return (
    <div className="border border-slate-100 rounded-lg overflow-hidden dark:border-white/10" style={{ height }}>
      <ForceGraph2D
        ref={fgRef}
        backgroundColor="rgba(0,0,0,0)"
        graphData={{ nodes: nodes.map((n) => ({ ...n })), links: edges.map((e) => ({ ...e })) }}
        nodeId="id"
        nodeLabel={(n) => {
          const node = n as unknown as NetworkNode;
          const extra = node.type === "transaction" && node.amount != null ? ` — $${node.amount.toLocaleString()}` : "";
          return `${node.type}: ${node.label}${extra}`;
        }}
        nodeColor={(n) => {
          const node = n as unknown as NetworkNode;
          if ((node.type === "customer" || node.type === "transaction") && node.risk_level) {
            return RISK_COLORS[node.risk_level] || NODE_COLORS[node.type];
          }
          return NODE_COLORS[node.type] || "#64748b";
        }}
        nodeRelSize={5}
        linkColor={() => "#cbd5e1"}
        linkWidth={1.5}
        width={undefined}
        height={height}
        cooldownTicks={80}
        onNodeClick={(n) => {
          const node = n as unknown as NodeObject & NetworkNode;
          if (onNodeClick) {
            onNodeClick(node);
          } else {
            alert(`${node.type.toUpperCase()}: ${node.label}${node.risk_level ? ` (risk: ${node.risk_level})` : ""}`);
          }
        }}
        nodeCanvasObjectMode={() => "after"}
        nodeCanvasObject={(n, ctx, globalScale) => {
          const node = n as unknown as NetworkNode & { x?: number; y?: number };
          const label = node.label;
          const fontSize = 10 / globalScale;
          ctx.font = `${fontSize}px sans-serif`;
          ctx.fillStyle = document.documentElement.classList.contains("dark") ? "#cbd5e1" : "#334155";
          ctx.textAlign = "center";
          ctx.fillText(label, node.x ?? 0, (node.y ?? 0) + 8);
        }}
      />
    </div>
  );
}
