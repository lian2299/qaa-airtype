# 代码重构说明

## 已完成的重构

为了减少单个文件的大小，已将代码模块化拆分：

### 已创建的模块

1. **src/config.py** - 配置文件管理
   - `get_config_path()` - 获取配置文件路径
   - `load_config()` - 加载配置
   - `save_config()` - 保存配置

2. **src/utils.py** - 工具函数和常量
   - `IS_MAC`, `IS_WINDOWS`, `PASTE_KEY` - 平台常量
   - Windows API 常量 (`VK_SHIFT`, `VK_INSERT`, etc.)
   - `get_icon_path()` - 获取图标路径
   - `get_host_ip()` - 获取主机IP
   - `get_all_ips()` - 获取所有IP地址

3. **src/clipboard.py** - 剪贴板操作
   - `clipboard_get()` - 获取剪贴板内容
   - `clipboard_set()` - 设置剪贴板内容
   - 支持 clipman 避免触发 Ditto 等工具

4. **src/audio.py** - 音频控制
   - `set_system_mute_windows()` - Windows系统静音控制
   - 音频状态管理 (`auto_mute_enabled`, `current_muted_by_app`, etc.)

5. **src/keyboard.py** - 键盘输入
   - `ensure_insert_mode_reset()` - 确保插入模式
   - `send_shift_insert_windows()` - 发送 Shift+Insert
   - `send_ctrl_v_windows()` - 发送 Ctrl+V
   - `paste_text()` - 复制并粘贴文本

6. **src/cf_client.py** - Cloudflare客户端
   - `derive_key_and_room()` - 派生密钥和房间ID
   - `decrypt_message()` - 解密消息
   - `CFChatClient` - CF模式WebSocket客户端类

7. **src/state.py** - 运行时状态管理
   - `use_ctrl_v` - 粘贴模式配置
   - `preserve_clipboard` - 剪贴板保护配置
   - `auto_minimize` - 自动最小化配置

## 已完成的新模块

8. **src/web_routes.py** - Flask路由处理
   - `register_routes(app, html_template)` - 注册所有Flask路由
   - `/` - 主页路由
   - `/mute` - 切换自动静音
   - `/mute_immediate` - 立即静音/取消静音
   - `/type` - 文本输入处理

## 待完成的工作（可选）

由于 `remote_server.py` 文件较大（2201行），以下工作可选完成：

1. **GUI类提取** (可选，建议保持现状)
   - 将 `ServerApp` 类提取到 `src/gui.py`
   - 注意：GUI类与Flask app耦合较紧，提取可能增加复杂性

2. **主文件重构** (可选)
   - 将 `remote_server.py` 重构为简洁的主入口文件
   - 使用 `register_routes(app, HTML_TEMPLATE)` 注册路由
   - 导入并使用新的模块

## 如何使用新模块

### 在 remote_server.py 中使用新模块

新模块可以在 `remote_server.py` 中导入使用。以下是迁移示例：

#### 1. 替换配置管理

**原代码：**
```python
def get_config_path():
    # ... 代码在remote_server.py中
```

**新代码：**
```python
from .config import get_config_path, load_config, save_config
```

#### 2. 替换工具函数

**原代码：**
```python
def get_icon_path():
    # ... 代码在remote_server.py中
```

**新代码：**
```python
from .utils import IS_WINDOWS, get_icon_path, get_all_ips
```

#### 3. 替换剪贴板操作

**原代码：**
```python
def clipboard_get():
    # ... 代码在remote_server.py中
```

**新代码：**
```python
from .clipboard import clipboard_get, clipboard_set
```

#### 4. 替换键盘输入

**原代码：**
```python
def paste_text(text):
    # ... 代码在remote_server.py中
```

**新代码：**
```python
from .keyboard import paste_text, send_shift_insert_windows, send_ctrl_v_windows
from .state import use_ctrl_v, preserve_clipboard

# 使用时传入参数
paste_text(text, use_ctrl_v=use_ctrl_v, preserve_clipboard=preserve_clipboard)
```

#### 5. 替换Flask路由

**原代码：**
```python
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)
# ... 其他路由
```

**新代码：**
```python
from .web_routes import register_routes

# 在创建Flask app后注册路由
app = Flask(__name__)
register_routes(app, HTML_TEMPLATE)
```

#### 6. 替换CF客户端

**原代码：**
```python
class CFChatClient:
    # ... 代码在remote_server.py中
```

**新代码：**
```python
from .cf_client import CFChatClient
```

### 模块依赖关系

- `config.py` - 独立模块
- `utils.py` - 独立模块（提供平台常量）
- `state.py` - 独立模块（运行时状态）
- `clipboard.py` - 依赖 `pyperclip`/`clipman`
- `audio.py` - 依赖 `utils.IS_WINDOWS`
- `keyboard.py` - 依赖 `utils`, `clipboard`
- `cf_client.py` - 独立模块（可选依赖 `websockets`, `cryptography`）
- `web_routes.py` - 依赖 `audio`, `keyboard`, `state`, `utils`

## 注意事项

- 所有模块都已经过基本检查，没有语法错误
- 模块之间的依赖关系已经处理
- 建议在完全重构前进行充分测试

