import torch
from ogb.graphproppred.mol_encoder import AtomEncoder, BondEncoder
from model.attention import AttentionDecoder
from model.basic import MLP_PLain, MLP_multi, basic_MLP, GIN, MLP_Sigmoid
import os
import csv
import random
import pickle
from pynvml import *
from torch_geometric.utils import degree
import torch_geometric.transforms as T

from sklearn.metrics import roc_auc_score, average_precision_score
import numpy as np


def num_total_parameters(model):
    return sum(p.numel() for p in model.parameters())


def num_trainable_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def print_gpu_utilization(device_index):
    nvmlInit()
    handle = nvmlDeviceGetHandleByIndex(device_index)
    info = nvmlDeviceGetMemoryInfo(handle)
    print(f"GPU memory occupied: {info.used // 1024 ** 2} MB.")
    return info.used // 1024 ** 2


def seed_everything(seed):
    r"""Sets the seed for generating random numbers in PyTorch, numpy and
        Python.

        Args:
            seed (int): The desired seed.
        """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def results_to_file(args, test_acc, test_std,
                    total_time, total_time_std,
                    avg_time, avg_time_std,
                    test_time, test_time_std):
    if not os.path.exists('./results/{}'.format(args.dataset)):
        print("=" * 20)
        print("Creating Results File !!!")

        os.makedirs('./results/{}'.format(args.dataset))

    filename = "./results/{}/result_batchsize{}_layers{}.csv".format(
        args.dataset, args.batch_size, args.n_layer)

    if args.dataset_type == 'TU':
        headerList = ["Method", "N_Heads", "Batch_Size",
                      "Encoder_Layers", "Hidden_Dims",
                      "GNN_Type", "Cluster_Bar",
                      "Model_Params", "Memory_Usage(MB)",
                      "::::::::",
                      "test_acc", "test_std",
                      "total_time", "total_time_std",
                      "avg_time", "avg_time_std",
                      "test_time", "test_time_std"]
    elif args.dataset_type == 'OGB':
        headerList = ["Method", "N_Heads", "Batch_Size",
                      "Encoder_Layers", "Hidden_Dims", "GNN_Type"
                                                       "Model_Params", "Memory_Usage(MB)",
                      "::::::::",
                      "test_auc", "test_std",
                      "total_time", "total_time_std",
                      "avg_time", "avg_time_std",
                      "test_time", "test_time_std"]

    with open(filename, "a+") as f:

        # reader = csv.reader(f)
        # row1 = next(reader)
        f.seek(0)
        header = f.read(6)
        if header != "Method":
            dw = csv.DictWriter(f, delimiter=',',
                                fieldnames=headerList)
            dw.writeheader()

        line = "{}, {}, {}, {}, {}, {}, {}, {}, {}, :::::::::, {:.4f}, {:.4f}, {:.4f}, {:.4f}, {:.4f}, {:.4f}, {:.4f}, {:.4f}\n".format(
            "PatchGT", args.n_head, args.batch_size,
            args.n_layer, args.n_embd,
            args.gnn_type, args.cluster_bar,
            args.total_params, args.memory_usage,
            test_acc, test_std,
            total_time, total_time_std,
            avg_time, avg_time_std,
            test_time, test_time_std
        )
        f.write(line)


class NormalizedDegree(object):
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def __call__(self, data):
        deg = degree(data.edge_index[0], dtype=torch.float)
        deg = (deg - self.mean) / self.std
        data.x = deg.view(-1, 1)
        return data


def TU_Preprocess(dataset):
    if dataset.data.x is None:
        max_degree = 0
        degs = []
        for data in dataset:
            degs += [degree(data.edge_index[0], dtype=torch.long)]
            max_degree = max(max_degree, degs[-1].max().item())

        if max_degree < 1000:
            dataset.transform = T.OneHotDegree(max_degree)
        else:
            deg = torch.cat(degs, dim=0).to(torch.float)
            mean, std = deg.mean().item(), deg.std().item()
            dataset.transform = NormalizedDegree(mean, std)
    return dataset


def create_models(args):
    return AtomEncoder(emb_dim=args.n_embd).to(args.device), BondEncoder(emb_dim=args.n_embd).to(args.device), GIN(
        args.num_node_features,
        args.gcn_num_layers,
        args.n_embd, args.n_embd).to(
        args.device).to(args.device), MGN(args.patch_gcn_num_layers, args.n_embd, in_edge_channels=4,
                                          out_channels=args.n_embd, hidFeature=args.n_embd, aggr='max').to(args.device), \
        AttentionDecoder(args).to(args.device), MLP_PLain(args.n_embd, args.n_embd, 1).to(args.device)


def create_TUmodels(args):
    if args.num_classes == 2:
        return basic_MLP(args.input_embd, args.n_embd, args.n_embd).to(args.device), GIN(args.n_embd,
                                                                                         args.gcn_num_layers,
                                                                                         args.n_embd, args.n_embd).to(
            args.device), MGN(args.patch_gcn_num_layers, args.n_embd, in_edge_channels=4, out_channels=args.n_embd,
                              hidFeature=args.n_embd, ).to(args.device), \
            AttentionDecoder(args).to(args.device), MLP_Sigmoid(args.n_embd, args.n_embd).to(args.device)
    else:
        return basic_MLP(args.input_embd, args.n_embd, args.n_embd).to(args.device), GIN(args.n_embd,
                                                                                         args.gcn_num_layers,
                                                                                         args.n_embd, args.n_embd).to(
            args.device), MGN(args.patch_gcn_num_layers, args.n_embd, in_edge_channels=4, out_channels=args.n_embd,
                              hidFeature=args.n_embd, ).to(args.device), \
            AttentionDecoder(args).to(args.device), MLP_multi(args.n_embd, args.n_embd, args.num_classes).to(
            args.device)


def binary_aac(y_pred, y_true):
    '''
    :param y_pred: Tensor (batch_size, 1)
    :param y_true: Tensor (batch_size, 1)
    :return: acc: float
    '''
    y_pred_tag = torch.round(y_pred)
    correct_results_sum = (y_pred_tag == y_true).sum().float()
    acc = correct_results_sum / y_true.shape[0]

    return acc


def binary_aac_sigmoid(y_pred, y_true):
    '''
    :param y_pred: Tensor (batch_size, 1)
    :param y_true: Tensor (batch_size, 1)
    :return: acc: float
    '''
    y_pred = torch.nn.Sigmoid()(y_pred)

    y_prob = y_pred > 0.5
    return (y_true == y_prob).sum().item() / y_true.size(0)

    return acc


def eval_rocauc(y_pred, y_true):
    y_true = y_true.cpu().numpy()
    y_pred = y_pred.cpu().detach().numpy()

    rocauc_list = []

    for i in range(y_true.shape[1]):
        # AUC is only defined when there is at least one positive data.
        if np.sum(y_true[:, i] == 1) > 0 and np.sum(y_true[:, i] == 0) > 0:
            # ignore nan values
            is_labeled = y_true[:, i] == y_true[:, i]
            rocauc_list.append(roc_auc_score(y_true[is_labeled, i], y_pred[is_labeled, i]))

    if len(rocauc_list) == 0:
        raise RuntimeError('No positively labeled data available. Cannot compute ROC-AUC.')

    return sum(rocauc_list) / len(rocauc_list)


def multi_acc(y_pred, y_true):
    y_pred = y_pred.max(1)[1]

    correct = y_pred.eq(y_true.view(-1)).sum().item()
    return correct / y_true.shape[0]


def save_model(epoch, args, model):
    if not os.path.isdir(args.current_model_save_path):
        os.makedirs(args.current_model_save_path)
    fname = args.current_model_save_path + 'epoch' + '_' + str(epoch) + '.dat'
    checkpoint = {'saved_args': args, 'epoch': epoch, 'model': model}
    torch.save(checkpoint, fname)


def save_processed_dataset(args, color_list, color_number, center_list, max_length, sender_list, receiver_list,
                           test_color_list, test_color_number, test_max_length, test_sender_list, test_receiver_list):
    dataname = "prcessed_dataset/" + str(args.dataset) + "/" + str(args.normalized) + "bar_" + str(args.cluster_bar)
    if not os.path.isdir(dataname):
        os.mkdir(dataname)
    dataname = "prcessed_dataset/" + str(args.dataset) + "/" + str(args.normalized) + "bar_" + str(
        args.cluster_bar) + "/"

    with open(dataname + "color_list.txt", "wb") as fp:  # Pickling
        pickle.dump(color_list, fp, protocol=2)
    with open(dataname + "color_number.txt", "wb") as fp:  # Pickling
        pickle.dump(color_number, fp, protocol=2)
    with open(dataname + "center_list.txt", "wb") as fp:  # Pickling
        pickle.dump(center_list, fp, protocol=2)
    with open(dataname + "max_length.txt", "wb") as fp:  # Pickling
        pickle.dump(max_length, fp, protocol=2)
    with open(dataname + "sender_list.txt", "wb") as fp:  # Pickling
        pickle.dump(sender_list, fp, protocol=2)
    with open(dataname + "receiver_list.txt", "wb") as fp:  # Pickling
        pickle.dump(receiver_list, fp, protocol=2)

    with open(dataname + "test_color_list.txt", "wb") as fp:  # Pickling
        pickle.dump(test_color_list, fp)
    with open(dataname + "test_color_number.txt", "wb") as fp:  # Pickling
        pickle.dump(test_color_number, fp)
    with open(dataname + "test_center_list.txt", "wb") as fp:  # Pickling
        pickle.dump(center_list, fp)
    with open(dataname + "test_max_length.txt", "wb") as fp:  # Pickling
        pickle.dump(test_max_length, fp)
    with open(dataname + "test_sender_list.txt", "wb") as fp:  # Pickling
        pickle.dump(test_sender_list, fp)
    with open(dataname + "test_receiver_list.txt", "wb") as fp:  # Pickling
        pickle.dump(test_receiver_list, fp)


def load_processed_dataset(args):
    dataname = "prcessed_dataset/" + str(args.dataset) + "/" + str(args.normalized) + "bar_" + str(args.cluster_bar)
    assert len(os.listdir(dataname)) != 0
    dataname = "prcessed_dataset/" + str(args.dataset) + '/' + str(args.normalized) + "bar_" + str(
        args.cluster_bar) + "/"
    with open(dataname + "color_list.txt", "rb") as fp:  # Pickling
        color_list = pickle.load(fp)
    with open(dataname + "color_number.txt", "rb") as fp:  # Pickling
        color_number = pickle.load(fp)
    with open(dataname + "center_list.txt", "rb") as fp:  # Pickling
        center_list = pickle.load(fp)
    with open(dataname + "max_length.txt", "rb") as fp:  # Pickling
        max_length = pickle.load(fp)
    with open(dataname + "sender_list.txt", "rb") as fp:  # Pickling
        sender_list = pickle.load(fp)
    with open(dataname + "receiver_list.txt", "rb") as fp:  # Pickling
        receiver_list = pickle.load(fp)

    with open(dataname + "test_color_list.txt", "rb") as fp:  # Pickling
        test_color_list = pickle.load(fp)
    with open(dataname + "test_color_number.txt", "rb") as fp:  # Pickling
        test_color_number = pickle.load(fp)
    with open(dataname + "test_center_list.txt", "rb") as fp:  # Pickling
        test_center_list = pickle.load(fp)
    with open(dataname + "test_max_length.txt", "rb") as fp:  # Pickling
        test_max_length = pickle.load(fp)
    with open(dataname + "test_sender_list.txt", "rb") as fp:  # Pickling
        test_sender_list = pickle.load(fp)
    with open(dataname + "test_receiver_list.txt", "rb") as fp:  # Pickling
        test_receiver_list = pickle.load(fp)
    return color_list, color_number, center_list, max_length, sender_list, receiver_list, \
        test_color_list, test_color_number, test_center_list, test_max_length, test_sender_list, test_receiver_list
