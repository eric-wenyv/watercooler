# WaterCooler

[English](README.md) | [简体中文](README.zh-CN.md)

WaterCooler 是一个 Linux 桌面工具，用于控制 `CoolingSystem` BLE 水冷设备。

本项目面向希望在 Linux 桌面上使用简单、轻量应用控制水冷设备的用户。我使用的笔记本是 MECHREVO，并在 Fedora 上进行测试。它也应该可以在其他拥有类似水冷系统的发行版上工作。

## tl;dr

使用 AI 阅读文档。

## 概览

启动后，WaterCooler 会扫描附近的 BLE 设备，并查找名称中包含 `CoolingSystem` 的设备。首次运行时，它会要求你在终端中选择目标设备。选中的设备会被保存，并在后续启动时复用。

运行期间，应用会读取：

- `/sys/class/thermal/thermal_zone0/temp` 中的 CPU 温度
- `nvidia-smi` 输出的 NVIDIA GPU 温度

它会使用两者中较高的温度计算目标速度，然后向水冷设备写入风扇和水泵命令。关闭时，它会在断开连接前尝试关闭 LED、风扇控制和水泵控制。

## 安装

### 1. 安装 WaterCooler

从 GitHub 安装：

```bash
curl -fsSL https://raw.githubusercontent.com/eric-wenyv/watercooler/main/scripts/install-user.sh | bash
```

安装脚本会创建：

- 命令：`~/.local/bin/watercooler`
- 桌面启动器：`~/.local/share/applications/watercooler.desktop`
- 图标：`~/.local/share/icons/hicolor/scalable/apps/watercooler.svg`
- 桌面启动日志：`~/.local/state/watercooler/watercooler.log`
- 独立虚拟环境：`~/.local/share/watercooler/venv`

### 2. 交互式运行一次

先从终端运行一次 WaterCooler，以便选择 BLE 设备：

```bash
watercooler
```

保存设备后，桌面启动器会在无终端窗口的后台启动 WaterCooler，为这次运行启用托盘，并把输出追加到桌面启动日志。如果只扫描到一个水冷设备，从桌面启动时也可以自动选择它。

选中的设备和 LED 设置会保存到：

```text
~/.config/watercooler/settings.json
```

### 3. 可选：注册用户服务

首次成功选择设备后，可以注册 systemd 用户服务：

```bash
curl -fsSL https://raw.githubusercontent.com/eric-wenyv/watercooler/main/scripts/install-user-service.sh | bash
```

服务会禁用托盘，并把输出写入：

```text
~/.local/state/watercooler/watercooler.service.log
```

### 4. 卸载

```bash
watercooler --uninstall
```

## 项目结构

核心应用代码位于 `src/watercooler`：

- `main.py`：扫描 BLE 设备、连接水冷设备、读取温度、计算目标速度，并发送风扇和水泵命令。
- `light.py`：封装 LED 控制命令。
- `config_manager.py`：加载和保存用户配置。
- `constant.py`：存储 BLE UUID 和配置文件路径。
- `tray_icon.py`：可选的系统托盘菜单支持。

安装后，`watercooler` 命令会运行 Python 包入口：

```bash
python -m watercooler
```

## 补充说明

托盘图标需要 Pillow 以及系统 GTK/AppIndicator 绑定。安装脚本会检测这些绑定，并在安装结束时输出托盘支持状态。GNOME 用户可能还需要启用 AppIndicator/KStatusNotifierItem shell 扩展。

可以用 `watercooler --tray` 为前台运行强制启用托盘，或用 `watercooler --no-tray` 进行类似服务的无托盘运行。如果 WaterCooler 以后台 systemd 用户服务运行，请保持托盘支持关闭。
