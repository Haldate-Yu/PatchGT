# PatchGT: Transformer over Non-trainable Clusters for Learning Graph Representations

This repository contains PyTorch implementation of the submission: PatchGT: Transformer over Non-trainable Clusters for
Learning Graph Representations

## 0. Environment Setup

enviroment setup: "run conda install -f patchgt.yml"

## 1. Training

To list the arguments, run the following command:

```
python main_seq.py -h
```

To train the given model on ogbg dataset with PatchGT, run the following:

``` 
python run_ogb.py \
    --gnn_type <gin, deepergcn, gcn>                                  \
    --cluster_bar <0.1, 0.2, 0.5>                  \
    --dataset ogbg-molhiv                                  \                       
```    

To train the given model on TU dataset with PatchGT, run the following:

``` 
python run_TU.py \
    --gnn_type <gin, deepergcn, gcn>                                  \
    --cluster_bar <0.1, 0.2, 0.5>                  \
    --dataset DD                                 \                       
```    
   
## 如何修改
args.py中直接锁定cuda:0，运行时需手动指定cuda，CUDA_VISIBLE_DEVICES=gpu_id python xxx.py

在整体代码规范化后，新增添了几个参数，其中值得注意的是args.runs，其为重复实验次数，通过多次重复去平均值并加以记录，得到最终的实验结果。实验结果可以在results/中查看。
