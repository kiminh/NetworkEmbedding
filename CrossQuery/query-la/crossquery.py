"""
Given the node embedding and a query, 
calculate the nearest neighbors of the query!
20180723
Author: Liu Yang
"""
import numpy as np 
import time
import config
from copy import deepcopy
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity



class CrossQuery(object):
    def __init__(self):
        self.node_dict, self.node_id, self.node_type = self.read_nodes()
        self.node_num = len(self.node_dict)
        self.embed_dim = config.embed_dim
        self.node_emd = self.read_embedding(self.node_num, self.embed_dim)

    
    def read_nodes(self):
        """
        Read node_dict file.
        Input format:
            node_id node_type intype_id value
            seperated by '\x01'
        Output format:
            node_id2nt is a dictionary
            key is the node id
            value is a list [node_type, intype_id, value]
            node_nt2id is a dictionary
            key is the value
            value is [node_id, node_type]
            node_type is a dictionary
            key is the node type
            value is a node id list of a certain type 
        """
        with open(config.node_dict_path, "r") as f:
            node_lines = f.readlines()
        node_id2nt = {}
        node_nt2id = {}
        node_type = {}
        for t in ['t', 'w', 'l']:
            node_type[t] = []
        for line in node_lines:
            line_lst = line.split('\x01')
            node_id = int(line_lst[0])
            node_id2nt[node_id] = [line_lst[1], line_lst[2], line_lst[3]]
            node_nt2id[line_lst[3]] = [node_id, node_type]
            node_type[line_lst[1]].append(node_id)
        return node_id2nt, node_nt2id, node_type


    def read_embedding(self, n_node, n_embed):
        with open(config.embed_init, "r") as f:
            lines = f.readlines()
        node_embed = np.random.rand(n_node, n_embed)
        for line in lines:
            emd = line.split()
            node_embed[int(float(emd[0])), :] = [float(i) for i in emd[1:]]
        return node_embed


    def get_neighbors(self, query, neighbor_type, neighbor_num):
        q_id = self.node_id[query][0]
        q_emd = self.node_emd[q_id, :]
        candidate = self.node_type[neighbor_type]
        candi_similarity = []
        for c_id in candidate:
            c_emd = self.node_emd[c_id, :]
            candi_similarity.append(cosine_similarity([q_emd],[c_emd])[0][0])
        candi_index = np.argsort(candi_similarity)
        neighbors = []
        for k in range(neighbor_num):
            neighbors.append(self.node_dict[candidate[candi_index[-1-k]]][2])
        return neighbors[:neighbor_num]


if __name__ == "__main__":
    model = CrossQuery()
    print("10 Nearest Neighbors of the Query!")
    start_time = time.time()   
    query = ['beach', 'shopping']
    for q in query:
        result = model.get_neighbors(q, 'w', 10)
        print(result)
    print("Neighbors found, elapsed time {}s".format(time.time()-start_time))   