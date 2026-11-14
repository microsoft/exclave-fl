# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import json


# vertex data structure
class Vertex(object):
    def __init__(self, input_list, output_list, code):
        # list of hash values (accepted inputs only)
        self.input = input_list
        # list of hash values
        self.output = output_list
        # code measurement (if provided)
        self.code = code
    
    def print_vertex(self):
        print("Output:" + str(self.output))
        print("Input:" + str(self.input))
        print("Code:" + str(self.code))

class DirectGraph(object):
    def __init__(self):
        self.graph = dict()
    
    def add_vertex(self, vertex):
        if vertex not in self.graph.keys():
            # adj list
            self.graph[vertex] = dict()
    
    def add_edge(self, source, dest, weight):
        # don't connect to yourself
        if source == dest:
            return
        if source not in self.graph.keys():
            self.add_vertex(source)
        if dest not in self.graph.keys():
            self.add_vertex(dest)
        if dest not in self.graph[source]:
            # weighted directed graph
            self.graph[source][dest] = weight

    # get edge (neighbor, weight)
    def get_edge(self, vertex):
        if vertex not in self.graph.keys():
            return None
        else:
            return self.graph[vertex]

    def get_vertex(self):
        return self.graph.keys()

    def DFS(self, vertex, visited, leafs):
        """Iterative DFS using explicit stack to avoid recursion limit."""
        stack = [vertex]
        
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            
            # collect the edge weights
            edges = self.get_edge(current)
            if edges is None:
                continue
            weights = list(edges.values())
            
            for vertex_input in current.input:
                if vertex_input not in weights:
                    leafs.add(vertex_input)
            
            for neighbor in edges.keys():
                if neighbor not in visited:
                    stack.append(neighbor)

# methods to do the auditing
class Auditor(object):
    def __init__(self):
        pass
    
    # extract all values from a nested dict or list
    def _flatten_values(self, obj):
        """Flatten nested dicts/lists into a list of leaf values."""
        # dict (e.g. {"model": "abc", "data": "def"}) → recurse on values
        if isinstance(obj, dict):
            result = []
            for v in obj.values():
                result.extend(self._flatten_values(v))
            return result
        # list (e.g. [{"model": "a"}, {"model": "b"}]) → recurse on items
        elif isinstance(obj, list):
            result = []
            for item in obj:
                result.extend(self._flatten_values(item))
            return result
        # leaf value (hash string) → return as single-element list
        else:
            return [obj]

    def construct_vertex(self, log_data):
        """Parse log entries into Vertex objects. Keys: input, output, code."""
        vertexs = []
        for log_item in log_data:
            input_val = log_item.get("input")
            output_val = log_item.get("output")
            code_measurement = log_item.get("code")
            
            # get all values from the input and output
            input_list = self._flatten_values(input_val) if input_val else []
            output_list = self._flatten_values(output_val) if output_val else []

            vertexs.append(Vertex(input_list, output_list, code_measurement))
        return vertexs
    
    def construct_graph(self, vertexs):
        # construct graph
        auditGraph = DirectGraph()
        for item in vertexs:
            auditGraph.add_vertex(item)
        
        # Build index: input_value -> list of vertices with that input (O(V*I))
        input_index = {}
        for vertex in vertexs:
            for input_value in vertex.input:
                if input_value not in input_index:
                    input_index[input_value] = []
                input_index[input_value].append(vertex)
        
        # Match outputs to inputs via hash lookup (O(V*O) instead of O(V²*I*O))
        for output_vertex in vertexs:
            for output_value in output_vertex.output:
                if output_value in input_index:
                    for input_vertex in input_index[output_value]:
                        auditGraph.add_edge(input_vertex, output_vertex, output_value)
        
        return auditGraph
    
    # get the leaf inputs that the target vertex depends on
    def get_all_input_from_final_vertex(self, vertex, graph):
        visited = set()
        leafs = set()
        graph.DFS(vertex, visited, leafs)
        return leafs

    # get the vertex with this output value and code measurement
    def get_vertex_from_output_and_code(self, target_output, target_code, graph):
        vertexs = graph.get_vertex()
        for vertex in vertexs:
            # check the code measurement
            if vertex.code == target_code:
                for vertex_output in vertex.output:
                    if target_output == vertex_output:
                        return vertex
        return None


def load_structured_logs(input_dir):
    """
    Load logs from structured folder format.
    Returns a flat list of all log entries and the final model hash.
    Raises FileNotFoundError if the directory or required files are missing.
    """
    import glob
    
    all_logs = []
    
    # Find all .log files
    log_files = glob.glob(os.path.join(input_dir, '**', '*.log'), recursive=True)
    if not log_files:
        raise FileNotFoundError(f"No .log files found in {input_dir}")
    
    for log_file in sorted(log_files):
        with open(log_file, 'r') as f:
            logs = json.load(f)
            all_logs.extend(logs)
    
    # Extract final model hash from the last mu log (already loaded in all_logs)
    mu_log_path = os.path.join(input_dir, 'server', 'mu', 'server-mu.log')
    with open(mu_log_path, 'r') as f:
        mu_logs = json.load(f)
    # final model - last round model update exclave output
    final_model_hash = mu_logs[-1]['output']['full_model']
    
    return all_logs, final_model_hash

