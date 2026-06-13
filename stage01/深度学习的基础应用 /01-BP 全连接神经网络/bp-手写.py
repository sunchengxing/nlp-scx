from typing import List
import matplotlib.pyplot as plt
import numpy as np

# 输入x
x = np.asarray([
    [4., 12.0]
])
# 输入y
y = np.asarray([
    [0.01, 0.99]
])
# 需要学习的模型参数
w = np.asarray([
    0.12, 0.32, 0.4, 0.25, 0.31, 0.35,
    0.42, 0.14, 0.5, 0.53, 0.06, 0.65
])
# 样本 - 目标特征y
y = np.asarray([
    [0.01, 0.99]
])

b = np.asarray([
    0.01, 0.01
])

# 学习率 -> 参数更新时候的超参数
alpha = 0.5

# 模型训练学习的参数w
def _w(i):
    return w[i - 1]

# 偏置 bias
def _b(i):
    return b[i - 1]

# 属于x
def _x(i):
    return x[0][i - 1]

# 实际值y
def _y(i):
    return y[0][i - 1]

# 参数更新
def update_w(i, gd):
    # 基于梯度的参数更新公式
   w[i - 1] = w[i - 1] - alpha * gd

# 激活函数
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))

# 前向过程 本BP 模拟路径规划网络结构来自：
# file:///Users/scx/data/codeData/python/dl/stage02/03.%E6%B7%B1%E5%BA%A6%E5%AD%A6%E4%B9%A0%E5%9F%BA%E7%A1%80/BP%E5%8F%8D%E5%90%91%E4%BC%A0%E6%92%AD%E5%8A%A8%E7%94%BB.html
def forward():
    # layer-one
    net_h1 = _w(1) * _x(1) + _w(2) * _x(2) + _b(1)
    out_h1 = sigmoid(net_h1)
    net_h2 = _w(3) * _x(1) + _w(4) * _x(2) + _b(1)
    out_h2 = sigmoid(net_h2)
    net_h3 = _w(5) * _x(1) + _w(6) * _x(2) + _b(1)
    out_h3 = sigmoid(net_h3)

    # layer-two
    net_o1 = _w(7) * out_h1 + _w(9) * out_h2 + _w(11) * out_h3 + _b(2)
    out_o1 = sigmoid(net_o1)
    net_o2 = _w(8) * out_h1 + _w(10) * out_h2 + _w(12) * out_h3 + _b(2)
    out_o2 = sigmoid(net_o2)

    # 计算损失
    loss_1 = 0.5 * (out_o1 - _y(1)) ** 2
    loss_2 = 0.5 * (out_o2 - _y(2)) ** 2

    # 当前样本总的损失
    loss = loss_1 + loss_2

    # 反向传播更新参数 先计算每一个环节的损失 loss1对于out_o1的导数，即损失对于out_o1的导数
    # ∂L /∂outo1 = outo1 - y₁
    out_o1_gradient = out_o1 - _y(1)
    # ∂L/∂outo2 = outo2 - y₂
    out_o2_gradient = out_o2 - _y(2)
    # ∂L/∂(neto1) = ∂L /∂outo1 * ∂outo1/∂(neto1)
    net_o1_gradient = (out_o1 - _y(1)) * (out_o1 * (1 - out_o1))
    # ∂L/∂(neto2) = ∂L /∂outo2 * ∂outo2/∂(neto2)
    net_o2_gradient = (out_o2 - _y(2)) * (out_o2 * (1 - out_o2))


    # 损失关于各个参数的导 损失关于w7的导数
    w_7_gradient = (out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * out_h1
    w_8_gradient = (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * out_h1
    w_9_gradient = (out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * out_h2
    w_10_gradient = (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * out_h2
    w_11_gradient = (out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * out_h3
    w_12_gradient = (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * out_h3

    out_h1_gradient = (out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(7) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(8)
    out_h2_gradient = (out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(9) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(10)
    out_h3_gradient = (out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(11) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(12)

    net_h1_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(7) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(8)) * sigmoid(net_h1) * (1 - sigmoid(net_h1))
    net_h2_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(9) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(10)) * sigmoid(net_h2) * (1 - sigmoid(net_h2))
    net_h3_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(11) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(12)) * sigmoid(net_h3) * (1 - sigmoid(net_h3))

    w_1_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(7) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(8)) * sigmoid(net_h1) * (1 - sigmoid(net_h1)) * _x(1)
    w_2_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(7) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(8)) * sigmoid(net_h1) * (1 - sigmoid(net_h1)) * _x(2)
    w_3_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(9) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(10)) * sigmoid(net_h2) * (1 - sigmoid(net_h2)) * _x(1)
    w_4_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(9) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(10)) * sigmoid(net_h2) * (1 - sigmoid(net_h2)) * _x(2)
    w_5_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(11) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(12)) * sigmoid(net_h3) * (1 - sigmoid(net_h3)) * _x(1)
    w_6_gradient = ((out_o1 - _y(1)) * (out_o1 * (1 - out_o1)) * _w(11) + (out_o2 - _y(2)) * (out_o2 * (1 - out_o2)) * _w(12)) * sigmoid(net_h3) * (1 - sigmoid(net_h3)) * _x(2)

    gradient_list =  [
        w_1_gradient, w_2_gradient, w_3_gradient, w_4_gradient, w_5_gradient, w_6_gradient,
        w_7_gradient, w_8_gradient, w_9_gradient, w_10_gradient, w_11_gradient, w_12_gradient
    ]

    return gradient_list, loss, out_o1, out_o2

def backward(gradient_list:List[float]):
    # 反向传播参数更新
    for gradient_index,  gradient in enumerate(gradient_list):
        update_w(gradient_index + 1, gradient)

if __name__ == '__main__':
    _loss = []
    gradient_list, _current_loss, out_o1, out_o2 = forward()
    backward(gradient_list)
    _loss.append(_current_loss)  # 将当前这次计算的样本损失保存到列表中
    print(f"当前样本损失: {_current_loss}")
    print(f"当前样本的预测节点/输出节点值: {out_o1, out_o2}")
    print(_w)

    for i in range(1000):
        gradient_list, _current_loss, out_o1, out_o2 = forward()
        backward(gradient_list)
        _loss.append(_current_loss)  # 将当前这次计算的样本损失保存到列表中
        print("=" * 100)
        print("总的迭代更新完成后的结果:")
        print(f"当前样本损失: {_current_loss}")
        print(f"当前样本的预测节点/输出节点值: {out_o1, out_o2}")
        print(_w)
        plt.plot(_loss)
        plt.show()