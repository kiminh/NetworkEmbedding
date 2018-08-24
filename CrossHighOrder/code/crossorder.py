"""
Using high order information to train crossmap C++
20180819
Author: Liu Yang
"""
import numpy as np  
import time
import ast
from copy import deepcopy
from collections import defaultdict
import itertools
import pickle
import random
import math
import os, sys
import pdb
from paras import load_params
from sklearn.preprocessing import normalize
from crossdata import CrossData
from evaluator import QuantitativeEvaluator, QualitativeEvaluator
from subprocess import call, check_call


        
class HighOrder(object):
    def __init__(self, pd, graph_train, graph_test):
        self.pd = pd
        self.g = graph_train
        self.g_test = graph_test
        self.nt2nodes = self.construct_nt2nodes()
        # self.et2net = self.construct_et2net()
        self.et2net = self.construct_et2net_from_adjacency()        
        self.nt2vecs = None # center vectors
        self.nt2cvecs = None # context vectors


    def construct_nt2nodes(self):
        """
        Construct self.nt2nodes from self.g.node_type and self.g.node_dict
        self.g.node_type is a dictionary whose key is the node type and 
                value is a global node_id list of this type
        self.g.node_dict is a dictionary whose key is global node id and
                value is a list [node_type, intype_id, value]
        self.nt2nodes stores local id for type 't' and 'l' and value for 'w'
        """
        nt2nodes = {nt:set() for nt in self.pd['nt_list']}
        for n_id in self.g.node_type['t']:
            nt2nodes['t'].add(int(self.g.node_dict[n_id][1]))
        for n_id in self.g.node_type['l']:
            nt2nodes['l'].add(int(self.g.node_dict[n_id][1]))
        for n_id in self.g.node_type['w']:
            nt2nodes['w'].add(self.g.node_dict[n_id][2])
        return nt2nodes


    def construct_et2net(self):
        """
        Construct self.et2net from self.g.et2net
        self.g.et2net is a dictionary
            the first key is the edge type
            the second key is a 2-tuple (start_node, end_node) global id
            value is the weight
        self.et2net is a dictionary
            the first key is the edge type
            the second key is the start_node local id or value for word
            the third key is the end_node local id or value for word
            value is the weight
        """
        node_dict = self.g.node_dict
        et2net = defaultdict(lambda : defaultdict(lambda : defaultdict(float)))
        for key_et in self.g.et2net.keys():
            for key_s, key_t in self.g.et2net[key_et].keys():
                if key_et[0]=='w':
                    s = node_dict[key_s][2]
                else:
                    s = int(node_dict[key_s][1])
                if key_et[1]=='w':
                    t = node_dict[key_t][2]
                else:
                    t = int(node_dict[key_t][1])
                et2net[key_et][s][t] = self.g.et2net[key_et][(key_s,key_t)]
        return et2net


    def construct_et2net_from_adjacency(self):
        node_dict = self.g.node_dict
        et2net = defaultdict(lambda : defaultdict(lambda : defaultdict(float)))
        weight = {}
        for key_et in self.g.et2net.keys():
            weight[key_et] = np.mat(self.construct_adjacency_matrix(key_et))
        for key_et in self.g.et2net.keys(): 
            # W = weight[key_et]       
            if key_et=='ww':
                W = weight['ww']*weight['ww']
            else:
                W = weight[key_et]
            row, col = W.shape
            for s in xrange(row):
                for t in xrange(col):
                    if W[s,t] >1e-2:
                        if key_et[0]=='w':
                            key_id = self.g.node_id2id['w'][s]
                            key_s = self.g.node_dict[key_id][2]
                        else:
                            key_s = s
                        if key_et[1]=='w':
                            key_id = self.g.node_id2id['w'][t]
                            key_t = self.g.node_dict[key_id][2]
                        else:
                            key_t = t
                        et2net[key_et][key_s][key_t] = W[s,t]
        return et2net


        
    def construct_adjacency_matrix(self, et):
        """
        Construct adjacency matrix of edge type et from self.g.et2net[et] 
        adj_matrix[s, t] stores the weight of edge (s, t), s and t are local ids
        """
        node_dict = self.g.node_dict        
        start_num = len(self.g.node_type[et[0]])
        end_num = len(self.g.node_type[et[1]])        
        adj_matrix = np.zeros(shape=(start_num, end_num), dtype=np.float32)

        for key_s,key_t in self.g.et2net[et].keys():
            s = int(node_dict[key_s][1])
            t = int(node_dict[key_t][1])            
            adj_matrix[s, t] = self.g.et2net[et][(key_s, key_t)]
        # row normalization
        # return normalize(adj_matrix, norm='l1')     
        return adj_matrix           
  

    def modify_et2net(self, et, W):
        row, col = W.shape
        for s in xrange(row):
            for t in xrange(col):
                if W[s,t] >1e-2:
                    if et[0]=='w':
                        key_id = self.g.node_id2id['w'][s]
                        key_s = self.g.node_dict[key_id][2]
                    else:
                        key_s = s
                    if et[1]=='w':
                        key_id = self.g.node_id2id['w'][t]
                        key_t = self.g.node_dict[key_id][2]
                    else:
                        key_t = t
                    self.et2net[et][key_s][key_t] = W[s,t]

    def fit(self):
        self.embed_algo = GraphEmbed(self.pd)
        self.nt2vecs, self.nt2cvecs = self.embed_algo.fit(self.nt2nodes, self.et2net, self.pd['sample_size'])


    def mr_predict(self):
        test_data = pickle.load(open(self.pd['test_data'], 'r'))
        predictor = pickle.load(open(self.pd['crossmap'], 'r'))
        predictor.update_vec_cvec(self.nt2vecs, self.nt2cvecs)

        start_time = time.time()
        for t in self.pd['predict_type']:
            evaluator = QuantitativeEvaluator(predict_type=t)
            evaluator.get_ranks(test_data, predictor, self.g_test)
            # evaluator.get_ranks_with_output(test_data, predictor, config.result_pre+str(epoch)+t+'.txt')
            mrr, mr = evaluator.compute_mrr()
            print('Type:{} mr: {}, mrr: {} '.format(evaluator.predict_type, mr, mrr))
            mrr, mr = evaluator.compute_highest_mrr()
            print('Type:{} hmr: {}, hmrr: {} '.format(evaluator.predict_type, mr, mrr))
        print("Prediction done, elapsed time {}s".format(time.time()-start_time))   
        


class GraphEmbed(object):
	def __init__(self, pd):
		self.pd = pd
		self.nt2vecs = dict()
		self.nt2cvecs = dict()
		self.path_prefix = 'GraphEmbed/'
		self.path_suffix = '-'+str(os.getpid())+'.txt'

	def fit(self, nt2nodes, et2net, sample_size):
		self.write_line_input(nt2nodes, et2net)
		self.execute_line(sample_size)
		self.read_line_output()
		return self.nt2vecs, self.nt2cvecs

	def write_line_input(self, nt2nodes, et2net):
		if 'c' not in nt2nodes: # add 'c' nodes (with no connected edges) to comply to Line's interface
			nt2nodes['c'] = self.pd['category_list']
		for nt, nodes in nt2nodes.items():
			# print nt, len(nodes)
			node_file = open(self.path_prefix+'node-'+nt+self.path_suffix, 'w')
			for node in nodes:
				node_file.write(str(node)+'\n')
		all_et = [nt1+nt2 for nt1, nt2 in itertools.product(nt2nodes.keys(), repeat=2)]
		for et in all_et:
			edge_file = open(self.path_prefix+'edge-'+et+self.path_suffix, 'w')
			if et in et2net:
				for u, u_nb in et2net[et].items():
					for v, weight in u_nb.items():
						edge_file.write('\t'.join([str(u), str(v), str(weight), 'e'])+'\n')


	def execute_line(self, sample_size):
		command = ['./hin2vec']
		command += ['-size', str(self.pd['dim'])]
		command += ['-negative', str(self.pd['negative'])]
		command += ['-alpha', str(self.pd['alpha'])]
		sample_num_in_million = max(1, sample_size/1000000)
		command += ['-samples', str(sample_num_in_million)]
		command += ['-threads', str(10)]
		command += ['-second_order', str(self.pd['second_order'])]
		command += ['-job_id', str(os.getpid())]
		# call(command, cwd=self.path_prefix, stdout=open('stdout.txt','wb'))
		call(command, cwd=self.path_prefix)

	def read_line_output(self):
		for nt in self.pd['nt_list']:
			for nt2vecs,vec_type in [(self.nt2vecs,'output-'), (self.nt2cvecs,'context-')]:
				vecs_path = self.path_prefix+vec_type+nt+self.path_suffix
				vecs_file = open(vecs_path, 'r')
				vecs = dict()
				for line in vecs_file:
					node, vec_str = line.strip().split('\t')
					try:
						node = ast.literal_eval(node)
					except: # when nt is 'w', the type of node is string
						pass
					vecs[node] = np.array([float(i) for i in vec_str.split(' ')])
				nt2vecs[nt] = vecs
		for f in os.listdir(self.path_prefix): # clean up the tmp files created by this execution
		    if f.endswith(self.path_suffix):
		        os.remove(self.path_prefix+f)
       


if __name__ == "__main__":
    para_train = sys.argv[1]
    para_test = sys.argv[2]    
    pd = load_params(para_train)  # load parameters as a dict
    pd_test = load_params(para_test)  # load parameters as a dict    
    g_train = CrossData(pd)
    g_test = CrossData(pd_test)    

    model = HighOrder(pd, g_train, g_test)
    # W = model.construct_adjacency_matrix('ww')
    # model.modify_et2net('ww', W)
    print("Start training with new evaluation methods from test tweets, real_num=3, fake_num=7, ww=ww*ww!")
    start_time = time.time()
    model.fit()
    print("Model training done, elapsed time {}s".format(time.time()-start_time))   
    model.mr_predict()