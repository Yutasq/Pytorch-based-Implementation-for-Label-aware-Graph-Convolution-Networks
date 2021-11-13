import math
import numpy as np
import torch

from src import utils


def ade(predAll, targetAll, count_):
    """
    Metric for Average Displacement Error: calculating the average error from the sampled trajectory (predAll) with the ground truth trajectory (targetAll)
    """
    All = len(predAll)
    sum_all = 0
    for s in range(All):
        pred = np.swapaxes(predAll[s][:, :count_[s], :], 0, 1)
        target = np.swapaxes(targetAll[s][:, :count_[s], :], 0, 1)

        N = pred.shape[0]
        T = pred.shape[1]
        sum_ = 0
        for i in range(N):
            for t in range(T):
                sum_ += math.sqrt((pred[i, t, 0] - target[i, t, 0]) ** 2 + (pred[i, t, 1] - target[i, t, 1]) ** 2)
        sum_all += sum_ / (N * T)

    return sum_all / All


def fde(predAll, targetAll, count_):
    """
    Metric for Final Displacement Error: calculating the minimum error from the sampled trajectory (predAll) with the ground truth trajectory (targetAll)
    """
    All = len(predAll)
    sum_all = 0
    for s in range(All):
        pred = np.swapaxes(predAll[s][:, :count_[s], :], 0, 1)
        target = np.swapaxes(targetAll[s][:, :count_[s], :], 0, 1)
        N = pred.shape[0]
        T = pred.shape[1]
        sum_ = 0
        for i in range(N):
            for t in range(T - 1, T):
                sum_ += math.sqrt((pred[i, t, 0] - target[i, t, 0]) ** 2 + (pred[i, t, 1] - target[i, t, 1]) ** 2)
        sum_all += sum_ / (N)

    return sum_all / All


def seq_to_nodes(seq_, max_nodes=88):
    seq_ = seq_.squeeze()
    seq_len = seq_.shape[2]

    V = np.zeros((seq_len, max_nodes, 2))
    for s in range(seq_len):
        step_ = seq_[:, :, s]
        for h in range(len(step_)):
            V[s, h, :] = step_[h]

    return V.squeeze()


def nodes_rel_to_nodes_abs(nodes, init_node):
    nodes_ = np.zeros_like(nodes)
    for s in range(nodes.shape[0]):
        for ped in range(nodes.shape[1]):
            nodes_[s, ped, :] = np.sum(nodes[:s + 1, ped, :], axis=0) + init_node[ped, :]

    return nodes_.squeeze()


def closer_to_zero(current, new_v):
    dec = min([(abs(current), current), (abs(new_v), new_v)])[1]
    if dec != current:
        return True
    else:
        return False


def bivariate_loss(V_pred, V_trgt, obs_classes, class_weights, labels):
    """
    Calculate loss from the estimated bi-variant distributions for every future time step
    Args: 
        V_pred: Predicted trajectory sequence in :math:`(max_nodes, node_dim, V)` format
        V_trgt: Target trajectory sequence in :math:`(max_nodes, node_dim, seq_len)` format
        obs_classes: The one-hot embedding of the object trajectories
        class_weights: Weights balancing the different classes
        labels: All the label categories of the trajectory
    """

    normx = V_trgt[:, :, 0] - V_pred[:, :, 0]
    normy = V_trgt[:, :, 1] - V_pred[:, :, 1]

    sx = torch.exp(V_pred[:, :, 2])  # sx
    sy = torch.exp(V_pred[:, :, 3])  # sy
    corr = torch.tanh(V_pred[:, :, 4])  # corr

    sxsy = sx * sy

    z = (normx / sx) ** 2 + (normy / sy) ** 2 - 2 * ((corr * normx * normy) / sxsy)
    negRho = 1 - corr ** 2

    # Numerator
    result = torch.exp(-z / (2 * negRho))
    # Normalization factor
    denom = 2 * np.pi * (sxsy * torch.sqrt(negRho))

    # Final PDF calculation
    result = result / denom

    # Numerical stability
    epsilon = 1e-20
    
    result = -torch.log(torch.clamp(result, min=epsilon))
    result = torch.mean(result)
    
    counts = [0] * len(labels)
    for enc in obs_classes:
        counts[utils.get_index_of_one_hot(enc.tolist(), labels)] += 1
    weight_sum = 0
    for i in range(len(counts)):
        weight_sum += (counts[i] * class_weights[i])
    return torch.mul(result, (weight_sum / sum(counts)))

def skeleton_loss(V_pred, V_trgt, obs_classes, class_weights, labels):
    """
    Calculate loss from the estimated 3D skeleton for every future time step
    Args: 
        V_pred: Predicted trajectory sequence in :math:`(max_nodes, node_dim, V)` format
        V_trgt: Target trajectory sequence in :math:`(max_nodes, node_dim, seq_len)` format
        obs_classes: The one-hot embedding of the object trajectories
        class_weights: Weights balancing the different classes
        labels: All the label categories of the trajectory
    """
    normx = V_trgt[:, :, 0] - V_pred[:, :, 0]
    normy = V_trgt[:, :, 1] - V_pred[:, :, 1]
    normz = V_trgt[:, :, 2] - V_pred[:, :, 2]

    loss = torch.norm(V_trgt - V_pred, dim=0)
    result = torch.mean(loss)

    counts = [0] * len(labels)
    for enc in obs_classes:
        counts[utils.get_index_of_one_hot(enc.tolist(), labels)] += 1
    weight_sum = 0
    for i in range(len(counts)):
        weight_sum += (counts[i] * class_weights[i])
    return torch.mul(result, (weight_sum / sum(counts)))
