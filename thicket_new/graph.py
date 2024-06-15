import rustworkx as rx

from .frame import Frame
from .node import Node

from collections import defaultdict
from typing import Union


def index_by(attr, objects):
    """Put objects into lists based on the value of an attribute.

    Returns:
        (dict): dictionary of lists of objects, keyed by attribute value
    """
    index = defaultdict(lambda: [])
    for obj in objects:
        index[getattr(obj, attr)].append(obj)
    return index


class GraphDFSVistor(rx.DFSVisitor):
    def __init__(self, order):
        self.node_ids = []
        self.order = order
        if self.order not in ("pre", "post"):
            raise ValueError("Unknown traversal order '{}' provided".format(self.order))
        self.visited = {}

    def discover_vertex(self, vertex, t):
        if self.order == "pre":
            self.node_ids.append(vertex)
        key = id(vertex)
        if key in self.visited:
            self.visited[key] += 1
        else:
            self.visited[key] = 1

    def finish_vertex(self, vertex, t):
        if self.order == "post":
            self.node_ids.append(vertex)


class Graph:
    def __init__(self):
        self.dag = rx.PyDiGraph(check_cycle=True, multigraph=False)
        self.roots = set()

    def add_node(self, frame: Frame) -> Node:
        node_id = self.dag.add_node()
        node_obj = Node(frame, node_id)
        self.dag[node_id] = node_obj
        self.roots.add(node_id)
        return node_obj

    def add_parent(self, child: Union[int, Node], parent_frame: Frame) -> Node:
        if isinstance(child, int):
            child_id = child
        elif isinstance(child, Node):
            child_id = child._hatchet_nid
        else:
            raise TypeError(
                "'child' argument to 'add_parent' must be either an int or a Node"
            )
        parent_id = self.dag.add_parent(child_id)
        parent_node = Node(parent_frame, hnid=parent_id)
        self.dag[parent_id] = parent_node
        self.roots.add(parent_id)
        if child_id in self.roots:
            self.roots.remove(child_id)
        return parent_node

    def add_child(self, parent: Union[int, Node], child_frame: Frame) -> Node:
        if isinstance(parent, int):
            parent_id = parent
        elif isinstance(parent, Node):
            parent_id = parent._hatchet_nid
        else:
            raise TypeError(
                "'parent' argument to 'add_child' must be either an int or a Node"
            )
        child_id = self.dag.add_parent(parent_id)
        child_node = Node(child_frame, hnid=child_id)
        self.dag[child_id] = child_node
        return child_node

    def add_edge(self, parent: Union[int, Node], child: Union[int, Node]):
        if isinstance(parent, int):
            parent_id = parent
        elif isinstance(parent, Node):
            parent_id = parent._hatchet_nid
        else:
            raise TypeError(
                "'parent' argument to 'add_edge' must be either an int or a Node"
            )
        if isinstance(child, int):
            child_id = child
        elif isinstance(child, Node):
            child_id = child._hatchet_nid
        else:
            raise TypeError(
                "'child' argument to 'add_edge' must be either an int or a Node"
            )
        self.dag.add_edge(parent_id, child_id)
        if child_id in self.roots:
            self.roots.remove(child_id)

    def get_parents(self, child: Union[int, Node]) -> [Node]:
        if isinstance(child, int):
            child_id = child
        elif isinstance(child, Node):
            child_id = child._hatchet_nid
        else:
            raise TypeError(
                "'child' argument to 'get_parents' must be either an int or a Node"
            )
        parents = []
        for in_edge in self.dag.in_edges(child_id):
            parent_id = in_edge[0]
            parents.append(self.dag[parent_id])
        return parents

    def get_children(self, parent: Union[int, Node]) -> [Node]:
        if isinstance(parent, int):
            parent_id = parent
        elif isinstance(parent, Node):
            parent_id = parent._hatchet_nid
        else:
            raise TypeError(
                "'parent' argument to 'add_children' must be either an int or a Node"
            )
        children = []
        for out_edge in self.dag.out_edges(parent_id):
            child_id = out_edge[1]
            children.append(self.dag[child_id])
        return children

    def traverse(self, order="pre", attrs=None, visited=None):
        def get_attrs(node):
            return node if attrs is None else node.frame.values(attrs)

        dfs_visitor = GraphDFSVistor(order, attrs)
        roots = list(self.roots)
        roots.sort()
        rx.digraph_dfs_search(self.dag, roots, dfs_visitor)
        if visited is not None:
            visited = dfs_visitor.visited
        for node_id in dfs_visitor.node_ids:
            yield get_attrs(self.dag[node_id])

    def is_tree(self):
        if len(self.roots) > 1:
            return False
        visited = {}
        list(self.traverse(visited=visited))
        return all(v == 1 for v in visited.values())

    def find_merges(self):
        """Find nodes that have the same parent and frame.

        Find nodes that have the same parent and duplicate frame, and
        return a mapping from nodes that should be eliminated to nodes
        they should be merged into.

        Return:
            (dict): dictionary from nodes to their merge targets

        """
        merges = {}  # old_node -> merged_node
        inverted_merges = defaultdict(
            lambda: []
        )  # merged_node -> list of corresponding old_nodes
        processed = []

        def _find_child_merges(node_list):
            index = index_by("frame", node_list)
            for frame, children in index.items():
                if len(children) > 1:
                    min_id = min(children, key=id)
                    for child in children:
                        prev_min = merges.get(child, min_id)
                        # Get the new merged_node
                        curr_min = min([min_id, prev_min], key=id)
                        # Save the new merged_node to the merges dict
                        # so that the merge can happen later.
                        merges[child] = curr_min
                        # Update inverted_merges to be able to set node_list
                        # to the right value.
                        inverted_merges[curr_min].append(child)

        _find_child_merges(self.roots)
        for node in self.traverse():
            if node in processed:
                continue
            nodes = None
            # If node is going to be merged with other nodes,
            # collect the set of those nodes' children. This is
            # done to ensure that equivalent children of merged nodes
            # also get merged.
            if node in merges:
                new_node = merges[node]
                nodes = []
                for node_to_merge in inverted_merges[new_node]:
                    nodes.extend(self.get_children(node_to_merge))
                processed.extend(inverted_merges[new_node])
            # If node is not going to be merged, simply get the list of
            # node's children.
            else:
                nodes = self.get_children(node)
                processed.append(node)
            _find_child_merges(nodes)

        return merges

    def update_roots(self):
        self.roots = set(
            [n for n in self.dag.node_indices() if self.dag.in_degree(n) == 0]
        )

    def merge_nodes(self, merges):
        """Merge some nodes in a graph into others.

        ``merges`` is a dictionary keyed by old nodes, with values equal
        to the nodes that they need to be merged into.  Old nodes'
        parents and children are connected to the new node.

        Arguments:
            merges (dict): dictionary from source nodes -> targets

        """
        for old, new in merges.items():
            self.dag.merge_nodes(old._hatchet_nid, new._hatchet_nid)
        self.update_roots()

    def normalize(self):
        merges = self.find_merges()
        self.merge_nodes(merges)
        return merges

    def copy(self, old_to_new=None):
        if old_to_new is None:
            old_to_new = {}
        new_dag = self.dag.copy()
        for old_idx, new_idx in zip(self.dag.node_indices(), new_dag.node_indices()):
            old_node = self.dag[old_idx]
            new_node = new_dag[new_idx].copy()
            new_dag[new_idx] = new_node
            old_to_new[old_node] = new_node
        graph = Graph()
        graph.dag = new_dag
        graph.roots = set([old_to_new[r] for r in self.roots])
        graph.enumerate_traverse()
        return graph
    
    def union(self, other, old_to_new=None):
        
