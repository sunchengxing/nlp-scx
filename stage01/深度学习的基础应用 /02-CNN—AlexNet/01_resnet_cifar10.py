"""
ResNet 网络
===========
2015 年 ImageNet 冠军，核心创新：残差连接（Residual Connection）

解决的问题：网络越深 ≠ 效果越好
- 56 层网络比 20 层网络效果差（退化问题）
- 不是过拟合（训练误差也更高），而是优化困难

核心洞察：让网络学习"增量"（残差）比学习"完整映射"更容易
  普通网络: H(x) = 直接学目标映射
  残差网络: F(x) + x = 学习残差 F(x) = H(x) - x

  如果最优解是恒等映射（x不变），则 F(x)=0 比 H(x)=x 更容易学
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader

#  超参数 
batch_size = 64
learning_rate = 0.001
epochs = 10

#  1. 数据准备 
train_transform = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomCrop(32, padding=4),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616))
])
test_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616))
])

train_dataset = datasets.CIFAR10('./data', train=True, download=True, transform=train_transform)
test_dataset = datasets.CIFAR10('./data', train=False, download=True, transform=test_transform)
train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)


#  2. ResNet 模型 
class BasicBlock(nn.Module):
    """
    ResNet 基本残差块

    普通块:  x → Conv → BN → ReLU → Conv → BN → 输出
    残差块:  x → Conv → BN → ReLU → Conv → BN → + x → ReLU
                                              ↑
                                         残差连接（shortcut）

    关键：F(x) + x 这个加法操作
    - 梯度可以直接通过 x 这条路传回去（跳跃连接）
    - 不用穿过所有卷积层 → 解决梯度消失
    - 网络至少不会比浅层网络差（最差 F(x)=0，退化为恒等映射）
    """
    expansion = 1  # 基础块不扩展通道

    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()

        # 主路径：两个 3×3 卷积
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3,
                               stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)

        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3,
                               stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

        # 残差连接（shortcut）
        # 如果输入输出维度不同（stride>1 或通道数不同），需要 1×1 卷积对齐
        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        # 主路径
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        # 残差连接：主路径输出 + shortcut(x)
        out += self.shortcut(x)  # ← 这就是残差连接！
        out = torch.relu(out)
        return out


class ResNet18(nn.Module):
    """
    ResNet-18，适配 CIFAR-10

    结构: 4 组残差块，每组 2 个 BasicBlock
    通道: [64, 128, 256, 512]
    尺寸: 32 → 16 → 8 → 4 → 2

    残差连接为什么有效？
    1. 梯度直通车：梯度可以通过 shortcut 直接流向前面的层
       没有 shortcut: ∂L/∂x₁ = W₁·W₂·...·Wₙ（连乘衰减）
       有 shortcut:  ∂L/∂x₁ = W₁·W₂·...·Wₙ + 1（至少有一条无损路径）

    2. 学习增量更容易：F(x) = H(x) - x
       如果最优解接近恒等映射，F(x)≈0 比 H(x)≈x 更容易学
       （权重初始化接近0时，F(x)自动接近0）

    3. 退化问题解决：网络至少不比浅层差
       最差情况 F(x)=0 → 输出 = x（恒等映射，等于没加这层）
    """
    def __init__(self, num_classes=10):
        super().__init__()

        # 初始卷积（CIFAR-10 用 3×3，ImageNet 原版用 7×7）
        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)

        # 4 组残差块
        self.layer1 = self._make_layer(64, 64, num_blocks=2, stride=1)   # 32×32
        self.layer2 = self._make_layer(64, 128, num_blocks=2, stride=2)   # 16×16
        self.layer3 = self._make_layer(128, 256, num_blocks=2, stride=2)  # 8×8
        self.layer4 = self._make_layer(256, 512, num_blocks=2, stride=2)  # 4×4

        self.linear = nn.Linear(512, num_classes)

    def _make_layer(self, in_channels, out_channels, num_blocks, stride):
        layers = []
        layers.append(BasicBlock(in_channels, out_channels, stride))
        for _ in range(1, num_blocks):
            layers.append(BasicBlock(out_channels, out_channels, stride=1))
        return nn.Sequential(*layers)

    def forward(self, x):
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = torch.avg_pool2d(out, 4)  # 全局平均池化: (batch, 512, 4, 4) → (batch, 512, 1, 1)
        out = out.view(out.size(0), -1)
        out = self.linear(out)
        return out

model = ResNet18()
print(f"模型结构:\n{model}")
total_params = sum(p.numel() for p in model.parameters())
print(f"总参数量: {total_params:,}")


#  3. 训练 
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=learning_rate)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.5)

print("\n" + "=" * 50)
print("开始训练 ResNet-18")
print("=" * 50)

for epoch in range(epochs):
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for images, labels in train_loader:
        logits = model(images)
        loss = criterion(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        pred = logits.argmax(dim=1)
        correct += (pred == labels).sum().item()
        total += labels.size(0)

    scheduler.step()
    acc = 100 * correct / total
    print(f"Epoch {epoch+1}/{epochs} | Loss: {total_loss/len(train_loader):.4f} | 准确率: {acc:.1f}%")


#  4. 测试 
model.eval()
correct = 0
total = 0
with torch.no_grad():
    for images, labels in test_loader:
        logits = model(images)
        pred = logits.argmax(dim=1)
        correct += (pred == labels).sum().item()
        total += labels.size(0)

print(f"\n测试准确率: {100 * correct / total:.1f}%")


#  5. ResNet 关键知识点
"""
ResNet 的演进意义：

| 模型    | 深度   | ImageNet Top-5 | 核心创新              |
|--------|--------|---------------|----------------------|
| AlexNet| 8 层   | 84.7%         | ReLU + Dropout       |
| VGG-16 | 16 层  | 92.3%         | 全 3×3 卷积堆叠       |
| ResNet | 18-152 | 96.4%         | 残差连接              |

残差连接的本质：
  普通网络: y = F(x)        → 学习完整映射，深层难优化
  残差网络: y = F(x) + x    → 学习增量/残差，深层也能优化

  梯度传播对比：
  无 shortcut: ∂L/∂x = ∂L/∂y × W₁ × W₂ × ... × Wₙ  （连乘衰减）
  有 shortcut: ∂L/∂x = ∂L/∂y × (W₁×W₂×...×Wₙ + 1)  （+1 保底）

  这和 LSTM 的细胞状态 C_t 更新是同一个思想！
  LSTM: C_t = f_t⊙C_{t-1} + i_t⊙g_t  ← 加法路径，梯度不消失
  ResNet: y = F(x) + x               ← 加法路径，梯度不消失
"""

