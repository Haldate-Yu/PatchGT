#!/bin/bash

# for TU Dataset
# MUTAG

# TU Dataset Settings
#

for dataset in IMDB-BINARY IMDB-MULTI REDDIT_BINARY COLLAB; do
  for gnn in gin deepergcn gcn; do
    for cluster_threshold in 0.1 0.2 0.4 0.5 0.8; do
      python run_TU.py --gcn_num_layers 4 --embd_pdrop 0.1 --n_embd 256 \
        --n_head 4 --batch_size 256 --epochs 50 --cluster_bar $cluster_threshold \
        --gnn_type $gnn --dataset $dataset
    done
  done
done
