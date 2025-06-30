import networkx as nx
import matplotlib.pyplot as plt


def visualize_wait_for_graph(graph, cycle=None):
    """
    Visualizes the Wait-For Graph using networkx and matplotlib.

    Args:
        graph (dict): The Wait-For Graph where keys are thread IDs and values are lists of dependencies.
        cycle (list): Optional list of nodes forming a cycle (deadlock).
    """
    G = nx.DiGraph()

    # Add nodes and edges to the graph
    for node, dependencies in graph.items():
        G.add_node(node)
        for dependency in dependencies:
            G.add_edge(node, dependency)

    # Use a circular layout for better spacing
    pos = nx.circular_layout(G)

    # Draw the graph
    plt.figure(figsize=(12, 8))
    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color="lightblue",
        node_size=2500,
        font_size=12,
        font_weight="bold",
        edge_color="gray",
    )

    # Highlight the cycle if provided
    if cycle:
        cycle_edges = [(cycle[i], cycle[i + 1]) for i in range(len(cycle) - 1)] + [
            (cycle[-1], cycle[0])
        ]
        nx.draw_networkx_edges(G, pos, edgelist=cycle_edges, edge_color="red", width=3)
        nx.draw_networkx_nodes(
            G, pos, nodelist=cycle, node_color="orange", node_size=3000
        )
        plt.title("Deadlock Detected: Cycle Highlighted", fontsize=16, color="red")
    else:
        plt.title("Wait-For Graph", fontsize=16)

    # Add a legend for clarity
    plt.legend(
        handles=[
            plt.Line2D([0], [0], color="gray", lw=2, label="Dependency"),
            plt.Line2D([0], [0], color="red", lw=2, label="Deadlock Cycle"),
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="orange",
                markersize=15,
                label="Deadlock Nodes",
            ),
        ],
        loc="upper left",
    )

    plt.show()
