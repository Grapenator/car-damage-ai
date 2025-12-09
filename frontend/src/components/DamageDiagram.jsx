import React, { useMemo } from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";

function DamageDiagram({ parts }) {
  const { nodes, edges } = useMemo(() => {
    if (!parts || parts.length === 0) {
      return { nodes: [], edges: [] };
    }

    const carNode = {
      id: "car",
      data: { label: "Car" },
      position: { x: 0, y: 0 },
      style: {
        padding: "10px 16px",
        borderRadius: 8,
        border: "1px solid #888",
        backgroundColor: "#f5f5f5",
        fontWeight: "bold",
      },
    };

    const partNodes = parts.map((part, index) => {
      const spacingX = 220;
      const x = (index - (parts.length - 1) / 2) * spacingX;
      const y = 200;

      const totalCost =
        part?.estimated_total_part_cost != null
          ? `$${part.estimated_total_part_cost}`
          : "";

      const labelLines = [
        part.part_name || "Unknown part",
        `Severity: ${part.severity ?? "?"}`,
        totalCost ? `Total: ${totalCost}` : "",
      ].filter(Boolean);

      return {
        id: part.part_id || `part-${index}`,
        data: { label: labelLines.join("\n") },
        position: { x, y },
        style: {
          padding: "8px 12px",
          borderRadius: 8,
          border: "1px solid #aaa",
          backgroundColor: "#ffffff",
          whiteSpace: "pre-line",
          textAlign: "center",
          fontSize: 12,
        },
      };
    });

    const edges = parts.map((part, index) => ({
      id: `edge-car-${part.part_id || index}`,
      source: "car",
      target: part.part_id || `part-${index}`,
      animated: true,
      style: { strokeWidth: 1.5 },
    }));

    return {
      nodes: [carNode, ...partNodes],
      edges,
    };
  }, [parts]);

  if (nodes.length === 0) {
    return null;
  }

  return (
    <ReactFlow nodes={nodes} edges={edges} fitView>
      <Background />
      <Controls />
    </ReactFlow>
  );
}

export default DamageDiagram;