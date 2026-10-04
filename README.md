# QAA AirType - 无线语音输入工具

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows&logoColor=white)
![Stars](https://img.shields.io/github/stars/QAA-Tools/qaa-airtype?style=flat&logo=github)
![License](https://img.shields.io/badge/License-MIT-green)

<div align="center">

<img src="demo.png" width="600" alt="Demo">

**通过手机端语音输入实现电脑端远程输入的便捷工具**

</div>

## 📖 项目简介

QAA AirType 是一个轻量级的远程输入工具，让你可以通过手机端的输入法（如豆包语音输入）来实现电脑端的文字输入。支持局域网直连和 Cloudflare Workers 跨网络两种模式。

### 为什么开发这个项目？

在日常使用中，我们发现：
- 电脑端的语音识别质量普遍较差
- 电脑的麦克风设备往往不够理想
- 手机端的语音输入法（如豆包输入法）识别准确率更高
- 需要一个简单的方式将手机的语音输入同步到电脑

因此，这个项目应运而生，让你可以充分利用手机端优秀的语音识别能力，提升电脑端的输入效率。

> **注意**：本程序目前主要针对 Windows 系统开发和测试，在 macOS 和 Linux 上可能需要额外的配置或存在兼容性问题。

## ✨ 主要特性

- 📱 **扫码即用**：启动程序后扫描二维码即可连接
- 📝 **历史记录**：保存最近10条输入记录，支持快速重发
- 🌐 **局域网模式**：无需互联网，同一 WiFi 下即可使用
- ☁️ **Cloudflare 模式**：自建免费 Workers 服务，突破局域网限制，手机流量也能用
- 📋 **多剪贴板占位符**：输入粘贴热词时立即保存当时的剪贴板，单条消息可依次嵌入多份文字、截图或文件
- 👀 **实时输入浮层**：桌面半透明显示手机端正在接收的文字，不抢焦点、不拦截鼠标
- 🟢 **服务状态控制**：桌面窗体明确显示启动、运行、异常与停止状态，可停止后再次启动
- 🔽 **系统托盘**：最小化到托盘，并可直接启动、停止或重启服务
- 📖 **详细文档**：[qaa-tools.github.io/qaa-airtype](https://qaa-tools.github.io/qaa-airtype/)

## 🚀 快速开始

### 方式一：下载可执行文件

1. 从 [Releases](https://github.com/QAA-Tools/qaa-airtype/releases) 下载 `QAA-AirType.exe`
2. 双击运行，选择连接模式（局域网 IP 或 Cloudflare）
3. 点击"启动服务"
4. 手机扫描二维码或访问显示的地址
5. 在手机网页使用语音输入，点击发送，文字自动粘贴到电脑

### 在一条消息中粘贴多份剪贴板内容

在桌面端的 `Keyword -> hotkey` 配置中，将任意热词配置为粘贴快捷键。下面的 `76632` 只是示例，并非程序内置值：

```json
[
  {"keyword": "76632", "keys": ["ctrl", "v"]}
]
```

程序会动态读取配置，找到所有绑定了 `Ctrl+V`、`Shift+Insert` 或 `paste` 动作的热词。描述过程中，每当输入框中新出现一次这样的热词，电脑端就会立即保存那一刻的完整剪贴板；最终发送时，各份内容会按热词出现的顺序嵌入目标文本。清空输入框会同时清除本条消息尚未发送的剪贴板快照。

### 方式二：从源码运行

```bash
git clone https://github.com/QAA-Tools/qaa-airtype.git
cd qaa-airtype

# 安装依赖
pip install flask pyautogui pyperclip qrcode pillow pystray

# 运行程序
python src/remote_server.py
```

## 🙏 致谢

- **Gemini**：核心程序编写
- **Claude**：项目标准化设计

---

<div align="center">

MIT License · Made with ❤️

</div>
