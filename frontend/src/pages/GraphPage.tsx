import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as d3 from "d3";
import { api } from "../api/client";
import type { Memory } from "../types";

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  memory: Memory;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  sharedTags: number;
}

function buildGraphData(memories: Memory[]): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  const nodes: GraphNode[] = memories.map((m) => ({ id: m.id, memory: m }));
  const links: GraphLink[] = [];

  for (let i = 0; i < memories.length; i++) {
    for (let j = i + 1; j < memories.length; j++) {
      const shared = memories[i].tags.filter((t) =>
        memories[j].tags.includes(t),
      );
      if (shared.length > 0) {
        links.push({
          source: memories[i].id,
          target: memories[j].id,
          sharedTags: shared.length,
        });
      }
    }
  }

  return { nodes, links };
}

const SOURCE_COLORS: Record<string, string> = {
  mcp: "#3b82f6",
  api: "#10b981",
  dashboard: "#8b5cf6",
  manual: "#f59e0b",
  import: "#ef4444",
};

export default function GraphPage() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);

  const { data: memories, isLoading } = useQuery({
    queryKey: ["memories"],
    queryFn: api.listMemories,
  });

  useEffect(() => {
    if (!memories || memories.length === 0 || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const { nodes, links } = buildGraphData(memories);

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance(100),
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const g = svg.append("g");

    // Zoom
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on("zoom", (event) => g.attr("transform", event.transform)),
    );

    // Links
    const link = g
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "#d1d5db")
      .attr("stroke-width", (d) => Math.min(d.sharedTags * 1.5, 5));

    // Nodes
    const node = g
      .selectAll<SVGCircleElement, GraphNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => 6 + d.memory.importance * 10)
      .attr("fill", (d) => SOURCE_COLORS[d.memory.source] || "#6b7280")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .style("cursor", "pointer")
      .on("click", (_, d) => setSelectedMemory(d.memory))
      .call(
        d3
          .drag<SVGCircleElement, GraphNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      );

    // Tooltips
    node.append("title").text((d) => d.memory.content.slice(0, 100));

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as GraphNode).x!)
        .attr("y1", (d) => (d.source as GraphNode).y!)
        .attr("x2", (d) => (d.target as GraphNode).x!)
        .attr("y2", (d) => (d.target as GraphNode).y!);
      node.attr("cx", (d) => d.x!).attr("cy", (d) => d.y!);
    });

    return () => {
      simulation.stop();
    };
  }, [memories]);

  if (isLoading) return <p className="text-gray-500 text-sm">Loading...</p>;

  if (!memories || memories.length === 0) {
    return (
      <p className="text-gray-400 text-sm text-center py-8">
        No memories to visualize.
      </p>
    );
  }

  return (
    <div className="h-full flex gap-4">
      <div className="flex-1 bg-white rounded-lg border border-gray-200 overflow-hidden">
        <svg
          ref={svgRef}
          className="w-full h-full"
          style={{ minHeight: "500px" }}
        />
      </div>

      {selectedMemory && (
        <div className="w-80 bg-white rounded-lg border border-gray-200 p-4 space-y-3 overflow-auto">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-gray-900">Memory Detail</h3>
            <button
              onClick={() => setSelectedMemory(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              x
            </button>
          </div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap">
            {selectedMemory.content}
          </p>
          <div className="text-xs text-gray-500 space-y-1">
            <p>Source: {selectedMemory.source}</p>
            <p>Tags: {selectedMemory.tags.join(", ") || "none"}</p>
            <p>Importance: {selectedMemory.importance.toFixed(1)}</p>
            <p>
              Created:{" "}
              {new Date(selectedMemory.created_at).toLocaleString()}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
