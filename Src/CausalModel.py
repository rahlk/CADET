import sys
import pandas as pd
import pydot
import traceback
import numpy as np
from Src.Configurations import Config as cfg
from collections import defaultdict
from causalnex.structure.notears import from_pandas
from causalnex.network import BayesianNetwork
from ananke.graphs import ADMG
from ananke.estimation import CausalEffect
from ananke.estimation import AutomatedIF
from causalnex.structure.notears import from_pandas
from causalnex.network import BayesianNetwork

class CausalModel:
    def __init__(self):
        print("initializing CausalModel class")      

    def get_tabu_edges(self, columns, options, 
                       objectives):
       """This function is used to exclude edges which are not possible"""
       tabu_edges=[]
       # constraint on configuration options
       for opt in options:
           for cur_elem in columns:
               if cur_elem != opt:
                   tabu_edges.append((cur_elem, opt))
        
       # constraints on performance objetcives  
       for obj in objectives:
           for cur_elem in columns:
               if cur_elem != obj:
                   tabu_edges.append((obj, cur_elem))

       return tabu_edges 

    def visualize(self, nodes, edges, fname):
        """This function is used to visualize the causal model using graphviz"""
        from causalgraphicalmodels import CausalGraphicalModel
        import graphviz
        try:
            graph = CausalGraphicalModel(nodes=nodes, edges=edges)
            graph.draw().render(filename=fname)
        except AssertionError:
            print ("[ERROR]: cycles in NOTEARS dag")
            print("Edges: {0}".format(edges))
    
    def learn_notears(self, df, tabu_edges, 
                      thres):
        """This function is used to learn model using NOTEARS"""
        sm = from_pandas(df, tabu_edges = tabu_edges, w_threshold=thres)
        return sm, sm.edges    

    def learn_fci(self, df, tabu_edges):
        """This function is used to learn model using FCI"""
        from pycausal.pycausal import pycausal as pc
        from pycausal import search as s
        from pycausal import prior as p
        pc=pc()
        pc.start_vm()
        forbid = [list(i) for i in tabu_edges]
        prior = p.knowledge(forbiddirect = forbid)
        tetrad=s.tetradrunner()
        tetrad.getAlgorithmParameters(algoId = 'fci', testId = 'fisher-z-test')
        tetrad.run(algoId = 'fci', dfs = df, testId = 'fisher-z-test', 
                   depth = -1, maxPathLength = -1, completeRuleSetUsed = False, 
                   verbose = False)
        edges = tetrad.getEdges()
        dot_str = pc.tetradGraphToDot(tetrad.getTetradGraph())
        graph = pydot.graph_from_dot_data(dot_str)
        # graph[0].write_pdf(fname) 
        pc.stop_vm()
        return edges

    def resolve_edges(self, DAG, PAG, 
                      columns, tabu_edges):
        """This function is used to resolve no-tears (DAG) and fci (PAG) edges"""
        bi_edge = "<->"
        directed_edge = "-->"
        undirected_edge = "o-o"
        trail_edge = "o->"
        # notearse only contains directed edges.
        options = {}
        for opt in columns:
            options[opt]= {}
            options[opt][directed_edge]= []
            options[opt][bi_edge]= []
        # add DAG edges to current graph
        for edge in DAG:
            if edge[0] or edge[1] is None:
                options[edge[0]][directed_edge].append(edge[1])
        # replace trail and undirected edges with single edges using policy
        for i in range (len(PAG)):
            if trail_edge in PAG[i]:
                PAG[i]=PAG[i].replace(trail_edge, directed_edge)
            elif undirected_edge in PAG[i]:
                    PAG[i]=PAG[i].replace(undirected_edge, directed_edge)
            else:
                continue
        # update causal graph edges
        for edge in PAG:
            cur = edge.split(" ")
            if cur[1]==directed_edge:
                options[cur[0]][directed_edge].append(cur[2])
            elif cur[1]==bi_edge:
                options[cur[0]][bi_edge].append(cur[2])
            else: print ("[ERROR]: unexpected edges")
        # extract mixed graph edges 
        single_edges=[]
        double_edges=[]
        for i in options:
            options[i][directed_edge]=list(set(options[i][directed_edge]))
            options[i][bi_edge]=list(set(options[i][bi_edge]))
        for i in options:
            for m in options[i][directed_edge]:
                single_edges.append((i,m))
            for m in options[i][bi_edge]:
                double_edges.append((i,m))
        single_edges=list(set(single_edges)-set(tabu_edges))
        double_edges=list(set(double_edges)-set(tabu_edges))
        return single_edges, double_edges
    
    def get_causal_paths(self, columns, di_edges,
                         bi_edges, objectives):
        """This function is used to discover causal paths from an objective node"""
        CG = Graph(columns)
        causal_paths={}
        for edge in di_edges:
            CG.add_edge(edge[1], edge[0])
        for edge in bi_edges:
            CG.add_edge(edge[1], edge[0])
        for obj in objectives:
            CG.get_all_paths(obj)
            causal_paths[obj] = CG.path
        
        return causal_paths 
    
    def compute_path_causal_effect(self, df, paths, 
                                   G, K):
        """This function is used to compute P_ACE for each path"""
        ace = {}
        for path in paths:
            ace[path] = 0
            for i in range(0, len(path)):
              if i > 0:
                obj= CausalEffect(graph=G, treatment=path[i],outcome=path[0])
                ace[path] += obj.compute_effect(df, "gformula") # computing the effect
                print ("causal effect of {0} on {1}".format(path[i], path[0]))
                print("ace = ", ace, "\n")
        # rank paths and select top K
        paths = {k: v for k, v in sorted(ace.items(), key=lambda item: item[1], reverse = True)}[:K]
        return paths 
    
    def compute_individual_treatment_effect(self, df, paths, 
                                            G, query, objectives, 
                                            bug_val, config):
        """This function is used to compute individual treatment effect"""
        from causality.estimation.nonparametric import CausalEffect
        ite = {}
        if query == "best":
            bestval = np.min(df[objectives])
        else:
            bestval = (1-query)*bug_val
        for path in paths:
            for i in range(0, len(path)):
               if i > 0:
                   if cfg.is_intervenable[path[i]]:
                       index = cfg.index[path[i]]
                       effect = CausalEffect(G, path[i], path[0])
                       max_effect = -20000
                       for val in cfg.path[i]:
                           x = df({path[i] : [val], path[0] : [bestval]})
                           if max_effect < effect.pdf(x):
                               max_effect = effect.pdf(x)
                               ite[path[i]] = [max_effect, val, index]
        # Find the best config options and values 
        options = [v for _, v in sorted(ace.items(), key=lambda item: item[0], reverse = True)][:5]                
        for opt in options:
            config[opt[2]] = opt[1]
        return config

class Graph:
    def __init__(self, vertices):
        # No. of vertices
        self.V = vertices
        # default dictionary to store graph
        self.graph = defaultdict(list)

    def add_edge(self, u, v):
        self.graph[u].append(v)

    def get_all_paths_util(self, u, visited, path):

        visited[u]= True
        path.append(u)
        # If current vertex is same as destination, then print
        if self.graph[u] == []:
            try:
                if self.path:
                    self.path.append(path[:])
            except AttributeError:
                    self.path=[path[:]]
        else:
            for i in self.graph[u]:
                if visited[i]== False:
                    self.get_all_paths_util(i, visited, path)

        # remove current vertex from path[] and mark it as unvisited
        path.pop()
        visited[u]= False

    def get_all_paths(self, s):
        # mark all the vertices as not visited
        visited = {}
        for i in self.V:
            visited[i] = False
        # create an array to store paths
        path = []
        # call the recursive helper function to print all paths
        self.get_all_paths_util(s, visited, path)
  