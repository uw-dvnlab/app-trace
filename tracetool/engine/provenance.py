"""
Provenance Visualization Module

Handles loading provenance JSON and visualizing the data flow graph.
"""

import json
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, Any


def load_provenance_graph(provenance_path: Path) -> nx.DiGraph:
    """
    Build a NetworkX graph from a provenance JSON file.

    Traverses backwards from the export to inputs.
    """
    G = nx.DiGraph()

    with open(provenance_path, "r") as f:
        prov = json.load(f)

    # Main node: The Compute Instance
    compute_node = prov["compute_instance"]
    plugin_name = prov.get("plugin_name", "UnknownPlugin")
    G.add_node(
        compute_node,
        type="compute",
        label=f"{compute_node}\n({plugin_name})",
        color="lightblue",
    )

    # Export File Node
    export_node = provenance_path.name
    G.add_node(
        export_node, type="file", label=f"Export:\n{export_node}", color="lightgreen"
    )
    G.add_edge(compute_node, export_node, label="produces")

    # Load Run Config if available to trace bindings further?
    # For now, just show immediate bindings from the provenance JSON

    channel_bindings = prov.get("channel_bindings", {})
    event_bindings = prov.get("event_bindings", {})

    # Bounded Channels (Inputs)
    for role, channel_id in channel_bindings.items():
        # channel_id is like "group:name"
        G.add_node(
            channel_id,
            type="channel",
            label=f"Channel:\n{channel_id}",
            color="lightgray",
        )
        G.add_edge(channel_id, compute_node, label=f"bound to\n{role}")

        # Check if we can trace this channel's provenance (derived?)
        # This would require loading channels.json or run_config.json
        # For this prototype, we'll stop at the channel unless we have more info loaded

    # Bounded Events (Inputs)
    for role, source_name in event_bindings.items():
        G.add_node(
            source_name,
            type="event_source",
            label=f"Event Source:\n{source_name}",
            color="orange",
        )
        G.add_edge(source_name, compute_node, label=f"bound to\n{role}")

    return G


def show_provenance_graph(provenance_path: Path):
    """
    Display the provenance graph using matplotlib.
    """
    G = load_provenance_graph(provenance_path)

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, seed=42, k=2.0)  # k controls node spacing

    # Draw nodes by type
    node_colors = [G.nodes[n].get("color", "white") for n in G.nodes]
    labels = {n: G.nodes[n].get("label", n) for n in G.nodes}

    nx.draw(
        G,
        pos,
        with_labels=True,
        labels=labels,
        node_color=node_colors,
        node_size=3000,
        font_size=8,
        arrowsize=20,
        edge_color="gray",
    )

    # Draw edge labels
    edge_labels = nx.get_edge_attributes(G, "label")
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

    plt.title(f"Provenance Graph: {provenance_path.name}")
    plt.axis("off")
    plt.show()
