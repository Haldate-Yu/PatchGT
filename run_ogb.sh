#!/bin/bash

# for TU Dataset
# MUTAG

# TU Dataset Settings
#

for dataset in ogbg-molhiv ogbg-molpcba; do
  for gnn in gin deepergcn gcn; do
    for cluster_threshold in 0.1 0.2 0.4 0.5 0.8; do
      python run_ogb.py --gcn_num_layers 5 --embd_pdrop 0.0 --n_embd 512 \
        --n_head 16 --batch_size 512 --epochs 150 --cluster_bar $cluster_threshold \
        --gnn_type $gnn --dataset $dataset
    done
  done
done
