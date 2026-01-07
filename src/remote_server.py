import socket
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from flask import Flask, request, render_template_string
import pyautogui
import pyperclip
import platform
import time
import logging
import qrcode
from PIL import Image, ImageTk
import io
import pystray
from pystray import MenuItem as item
import os
import sys
import tempfile
import ctypes
import asyncio
import hashlib
import json

# 尝试导入 clipman（避免触发剪贴板历史工具如 Ditto）
try:
    import clipman
    CLIPMAN_AVAILABLE = True
    print("clipman library available - clipboard history tools will not be triggered")
except ImportError:
    CLIPMAN_AVAILABLE = False
    print("clipman not available - using pyperclip (may trigger clipboard history tools)")

# CF 模式依赖（可选）
try:
    import websockets
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CF_AVAILABLE = True
except ImportError:
    CF_AVAILABLE = False

# --- 配置文件 ---
def get_config_path():
    """获取配置文件路径"""
    if IS_WINDOWS:
        config_dir = os.path.join(os.environ.get('APPDATA', ''), 'QAA-AirType')
    else:
        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'qaa-airtype')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'config.json')

def load_config() -> dict:
    """加载配置"""
    try:
        config_path = get_config_path()
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config(config: dict):
    """保存配置"""
    try:
        config_path = get_config_path()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置失败: {e}")

# --- 资源路径处理 ---
def get_icon_path():
    """获取图标路径，支持开发环境和打包后的环境"""
    # 如果是 PyInstaller 打包的程序
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
        if os.path.exists(icon_path):
            return icon_path

    # 开发环境或当前目录
    if os.path.exists('icon.ico'):
        return 'icon.ico'

    return None

# --- Flask 应用配置 ---
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- HTML 模板 (保持之前的历史记录功能) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>无线键盘</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            padding: 20px; 
            text-align: center; 
            background-color: #f5f5f7; 
            color: #333;
        }
        h2 { margin-bottom: 20px; font-weight: 600; }
        .last-sent-label {
            width: 100%; 
            padding: 12px 15px; 
            margin-bottom: 10px;
            font-size: 14px; 
            border-radius: 8px;
            border: 1px solid #e5e5ea; 
            box-sizing: border-box;
            background: #f8f8f8; 
            color: #666;
            min-height: 44px;
            word-wrap: break-word;
            white-space: pre-wrap;
            text-align: left;
            display: flex;
            align-items: center;
        }
        .input-group { margin-bottom: 15px; }
        input[type="text"] {
            width: 100%; padding: 15px; font-size: 16px; border-radius: 12px;
            border: 1px solid #d1d1d6; box-sizing: border-box; outline: none;
            background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            transition: border-color 0.2s;
        }
        input[type="text"]:focus { border-color: #007AFF; }
        textarea {
            width: 100%; padding: 15px; font-size: 16px; border-radius: 12px;
            border: 1px solid #d1d1d6; box-sizing: border-box; outline: none;
            background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            transition: border-color 0.2s;
            resize: vertical;
            min-height: 120px;
            font-family: inherit;
            line-height: 1.5;
        }
        textarea:focus { border-color: #007AFF; }
        .button-group { display: flex; gap: 10px; margin-bottom: 15px; }
        button {
            flex: 1; padding: 15px; font-size: 18px; color: white;
            border: none; border-radius: 12px; cursor: pointer; font-weight: 600;
            transition: background-color 0.1s, transform 0.1s;
        }
        button#sendBtn {
            background-color: #007AFF;
            box-shadow: 0 4px 6px rgba(0,122,255,0.2);
        }
        button#sendBtn:active { background-color: #0056b3; transform: scale(0.98); }
        button#clearBtn {
            background-color: #8e8e93;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        button#clearBtn:active { background-color: #636366; transform: scale(0.98); }
        #status { margin-top: 10px; height: 20px; font-size: 14px; color: #34c759; font-weight: 500;}
        .auto-send-switch { 
            margin-top: 10px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            gap: 8px;
            font-size: 14px;
            color: #666;
        }
        .switch-container {
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }
        .switch-input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .switch-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: 0.3s;
            border-radius: 24px;
        }
        .switch-slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: 0.3s;
            border-radius: 50%;
        }
        .switch-input:checked + .switch-slider {
            background-color: #007AFF;
        }
        .switch-input:checked + .switch-slider:before {
            transform: translateX(20px);
        }
        .history-container { margin-top: 30px; text-align: left; }
        .history-header { 
            font-size: 14px; color: #888; margin-bottom: 10px; 
            display: flex; justify-content: space-between; align-items: center;
        }
        .clear-btn { color: #ff3b30; cursor: pointer; font-size: 12px; }
        .history-list { list-style: none; padding: 0; margin: 0; }
        .history-item {
            background: #fff; padding: 12px; margin-bottom: 8px; border-radius: 8px;
            border: 1px solid #e5e5ea; cursor: pointer;
            display: flex; align-items: center; justify-content: space-between;
            transition: background 0.1s;
        }
        .history-item:active { background: #f0f0f0; }
        .history-text { 
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; 
            max-width: 85%; font-size: 14px;
        }
        .history-arrow { color: #c7c7cc; font-size: 18px; }
        .advanced-toggle {
            margin-top: 15px;
            font-size: 14px;
            color: #007AFF;
            cursor: pointer;
            text-decoration: underline;
        }
        .advanced-panel {
            margin-top: 15px;
            padding: 15px;
            background: #fff;
            border-radius: 12px;
            border: 1px solid #e5e5ea;
            display: none;
            text-align: left;
        }
        .advanced-panel.show {
            display: block;
        }
        .config-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .config-item:last-child {
            border-bottom: none;
        }
        .config-label {
            font-size: 14px;
            color: #333;
            flex: 1;
        }
        input[type="text"].large-input {
            padding: 20px;
            font-size: 18px;
            min-height: 60px;
        }
        textarea.large-input {
            width: 100%;
            padding: 20px;
            font-size: 18px;
            border-radius: 12px;
            border: 1px solid #d1d1d6;
            box-sizing: border-box;
            outline: none;
            background: #fff;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            transition: border-color 0.2s;
            resize: vertical;
            min-height: 100px;
            font-family: inherit;
        }
        textarea.large-input:focus { border-color: #007AFF; }
        button#enterBtn {
            background-color: #34c759;
            box-shadow: 0 4px 6px rgba(52,199,89,0.2);
        }
        button#enterBtn:active { background-color: #28a745; transform: scale(0.98); }
        button#backspaceBtn {
            background-color: #ff9500;
            box-shadow: 0 4px 6px rgba(255,149,0,0.2);
        }
        button#backspaceBtn:active { background-color: #e68900; transform: scale(0.98); }
        button#undoBtn {
            background-color: #5856d6;
            box-shadow: 0 4px 6px rgba(88,86,214,0.2);
        }
        button#undoBtn:active { background-color: #4846b6; transform: scale(0.98); }
    </style>
</head>
<body>
    <h2 id="titleHeader">电脑远程输入板</h2>
    <div class="last-sent-label" id="lastSentLabel" style="display: none;"></div>
    <div class="input-group">
        <textarea id="textInput" placeholder="输入文字..." autofocus></textarea>
    </div>
    <div class="button-group" id="buttonGroup">
        <button id="sendBtn" onclick="handleSend()">Send</button>
    </div>
    <div id="status"></div>
    <div class="advanced-toggle" onclick="toggleAdvanced()">⚙️ 高级选项</div>
    <div class="advanced-panel" id="advancedPanel">
        <div class="config-item">
            <span class="config-label">自动发送</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configAutoSend">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">清空两端空白</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configTrim">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">展示历史记录</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configShowHistory">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">使用较大的文本输入框</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configLargeInput">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">提供 Enter 按钮发送 Enter 信号</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configEnterButton">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">提供 Backspace 按钮发送删除信号</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configBackspaceButton">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">提供 Undo 按钮发送撤销信号 (Ctrl+Z)</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configUndoButton">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">发送前在末尾追加空格</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configAppendSpace">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">实验性: 输入时自动静音系统</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configAutoMute">
                <span class="switch-slider"></span>
            </label>
        </div>
        <div class="config-item">
            <span class="config-label">显示上次发送的文本</span>
            <label class="switch-container">
                <input type="checkbox" class="switch-input" id="configShowLastSent">
                <span class="switch-slider"></span>
            </label>
        </div>
    </div>
    <div class="history-container" id="historyContainer">
        <div class="history-header">
            <span>最近记录 (点击重发)</span>
            <span class="clear-btn" onclick="clearHistory()">清空</span>
        </div>
        <ul id="historyList" class="history-list"></ul>
    </div>
    <script>
        const status = document.getElementById('status');
        const historyList = document.getElementById('historyList');
        const historyContainer = document.getElementById('historyContainer');
        const buttonGroup = document.getElementById('buttonGroup');
        const lastSentLabel = document.getElementById('lastSentLabel');
        const titleHeader = document.getElementById('titleHeader');
        const MAX_HISTORY = 10;
        let isSending = false;
        let inputElement = document.getElementById('textInput');

        // IME composition state (voice input with underline)
        let isComposing = false;

        // 配置项
        const config = {
            autoSend: true,
            trim: true,
            showHistory: false,
            largeInput: true,
            enterButton: false,
            backspaceButton: false,
            undoButton: true,
            appendSpace: true,
            autoMute: false,
            showLastSent: false
        };

        // 从localStorage加载配置
        function loadConfig() {
            const saved = localStorage.getItem('airtypeConfig');
            if (saved) {
                Object.assign(config, JSON.parse(saved));
            }
            applyConfig();
        }

        // 保存配置到localStorage
        function saveConfig() {
            localStorage.setItem('airtypeConfig', JSON.stringify(config));
        }

        // 应用配置
        function applyConfig() {
            // 更新开关状态
            document.getElementById('configAutoSend').checked = config.autoSend;
            document.getElementById('configTrim').checked = config.trim;
            document.getElementById('configShowHistory').checked = config.showHistory;
            document.getElementById('configLargeInput').checked = config.largeInput;
            document.getElementById('configEnterButton').checked = config.enterButton;
            document.getElementById('configBackspaceButton').checked = config.backspaceButton;
            document.getElementById('configUndoButton').checked = config.undoButton;
            document.getElementById('configAppendSpace').checked = config.appendSpace;
            document.getElementById('configAutoMute').checked = config.autoMute;
            document.getElementById('configShowLastSent').checked = config.showLastSent;

            // 应用发送按钮显示/隐藏（自动发送开启时隐藏）
            const sendBtn = document.getElementById('sendBtn');
            sendBtn.style.display = config.autoSend ? 'none' : 'flex';

            // 应用历史记录显示/隐藏
            historyContainer.style.display = config.showHistory ? 'block' : 'none';

            // 应用显示上次发送文本的配置
            if (titleHeader) {
                titleHeader.style.display = config.showLastSent ? 'none' : 'block';
            }
            if (lastSentLabel && !config.showLastSent) {
                lastSentLabel.style.display = 'none';
            }

            // 应用大输入框
            if (config.largeInput) {
                if (inputElement.tagName === 'INPUT') {
                    const textarea = document.createElement('textarea');
                    textarea.id = 'textInput';
                    textarea.className = 'large-input';
                    textarea.placeholder = '输入文字...';
                    textarea.autofocus = true;
                    textarea.value = inputElement.value;
                    inputElement.parentNode.replaceChild(textarea, inputElement);
                    inputElement = textarea;
                    setupInputEvents();
                }
            } else {
                if (inputElement.tagName === 'TEXTAREA') {
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.id = 'textInput';
                    input.placeholder = '输入文字...';
                    input.autofocus = true;
                    input.value = inputElement.value;
                    inputElement.parentNode.replaceChild(input, inputElement);
                    inputElement = input;
                    setupInputEvents();
                }
            }

            // 应用Enter按钮
            const existingEnterBtn = document.getElementById('enterBtn');
            if (config.enterButton) {
                if (!existingEnterBtn) {
                    const enterBtn = document.createElement('button');
                    enterBtn.id = 'enterBtn';
                    enterBtn.textContent = 'Enter';
                    // 在按钮按下时处理点击并保持焦点，防止输入法闪烁
                    enterBtn.onmousedown = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendEnter(e);
                    };
                    enterBtn.ontouchstart = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendEnter(e);
                    };
                    buttonGroup.appendChild(enterBtn);
                } else {
                    // 如果按钮已存在，确保事件处理器正确设置
                    existingEnterBtn.onmousedown = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendEnter(e);
                    };
                    existingEnterBtn.ontouchstart = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendEnter(e);
                    };
                }
            } else {
                if (existingEnterBtn) {
                    existingEnterBtn.remove();
                }
            }

            // 应用Backspace按钮
            const existingBackspaceBtn = document.getElementById('backspaceBtn');
            if (config.backspaceButton) {
                if (!existingBackspaceBtn) {
                    const backspaceBtn = document.createElement('button');
                    backspaceBtn.id = 'backspaceBtn';
                    backspaceBtn.textContent = 'Backspace';
                    // 在按钮按下时处理点击并保持焦点，防止输入法闪烁
                    backspaceBtn.onmousedown = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendBackspace(e);
                    };
                    backspaceBtn.ontouchstart = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendBackspace(e);
                    };
                    buttonGroup.appendChild(backspaceBtn);
                } else {
                    // 如果按钮已存在，确保事件处理器正确设置
                    existingBackspaceBtn.onmousedown = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendBackspace(e);
                    };
                    existingBackspaceBtn.ontouchstart = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendBackspace(e);
                    };
                }
            } else {
                if (existingBackspaceBtn) {
                    existingBackspaceBtn.remove();
                }
            }

            // 应用Undo按钮
            const existingUndoBtn = document.getElementById('undoBtn');
            if (config.undoButton) {
                if (!existingUndoBtn) {
                    const undoBtn = document.createElement('button');
                    undoBtn.id = 'undoBtn';
                    undoBtn.textContent = 'Undo';
                    // 在按钮按下时处理点击并保持焦点，防止输入法闪烁
                    undoBtn.onmousedown = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendUndo(e);
                    };
                    undoBtn.ontouchstart = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendUndo(e);
                    };
                    buttonGroup.appendChild(undoBtn);
                } else {
                    // 如果按钮已存在，确保事件处理器正确设置
                    existingUndoBtn.onmousedown = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendUndo(e);
                    };
                    existingUndoBtn.ontouchstart = function(e) {
                        e.preventDefault();
                        inputElement.focus();
                        handleSendUndo(e);
                    };
                }
            } else {
                if (existingUndoBtn) {
                    existingUndoBtn.remove();
                }
            }

            if (config.showHistory) {
                renderHistory();
            }
        }

        // 设置输入框事件
        function setupInputEvents() {
            // 移除旧的事件监听器（通过重新绑定）
            inputElement.removeEventListener('input', handleInput);
            inputElement.removeEventListener('keydown', handleKeydown);
            inputElement.removeEventListener('compositionstart', handleCompositionStart);
            inputElement.removeEventListener('compositionend', handleCompositionEnd);
            
            // 添加新的事件监听器
            inputElement.addEventListener('input', handleInput);
            inputElement.addEventListener('keydown', handleKeydown);
            
            // Add IME composition event listeners
            inputElement.addEventListener('compositionstart', handleCompositionStart);
            inputElement.addEventListener('compositionend', handleCompositionEnd);
        }
        
        // IME composition event handlers
        function handleCompositionStart(event) {
            isComposing = true;
            console.log('IME composition started - voice input in progress');
        }
        
        function handleCompositionEnd(event) {
            isComposing = false;
            console.log('IME composition ended - final text:', event.data);
            
            // Immediately send the text after composition ends
            if (config.autoSend) {
                setTimeout(function() {
                    if (!isComposing && !isSending) {
                        handleSend();
                    }
                }, 50);
            }
        }

        // 切换高级选项面板
        function toggleAdvanced() {
            const panel = document.getElementById('advancedPanel');
            panel.classList.toggle('show');
        }

        // 配置项变更处理
        document.getElementById('configAutoSend').addEventListener('change', function() {
            config.autoSend = this.checked;
            saveConfig();
            // 自动发送状态改变时，更新发送按钮显示
            const sendBtn = document.getElementById('sendBtn');
            sendBtn.style.display = config.autoSend ? 'none' : 'flex';
        });

        document.getElementById('configTrim').addEventListener('change', function() {
            config.trim = this.checked;
            saveConfig();
        });

        document.getElementById('configShowHistory').addEventListener('change', function() {
            config.showHistory = this.checked;
            saveConfig();
            applyConfig();
        });

        document.getElementById('configLargeInput').addEventListener('change', function() {
            config.largeInput = this.checked;
            saveConfig();
            applyConfig();
        });

        document.getElementById('configEnterButton').addEventListener('change', function() {
            config.enterButton = this.checked;
            saveConfig();
            applyConfig();
        });

        document.getElementById('configBackspaceButton').addEventListener('change', function() {
            config.backspaceButton = this.checked;
            saveConfig();
            applyConfig();
        });

        document.getElementById('configUndoButton').addEventListener('change', function() {
            config.undoButton = this.checked;
            saveConfig();
            applyConfig();
        });

        document.getElementById('configAppendSpace').addEventListener('change', function() {
            config.appendSpace = this.checked;
            saveConfig();
        });

        document.getElementById('configAutoMute').addEventListener('change', function() {
            config.autoMute = this.checked;
            saveConfig();
            // 通知服务器端更新静音状态
            fetch('/mute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: this.checked })
            });
        });

        document.getElementById('configShowLastSent').addEventListener('change', function() {
            config.showLastSent = this.checked;
            saveConfig();
            applyConfig();
        });

        // 输入事件处理
        let isFirstInput = true;  // 标记是否是首次输入
        let muteRequested = false; // 标记是否已请求静音
        
        function handleInput(event) {
            // Key: If IME composition is in progress (voice input with underline), skip sending
            if (isComposing) {
                console.log('Skipping send - IME composition in progress');
                return;
            }
            
            // 如果启用了自动静音且是首次输入，立即请求静音
            if (config.autoMute && isFirstInput && !muteRequested) {
                isFirstInput = false;
                muteRequested = true;
                fetch('/mute_immediate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mute: true })
                }).catch(err => console.error('Failed to mute:', err));
            }
            
            // Non-composition input: do nothing (wait for compositionend)
            // This prevents sending during manual typing
        }

        // 按键事件处理
        function handleKeydown(event) {
            if (event.key === "Enter") {
                // Shift+Enter 始终允许换行
                if (event.shiftKey) {
                    return; // 允许默认行为（换行）
                }
                
                // 检查文本框内容是否为空
                const text = inputElement.value.trim();
                if (text.length === 0) {
                    // 文本框为空时，发送 Enter 事件
                    event.preventDefault();
                    handleSendEnter();
                }
                // 文本框不为空时，允许默认行为（换行），不阻止事件
            }
        }

        // 发送Enter键
        function handleSendEnter(event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            if (isSending) return;
            isSending = true;
            status.innerText = "发送中...";
            status.style.color = "#888";
            fetch('/type', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: '', enter: true })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    status.innerText = "✓ 已发送 Enter";
                    status.style.color = "#34c759";
                    setTimeout(() => status.innerText = "", 1500);
                } else { throw new Error("Server error"); }
            })
            .catch(err => {
                status.innerText = "✕ 发送失败";
                status.style.color = "#ff3b30";
            })
            .finally(() => {
                isSending = false;
            });
        }

        // 发送Backspace键
        function handleSendBackspace(event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            if (isSending) return;
            isSending = true;
            status.innerText = "发送中...";
            status.style.color = "#888";
            fetch('/type', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: '', backspace: true })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    status.innerText = "✓ 已发送 Backspace";
                    status.style.color = "#34c759";
                    setTimeout(() => status.innerText = "", 1500);
                } else { throw new Error("Server error"); }
            })
            .catch(err => {
                status.innerText = "✕ 发送失败";
                status.style.color = "#ff3b30";
            })
            .finally(() => {
                isSending = false;
            });
        }

        // 发送Undo键 (Ctrl+Z)
        function handleSendUndo(event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            if (isSending) return;
            isSending = true;
            status.innerText = "发送中...";
            status.style.color = "#888";
            fetch('/type', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: '', undo: true })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    status.innerText = "✓ 已发送 Undo";
                    status.style.color = "#34c759";
                    setTimeout(() => status.innerText = "", 1500);
                } else { throw new Error("Server error"); }
            })
            .catch(err => {
                status.innerText = "✕ 发送失败";
                status.style.color = "#ff3b30";
            })
            .finally(() => {
                isSending = false;
            });
        }

        window.onload = function() { 
            loadConfig();
            setupInputEvents();
            // 同步自动静音状态到服务器
            fetch('/mute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: config.autoMute })
            });
        }

        // 点击页面任意位置聚焦输入框（除了按钮和历史记录）
        document.body.addEventListener('click', function(event) {
            const target = event.target;
            // 如果点击的不是按钮、历史记录项、清空按钮、高级选项面板，则聚焦输入框
            if (!target.closest('button') &&
                !target.closest('.history-item') &&
                !target.closest('.clear-btn') &&
                !target.closest('.advanced-panel') &&
                !target.closest('.advanced-toggle') &&
                target !== inputElement) {
                inputElement.focus();
            }
        });
        function handleSend() {
            let text = config.trim ? inputElement.value.trim() : inputElement.value;
            if (text.length === 0 || isSending) return;
            
            // 如果启用了追加空格，在末尾添加空格
            if (config.appendSpace) {
                text = text + ' ';
            }
            
            saveToHistory(text);
            sendRequest(text);
        }
        function handleClear() {
            inputElement.value = '';
            inputElement.focus();
        }
        function sendRequest(text) {
            if (isSending) return;
            isSending = true;
            status.innerText = "发送中...";
            status.style.color = "#888";
            
            fetch('/type', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    status.innerText = "✓ 已发送";
                    status.style.color = "#34c759";
                    
                    // 更新最后发送的文本标签（仅在配置开启时显示）
                    if (lastSentLabel && config.showLastSent) {
                        lastSentLabel.textContent = text;
                        lastSentLabel.style.display = 'flex';
                    }
                    
                    // Clear input immediately after sending
                    inputElement.value = '';
                    inputElement.focus();
                    
                    // 发送完成后，如果启用了自动静音，恢复音量
                    if (config.autoMute && muteRequested) {
                        muteRequested = false;
                        isFirstInput = true;
                        fetch('/mute_immediate', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ mute: false })
                        }).catch(err => console.error('Failed to unmute:', err));
                    }
                    
                    setTimeout(() => status.innerText = "", 1500);
                } else { throw new Error("Server error"); }
            })
            .catch(err => {
                status.innerText = "✕ 发送失败";
                status.style.color = "#ff3b30";
                // 发送失败也要恢复音量
                if (config.autoMute && muteRequested) {
                    muteRequested = false;
                    isFirstInput = true;
                    fetch('/mute_immediate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mute: false })
                    }).catch(err => console.error('Failed to unmute:', err));
                }
            })
            .finally(() => {
                isSending = false;
            });
        }
        function getHistory() {
            const stored = localStorage.getItem('typeHistory');
            return stored ? JSON.parse(stored) : [];
        }
        function saveToHistory(text) {
            let history = getHistory();
            history = history.filter(item => item !== text);
            history.unshift(text);
            if (history.length > MAX_HISTORY) { history = history.slice(0, MAX_HISTORY); }
            localStorage.setItem('typeHistory', JSON.stringify(history));
            renderHistory();
        }
        function renderHistory() {
            if (!config.showHistory) return;
            const history = getHistory();
            historyList.innerHTML = '';
            history.forEach(text => {
                const li = document.createElement('li');
                li.className = 'history-item';
                li.onclick = () => { 
                    inputElement.value = text; 
                    handleSend(); 
                };
                li.innerHTML = `<span class="history-text">${escapeHtml(text)}</span><span class="history-arrow">⤶</span>`;
                historyList.appendChild(li);
            });
        }
        function clearHistory() { localStorage.removeItem('typeHistory'); renderHistory(); }
        function escapeHtml(text) {
            const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
            return text.replace(/[&<>"']/g, function(m) { return map[m]; });
        }

        // Keyboard detection and keep-alive logic
        (function () {
            const KeyboardState = {
                visible: false,
                height: 0,
            };

            let baseHeight = null;
            let isInputFocused = false;

            function getViewportHeight() {
                return window.visualViewport ? window.visualViewport.height : window.innerHeight;
            }

            function ensureBaseHeight() {
                if (baseHeight == null) {
                    baseHeight = getViewportHeight();
                }
            }

            // Listen for input focus state
            document.addEventListener('focusin', (e) => {
                if (e.target.matches('input, textarea, [contenteditable="true"]')) {
                    isInputFocused = true;
                    ensureBaseHeight();
                }
            });

            document.addEventListener('focusout', (e) => {
                if (e.target.matches('input, textarea, [contenteditable="true"]')) {
                    isInputFocused = false;
                }
            });

            // Listen for viewport height changes to infer keyboard state
            function updateKeyboardState() {
                ensureBaseHeight();

                const vh = getViewportHeight();
                const delta = baseHeight - vh;

                // Consider keyboard visible if delta exceeds threshold (adjust per device)
                const maybeVisible = delta > 100;

                KeyboardState.visible = isInputFocused && maybeVisible;
                KeyboardState.height = KeyboardState.visible ? delta : 0;
            }

            if (window.visualViewport) {
                window.visualViewport.addEventListener('resize', updateKeyboardState);
            } else {
                window.addEventListener('resize', updateKeyboardState);
            }

            window.addEventListener('load', ensureBaseHeight);

            // Expose API
            window.Keyboard = {
                /**
                 * Check if keyboard is visible
                 */
                isVisible() {
                    return KeyboardState.visible;
                },

                /**
                 * Force show keyboard and focus on input element
                 * @param {HTMLElement} input
                 */
                showFor(input) {
                    if (!input) return;

                    // If already visible, ensure cursor position is correct
                    if (KeyboardState.visible) {
                        if (document.activeElement !== input) {
                            input.focus();
                        }
                        try {
                            if (typeof input.setSelectionRange === 'function') {
                                const len = input.value.length;
                                input.setSelectionRange(len, len);
                            }
                        } catch (e) {}
                        return;
                    }

                    // Not visible yet: blur then focus to force refresh input context
                    if (document.activeElement === input) {
                        input.blur();
                    }

                    setTimeout(() => {
                        input.focus();

                        try {
                            if (typeof input.setSelectionRange === 'function') {
                                const len = input.value.length;
                                input.setSelectionRange(len, len);
                            }
                        } catch (e) {}
                    }, 10);
                },
            };

            console.log('Keyboard API ready:', window.Keyboard);

            // Keep keyboard visible: check every 2 seconds
            setInterval(function() {
                // Check if advanced panel is open, if so, skip keyboard check
                const advancedPanel = document.getElementById('advancedPanel');
                if (advancedPanel && advancedPanel.classList.contains('show')) {
                    return; // Panel is open, disable keyboard auto-show
                }
                
                if (!Keyboard.isVisible()) {
                    // Keyboard not visible, show it
                    window.Keyboard.showFor(inputElement);
                }
            }, 1000);
        })();
    </script>
</body>
</html>
"""

IS_MAC = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'
PASTE_KEY = 'command' if IS_MAC else 'ctrl'

# Windows API 常量
if IS_WINDOWS:
    VK_SHIFT = 0x10
    VK_INSERT = 0x2D
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0

# 系统音量控制相关
auto_mute_enabled = False  # 默认关闭自动静音功能
original_mute_state = False  # 记录原始静音状态
current_muted_by_app = False  # 记录当前是否由应用控制静音

# 粘贴和剪贴板配置
use_ctrl_v = False  # False: 使用 Shift+Insert, True: 使用 Ctrl+V
preserve_clipboard = False  # 是否保护剪贴板（不覆盖）
auto_minimize = False  # 启动后自动最小化


# --- 剪贴板操作包装函数（支持 clipman 避免触发 Ditto 等工具）---
def clipboard_get():
    """获取剪贴板内容（优先使用 clipman 避免触发 Ditto）"""
    if CLIPMAN_AVAILABLE:
        try:
            clipman.init()
            return clipman.get()
        except Exception as e:
            print(f"clipman.get() failed: {e}, falling back to pyperclip")
    # 回退到 pyperclip
    return pyperclip.paste()


def clipboard_set(text):
    """设置剪贴板内容（优先使用 clipman 避免触发 Ditto）"""
    if CLIPMAN_AVAILABLE:
        try:
            clipman.init()
            clipman.set(text)
            return
        except Exception as e:
            print(f"clipman.set() failed: {e}, falling back to pyperclip")
    # 回退到 pyperclip
    pyperclip.copy(text)

def set_system_mute_windows(mute: bool) -> bool:
    """控制 Windows 系统音量静音状态（不显示音量条）"""
    if not IS_WINDOWS:
        return False
    
    try:
        # 使用 pycaw 的正确方式：直接访问 EndpointVolume 属性
        from pycaw.pycaw import AudioUtilities
        
        # 获取音频设备
        speakers = AudioUtilities.GetSpeakers()
        
        # 正确的方式：直接访问 EndpointVolume 属性
        volume = speakers.EndpointVolume
        
        # 设置静音状态（不会显示音量条）
        volume.SetMute(1 if mute else 0, None)
        print(f"[pycaw] {'静音' if mute else '取消静音'}成功（无OSD）")
        
        return True
        
    except ImportError as e:
        print(f"Warning: pycaw 未安装: {e}")
        print("请运行: pip install pycaw comtypes")
        return False
    
    except Exception as e:
        print(f"pycaw 静音失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 使用备用方案（会显示音量条）
        print(f"使用备用方案（会显示音量条）...")
        try:
            user32 = ctypes.windll.user32
            VK_VOLUME_MUTE = 0xAD
            
            global current_muted_by_app
            
            # 只在需要切换时才按键
            if (mute and not current_muted_by_app) or (not mute and current_muted_by_app):
                user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
                time.sleep(0.02)
                user32.keybd_event(VK_VOLUME_MUTE, 0, 0x0002, 0)
                print(f"[备用] {'静音' if mute else '取消静音'}（会显示OSD）")
                return True
            
            return True
                
        except Exception as e2:
            print(f"备用方案也失败: {e2}")
            return False


def ensure_insert_mode_reset():
    """确保不在覆盖模式（检查并重置 Insert 状态）"""
    if not IS_WINDOWS:
        return
    
    try:
        user32 = ctypes.windll.user32
        insert_state = user32.GetKeyState(VK_INSERT)
        
        # 低位为1表示覆盖模式被激活
        if insert_state & 0x0001:
            insert_scan = user32.MapVirtualKeyW(VK_INSERT, MAPVK_VK_TO_VSC)
            # 按一次 Insert 切换回插入模式
            user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.01)
            user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            print("Detected overwrite mode, reset to insert mode")
    except Exception as e:
        print(f"Check Insert state failed: {e}")


def send_shift_insert_windows():
    """使用 Windows API 发送 Shift+Insert 组合键（使用扫描码，兼容终端）"""
    if not IS_WINDOWS:
        return False

    user32 = None
    shift_scan = None
    insert_scan = None
    shift_pressed = False
    insert_pressed = False

    try:
        user32 = ctypes.windll.user32

        # 获取扫描码（对于终端应用如 CMD/PowerShell 必须使用扫描码）
        shift_scan = user32.MapVirtualKeyW(VK_SHIFT, MAPVK_VK_TO_VSC)
        insert_scan = user32.MapVirtualKeyW(VK_INSERT, MAPVK_VK_TO_VSC)

        # 按下 Shift（使用扫描码）
        user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE, 0)
        shift_pressed = True
        time.sleep(0.05)

        # 按下 Insert（使用扫描码 + 扩展键标志）
        user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY, 0)
        insert_pressed = True
        time.sleep(0.02)

        # 释放 Insert（使用扫描码 + 扩展键标志）
        user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        insert_pressed = False
        time.sleep(0.02)

        # 释放 Shift（使用扫描码）
        user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        shift_pressed = False

        return True
        
    except Exception as e:
        print(f"Windows API error: {e}")
        return False
        
    finally:
        # 使用 finally 确保清理一定执行
        if user32 and shift_scan is not None and insert_scan is not None:
            try:
                # 强制释放所有可能按下的键
                if insert_pressed:
                    user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
                if shift_pressed:
                    user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
            except Exception as cleanup_error:
                print(f"Error during key cleanup: {cleanup_error}")


def send_ctrl_v_windows():
    """使用 Windows API 发送 Ctrl+V 组合键"""
    if not IS_WINDOWS:
        return False

    try:
        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11
        VK_V = 0x56
        
        ctrl_scan = user32.MapVirtualKeyW(VK_CONTROL, MAPVK_VK_TO_VSC)
        v_scan = user32.MapVirtualKeyW(VK_V, MAPVK_VK_TO_VSC)
        
        # 按下 Ctrl
        user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.05)
        
        # 按下 V
        user32.keybd_event(VK_V, v_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.02)
        
        # 释放 V
        user32.keybd_event(VK_V, v_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)
        
        # 释放 Ctrl
        user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        
        return True
    except Exception as e:
        print(f"Ctrl+V error: {e}")
        return False


def paste_text(text):
    """复制到剪切板并粘贴"""
    global use_ctrl_v, preserve_clipboard
    
    # 如果启用剪贴板保护，保存原内容
    clipboard_saved = False
    original_clipboard = None
    if preserve_clipboard:
        try:
            original_clipboard = clipboard_get()
            clipboard_saved = True
            print(f"[Clipboard] Saved original content (length: {len(original_clipboard) if original_clipboard else 0})")
        except Exception as e:
            print(f"[Clipboard] Failed to save: {e}")
    
    # 复制文本到剪贴板
    clipboard_set(text)
    time.sleep(0.1)
    
    # 根据配置选择粘贴方式
    if IS_WINDOWS:
        if use_ctrl_v:
            # 使用 Ctrl+V 粘贴
            send_ctrl_v_windows()
        else:
            # 使用 Shift+Insert 粘贴
            send_shift_insert_windows()
            # 检查并重置 Insert 状态
            ensure_insert_mode_reset()
    else:
        # Mac/Linux
        if use_ctrl_v:
            pyautogui.hotkey('ctrl', 'v')
        else:
            pyautogui.hotkey('shift', 'insert')
    
    # 如果启用剪贴板保护，恢复原内容（增加等待时间）
    if preserve_clipboard and clipboard_saved:
        time.sleep(0.15)  # 增加等待时间到 150ms，确保粘贴操作完成
        try:
            if original_clipboard is not None:
                clipboard_set(original_clipboard)
            else:
                # 如果原内容是 None，清空剪贴板
                clipboard_set('')
            print(f"[Clipboard] Restored original content")
        except Exception as e:
            print(f"[Clipboard] Failed to restore: {e}")


# --- CF 模式：cfchat 加密协议 ---
def derive_key_and_room(password: str) -> tuple:
    """从密码派生 AES 密钥和房间 ID"""
    password = password.strip() or 'noset'
    encoded = password.encode('utf-8')
    hash_bytes = hashlib.sha256(encoded).digest()
    room_id = hash_bytes.hex()
    return hash_bytes, room_id


def decrypt_message(key: bytes, iv_b64: str, data_b64: str) -> str:
    """AES-GCM 解密消息"""
    import base64
    iv = base64.b64decode(iv_b64)
    data = base64.b64decode(data_b64)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, data, None)
    return plaintext.decode('utf-8')


class CFChatClient:
    """CF 模式 WebSocket 客户端"""
    def __init__(self, worker_url: str, password: str, on_message=None, on_status=None):
        self.worker_url = worker_url.rstrip('/')
        self.password = password
        self.on_message = on_message
        self.on_status = on_status
        self.key, self.room_id = derive_key_and_room(password)
        self.ws = None
        self.running = False
        self._loop = None
        self._thread = None

    def _get_ws_url(self) -> str:
        """构建 WebSocket URL"""
        url = self.worker_url
        if url.startswith('https://'):
            url = 'wss://' + url[8:]
        elif url.startswith('http://'):
            url = 'ws://' + url[7:]
        elif not url.startswith('ws'):
            url = 'wss://' + url
        return f"{url}/ws/{self.room_id}"

    async def _connect(self):
        """连接并监听消息"""
        ws_url = self._get_ws_url()
        if self.on_status:
            self.on_status('connecting', '连接中...')

        try:
            async with websockets.connect(ws_url) as ws:
                self.ws = ws
                if self.on_status:
                    self.on_status('connected', '已连接 CF')

                while self.running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        self._handle_message(raw)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break

        except Exception as e:
            if self.on_status:
                self.on_status('error', f'连接失败: {e}')

        finally:
            self.ws = None
            if self.on_status and self.running:
                self.on_status('disconnected', '已断开，重连中...')

    def _handle_message(self, raw: str):
        """处理收到的消息"""
        try:
            payload = json.loads(raw)
            msg_type = payload.get('type', 'text').lower()

            if msg_type != 'text':
                return

            iv = payload.get('iv')
            data = payload.get('data')
            if not iv or not data:
                return

            text = decrypt_message(self.key, iv, data)
            if self.on_message:
                self.on_message(text)

        except Exception as e:
            print(f"消息处理错误: {e}")

    def _run_loop(self):
        """在独立线程运行事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        while self.running:
            try:
                self._loop.run_until_complete(self._connect())
            except Exception as e:
                print(f"连接错误: {e}")

            if self.running:
                time.sleep(2)

        self._loop.close()

    def start(self):
        """启动客户端"""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止客户端"""
        self.running = False
        if self.ws and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self.ws.close(), self._loop)
            except:
                pass


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/mute', methods=['POST'])
def toggle_mute():
    """切换自动静音功能"""
    global auto_mute_enabled
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        auto_mute_enabled = enabled
        return {'success': True, 'enabled': auto_mute_enabled}
    except Exception as e:
        print(f"Error in toggle_mute: {e}")
        return {'success': False}

@app.route('/mute_immediate', methods=['POST'])
def mute_immediate():
    """立即静音或取消静音（用于语音输入时）"""
    global current_muted_by_app
    
    try:
        data = request.get_json()
        mute = data.get('mute', False)
        
        if IS_WINDOWS:
            if mute:
                # 如果当前未被应用静音，则切换到静音
                if not current_muted_by_app:
                    success = set_system_mute_windows(True)
                    if success:
                        current_muted_by_app = True
                    print(f"🔇 语音输入开始，切换到静音: {success}")
                else:
                    success = True
                    print("已经处于静音状态")
            else:
                # 如果当前被应用静音，则切换回来
                if current_muted_by_app:
                    success = set_system_mute_windows(False)
                    if success:
                        current_muted_by_app = False
                    print(f"🔊 语音输入结束，切换回音量: {success}")
                else:
                    success = True
                    print("未处于应用静音状态，无需恢复")
            
            return {'success': success}
        else:
            return {'success': False, 'message': 'Only supported on Windows'}
    except Exception as e:
        print(f"Error in mute_immediate: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

@app.route('/type', methods=['POST'])
def type_text():
    try:
        data = request.get_json()
        enter = data.get('enter', False)
        backspace = data.get('backspace', False)
        undo = data.get('undo', False)
        
        # 如果只是发送Undo键 (Ctrl+Z)
        if undo:
            if IS_WINDOWS:
                # Windows: 使用 Windows API 发送 Ctrl+Z
                try:
                    user32 = ctypes.windll.user32
                    VK_CONTROL = 0x11
                    VK_Z = 0x5A
                    ctrl_scan = user32.MapVirtualKeyW(VK_CONTROL, MAPVK_VK_TO_VSC)
                    z_scan = user32.MapVirtualKeyW(VK_Z, MAPVK_VK_TO_VSC)
                    
                    # 按下 Ctrl
                    user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE, 0)
                    time.sleep(0.02)
                    # 按下 Z
                    user32.keybd_event(VK_Z, z_scan, KEYEVENTF_SCANCODE, 0)
                    time.sleep(0.02)
                    # 释放 Z
                    user32.keybd_event(VK_Z, z_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
                    # 释放 Ctrl
                    user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                except Exception as e:
                    print(f"Windows API error for Ctrl+Z: {e}")
                    pyautogui.hotkey('ctrl', 'z')
            else:
                # Mac/Linux: 使用 pyautogui
                pyautogui.hotkey('ctrl', 'z')
            
            return {'success': True}
        
        # 如果只是发送Enter键
        if enter:
            if IS_WINDOWS:
                # Windows: 使用 Windows API 发送 Enter 键
                try:
                    user32 = ctypes.windll.user32
                    VK_RETURN = 0x0D
                    return_scan = user32.MapVirtualKeyW(VK_RETURN, MAPVK_VK_TO_VSC)
                    # 按下 Enter
                    user32.keybd_event(VK_RETURN, return_scan, KEYEVENTF_SCANCODE, 0)
                    time.sleep(0.02)
                    # 释放 Enter
                    user32.keybd_event(VK_RETURN, return_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                except Exception as e:
                    print(f"Windows API error for Enter: {e}")
                    pyautogui.press('enter')
            else:
                # Mac/Linux: 使用 pyautogui
                pyautogui.press('enter')
            
            return {'success': True}
        
        # 如果只是发送Backspace键
        if backspace:
            if IS_WINDOWS:
                # Windows: 使用 Windows API 发送 Backspace 键
                try:
                    user32 = ctypes.windll.user32
                    VK_BACK = 0x08
                    backspace_scan = user32.MapVirtualKeyW(VK_BACK, MAPVK_VK_TO_VSC)
                    # 按下 Backspace
                    user32.keybd_event(VK_BACK, backspace_scan, KEYEVENTF_SCANCODE, 0)
                    time.sleep(0.02)
                    # 释放 Backspace
                    user32.keybd_event(VK_BACK, backspace_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                except Exception as e:
                    print(f"Windows API error for Backspace: {e}")
                    pyautogui.press('backspace')
            else:
                # Mac/Linux: 使用 pyautogui
                pyautogui.press('backspace')
            
            return {'success': True}
        
        # 发送文本
        text = data.get('text', '')
        if text:
            global use_ctrl_v, preserve_clipboard
            
            # 如果启用剪贴板保护，保存原内容
            clipboard_saved = False
            original_clipboard = None
            if preserve_clipboard:
                try:
                    original_clipboard = clipboard_get()
                    clipboard_saved = True
                    print(f"[Clipboard] Saved original content (length: {len(original_clipboard) if original_clipboard else 0})")
                except Exception as e:
                    print(f"[Clipboard] Failed to save: {e}")
            
            # 复制文本到剪贴板
            clipboard_set(text)
            time.sleep(0.1)

            # 根据配置选择粘贴方式
            if IS_WINDOWS:
                if use_ctrl_v:
                    # 使用 Ctrl+V 粘贴
                    success = send_ctrl_v_windows()
                else:
                    # 使用 Shift+Insert 粘贴（兼容终端）
                    success = send_shift_insert_windows()
                    # 检查并重置 Insert 状态（防止停留在覆盖模式）
                    ensure_insert_mode_reset()
                
                if not success:
                    print("Paste failed: Windows API call failed")
                    # 恢复剪贴板后返回错误
                    if preserve_clipboard and clipboard_saved:
                        try:
                            if original_clipboard is not None:
                                clipboard_set(original_clipboard)
                            else:
                                clipboard_set('')
                            print("[Clipboard] Restored after failure")
                        except:
                            pass
                    return {'success': False, 'error': 'Paste failed'}
            else:
                # Mac/Linux: 使用 pyautogui
                if use_ctrl_v:
                    pyautogui.hotkey('ctrl', 'v')
                else:
                    pyautogui.hotkey('shift', 'insert')
            
            # 如果启用剪贴板保护，恢复原内容（增加等待时间）
            if preserve_clipboard and clipboard_saved:
                time.sleep(0.15)  # 增加等待时间到 150ms，确保粘贴操作完成
                try:
                    if original_clipboard is not None:
                        clipboard_set(original_clipboard)
                    else:
                        # 如果原内容是 None，清空剪贴板
                        clipboard_set('')
                    print("[Clipboard] Restored original content")
                except Exception as e:
                    print(f"[Clipboard] Failed to restore: {e}")

            return {'success': True}
    except Exception as e:
        print(f"Error in type_text: {e}")
        pass
    return {'success': False}

def get_host_ip():
    """获取主要的本机 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_all_ips():
    """获取所有可用的本机 IP 地址"""
    ips = []
    try:
        # 获取主机名
        hostname = socket.gethostname()
        # 获取所有 IP 地址
        addrs = socket.getaddrinfo(hostname, None)
        for addr in addrs:
            ip = addr[4][0]
            # 只保留 IPv4 地址，排除回环地址
            if ':' not in ip and ip != '127.0.0.1':
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass

    # 如果没有找到任何 IP，添加默认值
    if not ips:
        ips.append('127.0.0.1')

    # IP 分类排序
    # 优先级：192.168.x.x > 10.x.x.x > 其他 > 虚拟网卡
    priority_192 = []  # 192.168.x.x (家庭/办公网络)
    priority_10 = []   # 10.x.x.x (企业网络)
    other_ips = []     # 其他真实 IP
    virtual_ips = []   # 虚拟网卡 IP

    for ip in ips:
        if ip.startswith('192.168.'):
            priority_192.append(ip)
        elif ip.startswith('10.'):
            priority_10.append(ip)
        elif ip.startswith('172.'):
            # 检查是否是虚拟网卡
            parts = ip.split('.')
            if len(parts) >= 2:
                second = int(parts[1])
                # Docker: 172.17.x.x, 172.18.x.x
                # Windows 虚拟网卡: 172.16.x.x
                # 私有网络范围: 172.16-31.x.x
                if 16 <= second <= 31:
                    virtual_ips.append(ip)
                else:
                    other_ips.append(ip)
        elif ip.startswith('198.18.'):
            # Clash 等代理工具虚拟网卡
            virtual_ips.append(ip)
        else:
            other_ips.append(ip)

    # 重新组合：优先级从高到低
    ips = priority_192 + priority_10 + other_ips + virtual_ips

    # 将主要 IP 移到对应分类的第一位（保持分类顺序）
    main_ip = get_host_ip()
    if main_ip in ips:
        ips.remove(main_ip)
        # 根据主要 IP 的类型，插入到对应分类的开头
        if main_ip.startswith('192.168.'):
            insert_pos = 0
        elif main_ip.startswith('10.'):
            insert_pos = len(priority_192)
        else:
            insert_pos = len(priority_192) + len(priority_10)
        ips.insert(insert_pos, main_ip)

    # 在最前面添加 0.0.0.0（监听所有网卡）
    ips.insert(0, '0.0.0.0 (所有网卡)')

    return ips

# --- GUI 主程序 ---
class ServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QAA AirType")
        # 增加高度以容纳配置选项和二维码
        self.root.geometry("512x720")
        self.root.resizable(True, True)
        self.root.minsize(380, 560)  # 最小尺寸

        # 绑定窗口关闭事件（正常退出）
        self.root.protocol('WM_DELETE_WINDOW', self.quit_app)

        # 设置窗口图标
        try:
            icon_path = get_icon_path()
            if icon_path:
                self.root.iconbitmap(icon_path)
        except Exception as e:
            pass

        # 系统托盘图标
        self.tray_icon = None
        self.create_tray_icon()

        # 居中屏幕
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 512) // 2
        y = (screen_height - 720) // 2
        self.root.geometry(f"512x720+{x}+{y}")

        self.all_ips = get_all_ips()
        self.ip_var = tk.StringVar(value=self.all_ips[0])
        self.is_running = False
        self.cf_client = None  # CF 模式客户端
        self.cf_mode = False   # 是否为 CF 模式

        # 加载配置
        self.config = load_config()
        saved_mode = self.config.get('mode', 'lan')  # lan 或 cf
        saved_port = self.config.get('port', '5000')
        saved_ip = self.config.get('ip', '')
        saved_cf_url = self.config.get('cf_url', '')
        saved_cf_key = self.config.get('cf_key', '')
        
        # 加载并应用粘贴和剪贴板配置到全局变量
        global use_ctrl_v, preserve_clipboard, auto_minimize
        use_ctrl_v = self.config.get('use_ctrl_v', False)
        preserve_clipboard = self.config.get('preserve_clipboard', False)
        auto_minimize = self.config.get('auto_minimize', False)

        # 在 IP 列表末尾添加 CF 模式选项
        self.all_ips.append('Cloudflare Chat Workers')

        # 主容器
        main_frame = tk.Frame(root, padx=20, pady=20)
        main_frame.pack(expand=True, fill='both')

        # 模式/IP 选择
        tk.Label(main_frame, text="连接模式:", font=("Arial", 10, "bold")).pack(anchor='w')
        self.ip_combo = ttk.Combobox(main_frame, textvariable=self.ip_var,
                                     values=self.all_ips, font=("Arial", 10), state='readonly')
        self.ip_combo.pack(fill='x', pady=(0, 10))
        self.ip_combo.bind('<<ComboboxSelected>>', self.on_mode_changed)

        # --- 局域网模式控件 ---
        self.lan_frame = tk.Frame(main_frame)
        self.lan_frame.pack(fill='x', pady=(0, 10))

        tk.Label(self.lan_frame, text="端口:", font=("Arial", 10, "bold")).pack(anchor='w')
        self.port_var = tk.StringVar(value=saved_port)
        self.port_entry = tk.Entry(self.lan_frame, textvariable=self.port_var, font=("Arial", 10))
        self.port_entry.pack(fill='x')

        # --- CF 模式控件 ---
        self.cf_frame = tk.Frame(main_frame)
        # 默认隐藏，选择 CF 模式时显示

        tk.Label(self.cf_frame, text="CF Worker 地址:", font=("Arial", 10, "bold")).pack(anchor='w')
        self.cf_url_var = tk.StringVar(value=saved_cf_url)
        self.cf_url_entry = tk.Entry(self.cf_frame, textvariable=self.cf_url_var, font=("Arial", 10))
        self.cf_url_entry.pack(fill='x', pady=(0, 10))

        tk.Label(self.cf_frame, text="共享密钥:", font=("Arial", 10, "bold")).pack(anchor='w')
        self.cf_key_var = tk.StringVar(value=saved_cf_key)
        self.cf_key_entry = tk.Entry(self.cf_frame, textvariable=self.cf_key_var, font=("Arial", 10), show="*")
        self.cf_key_entry.pack(fill='x')

        # 恢复保存的模式
        if saved_mode == 'cf':
            self.ip_var.set('Cloudflare Chat Workers')
            self.lan_frame.pack_forget()
            self.cf_frame.pack(fill='x', pady=(0, 10))
        elif saved_ip and saved_ip in self.all_ips:
            self.ip_var.set(saved_ip)

        # --- 配置选项框 ---
        config_frame = tk.LabelFrame(main_frame, text="配置选项", font=("Arial", 10, "bold"), padx=10, pady=10)
        config_frame.pack(fill='x', pady=(0, 10))

        # 粘贴模式选择
        self.use_ctrl_v_var = tk.BooleanVar(value=self.config.get('use_ctrl_v', False))
        cb_paste_mode = tk.Checkbutton(config_frame, text="使用 Ctrl+V 粘贴（关闭则用 Shift+Insert）",
                                       variable=self.use_ctrl_v_var,
                                       command=self.on_paste_mode_changed,
                                       font=("Arial", 9))
        cb_paste_mode.pack(anchor='w', pady=2)

        # 剪贴板保护
        self.preserve_clipboard_var = tk.BooleanVar(value=self.config.get('preserve_clipboard', False))
        cb_preserve = tk.Checkbutton(config_frame, text="保护剪贴板（输入时不覆盖剪贴板内容）",
                                     variable=self.preserve_clipboard_var,
                                     command=self.on_preserve_clipboard_changed,
                                     font=("Arial", 9))
        cb_preserve.pack(anchor='w', pady=2)

        # 自动最小化
        self.auto_minimize_var = tk.BooleanVar(value=self.config.get('auto_minimize', False))
        cb_auto_min = tk.Checkbutton(config_frame, text="启动后自动最小化窗口",
                                     variable=self.auto_minimize_var,
                                     command=self.on_auto_minimize_changed,
                                     font=("Arial", 9))
        cb_auto_min.pack(anchor='w', pady=2)

        # 按钮组
        self.button_frame = tk.Frame(main_frame)
        self.button_frame.pack(fill='x', pady=(0, 20))

        # 启动按钮
        self.btn_start = tk.Button(self.button_frame, text="启动服务", command=self.toggle_server,
                                   bg="#007AFF", fg="white", font=("Arial", 12, "bold"),
                                   relief="flat", pady=8, cursor="hand2")
        self.btn_start.pack(side='left', fill='x', expand=True, padx=(0, 5))

        # 最小化到托盘按钮
        self.btn_minimize = tk.Button(self.button_frame, text="🔽", command=self.hide_window,
                                      bg="#8e8e93", fg="white", font=("Arial", 12, "bold"),
                                      relief="flat", pady=8, cursor="hand2", width=3)
        self.btn_minimize.pack(side='right')

        # 二维码显示区域
        self.qr_label = tk.Label(main_frame, text="",
                                 bg="#e6e6e6", fg="#333", width=30, height=12, font=("Arial", 9))
        self.qr_label.pack(pady=5)

        # 初始显示所有可用地址
        self.show_all_ips_display(5000)

        # 底部链接提示
        self.url_label = tk.Label(main_frame, text="", fg="blue", font=("Arial", 9, "underline"), cursor="hand2")
        self.url_label.pack(pady=(5, 0))
        self.url_label.bind("<Button-1>", self.open_browser) # 点击用浏览器打开

        # 提示信息
        self.tip_label = tk.Label(main_frame, text="", fg="#888", font=("Arial", 8))
        self.tip_label.pack(pady=(5, 0))

        # 自动启动服务（延迟执行，确保GUI完全加载）
        self.root.after(100, self.auto_start_service)
        
        # 检查是否需要自动最小化（延迟更长时间确保服务已启动）
        self.root.after(500, self.check_auto_minimize)

    def show_all_ips_display(self, port, started=False):
        """显示所有可用 IP 地址列表"""
        # 过滤掉 0.0.0.0 和 Cloudflare 选项
        all_ips = [ip for ip in self.all_ips if not ip.startswith('0.0.0.0') and not ip.startswith('Cloudflare')]
        ip_list = '\n'.join([f"http://{ip}:{port}" for ip in all_ips])

        if started:
            # 已启动状态
            title = "监听所有网卡"
            tip = "💡 切换到具体 IP 可显示二维码"
        else:
            # 未启动状态
            title = "可用地址"
            tip = "💡 点击启动服务开始使用"

        self.qr_label.config(
            text=f"{title}\n\n{ip_list}\n\n{tip}",
            image='',
            bg="#e6e6e6",
            fg="#333",
            font=("Arial", 9)
        )

    def run_flask(self, host, port):
        try:
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"Error: {e}")

    def generate_qr(self, url, target_size=200):
        """生成二维码图像，自动调整大小以适应目标尺寸"""
        # 生成二维码图像
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        # 调整图像大小以适应显示区域
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)

        # 转换为 Tkinter 可用的格式
        img_tk = ImageTk.PhotoImage(img)
        return img_tk

    def on_paste_mode_changed(self):
        """粘贴模式改变时的回调"""
        global use_ctrl_v
        use_ctrl_v = self.use_ctrl_v_var.get()
        self.config['use_ctrl_v'] = use_ctrl_v
        save_config(self.config)
        mode = "Ctrl+V" if use_ctrl_v else "Shift+Insert"
        print(f"Paste mode: {mode}")

    def on_preserve_clipboard_changed(self):
        """剪贴板保护改变时的回调"""
        global preserve_clipboard
        preserve_clipboard = self.preserve_clipboard_var.get()
        self.config['preserve_clipboard'] = preserve_clipboard
        save_config(self.config)
        status = "enabled" if preserve_clipboard else "disabled"
        print(f"Clipboard preservation: {status}")

    def on_auto_minimize_changed(self):
        """自动最小化改变时的回调"""
        global auto_minimize
        auto_minimize = self.auto_minimize_var.get()
        self.config['auto_minimize'] = auto_minimize
        save_config(self.config)
        status = "enabled" if auto_minimize else "disabled"
        print(f"Auto minimize: {status}")

    def check_auto_minimize(self):
        """检查是否需要自动最小化窗口（调用 hide_window 方法隐藏到系统托盘）"""
        global auto_minimize
        if auto_minimize and self.is_running:
            self.hide_window()  # 调用现有的最小化按钮功能
            print("Window auto-minimized to system tray")

    def auto_start_service(self):
        """程序启动时自动启动服务"""
        if not self.is_running:
            selected = self.ip_var.get()

            # 判断模式并启动
            if selected == 'Cloudflare Chat Workers':
                cf_url = self.cf_url_var.get().strip()
                cf_key = self.cf_key_var.get()
                if cf_url and cf_key:
                    # 保存 CF 配置
                    self.config['mode'] = 'cf'
                    self.config['cf_url'] = cf_url
                    self.config['cf_key'] = cf_key
                    save_config(self.config)
                    self.start_cf_mode()
            else:
                # 保存局域网配置
                self.config['mode'] = 'lan'
                self.config['port'] = self.port_var.get()
                self.config['ip'] = selected
                save_config(self.config)
                self.start_lan_mode()

    def toggle_server(self):
        if self.is_running:
            # 停止服务并退出
            self.quit_app()
            return

        selected = self.ip_var.get()

        # 判断模式并启动
        if selected == 'Cloudflare Chat Workers':
            # 保存 CF 配置
            self.config['mode'] = 'cf'
            self.config['cf_url'] = self.cf_url_var.get()
            self.config['cf_key'] = self.cf_key_var.get()
            save_config(self.config)
            self.start_cf_mode()
        else:
            # 保存局域网配置
            self.config['mode'] = 'lan'
            self.config['port'] = self.port_var.get()
            self.config['ip'] = selected
            save_config(self.config)
            self.start_lan_mode()

    def parse_cf_config(self, config: str) -> tuple:
        """解析 CF 配置：key@url（保留兼容）"""
        if '@' not in config:
            return '', config
        at_pos = config.find('@')
        key = config[:at_pos]
        url = config[at_pos + 1:]
        return key, url

    def start_cf_mode(self):
        """启动 CF 模式"""
        if not CF_AVAILABLE:
            messagebox.showerror("错误", "CF 模式需要安装依赖:\npip install websockets cryptography")
            return

        url = self.cf_url_var.get().strip()
        key = self.cf_key_var.get()

        if not url:
            messagebox.showerror("错误", "请输入 CF Worker 地址")
            return

        # 确保 URL 有协议
        if not url.startswith('http'):
            url = 'https://' + url

        self.cf_mode = True
        self.cf_url = url
        self.cf_key = key

        # 创建 CF 客户端
        self.cf_client = CFChatClient(
            worker_url=url,
            password=key,
            on_message=self.on_cf_message,
            on_status=self.on_cf_status
        )
        self.cf_client.start()

        self.is_running = True
        self.btn_start.config(text="停止服务并退出", bg="#ff3b30")
        self.cf_url_entry.config(state='disabled', bg="#f0f0f0")
        self.cf_key_entry.config(state='disabled', bg="#f0f0f0")
        self.ip_combo.config(state='disabled')

        # 显示 cfchat URL 的二维码
        try:
            qr_size = min(self.root.winfo_width() - 80, 250)
            self.qr_img = self.generate_qr(url, target_size=qr_size)
            self.qr_label.config(image=self.qr_img, width=qr_size, height=qr_size,
                                bg="white", text='', font=("Arial", 10))
        except Exception as e:
            self.qr_label.config(text=f"二维码生成失败\n{e}")

        self.url_label.config(text=url)
        self.current_url = url
        self.tip_label.config(text="CF 模式：手机访问上方链接发送消息")

    def start_lan_mode(self):
        """启动局域网模式"""
        port_str = self.port_var.get().strip()

        if not port_str.isdigit():
            messagebox.showerror("错误", "端口必须是数字")
            return

        self.cf_mode = False
        port = int(port_str)
        host_ip = self.ip_var.get()

        # 确定监听地址
        if host_ip.startswith('0.0.0.0'):
            listen_host = '0.0.0.0'
        else:
            listen_host = host_ip

        # 启动 Flask 线程
        t = threading.Thread(target=self.run_flask, args=(listen_host, port), daemon=True)
        t.start()

        self.is_running = True
        self.listen_on_all = host_ip.startswith('0.0.0.0')
        self.btn_start.config(text="停止服务并退出", state='normal', bg="#ff3b30")
        self.port_entry.config(state='disabled', bg="#f0f0f0")

        if not self.listen_on_all:
            self.ip_combo.config(state='disabled')

        if host_ip.startswith('0.0.0.0'):
            self.show_all_ips_display(port, started=True)
            all_ips = [ip for ip in self.all_ips if not ip.startswith('0.0.0.0') and not ip.startswith('Cloudflare')]
            self.url_label.config(text="请手动输入上方地址")
            self.current_url = f"http://{all_ips[0]}:{port}" if all_ips else ""
            self.tip_label.config(text="")
        else:
            url = f"http://{host_ip}:{port}"
            try:
                qr_size = min(self.root.winfo_width() - 80, 250)
                self.qr_img = self.generate_qr(url, target_size=qr_size)
                self.qr_label.config(image=self.qr_img, width=qr_size, height=qr_size,
                                    bg="white", text='', font=("Arial", 10))
            except Exception as e:
                self.qr_label.config(text=f"二维码生成失败\n{e}")

            self.url_label.config(text=url)
            self.current_url = url
            self.tip_label.config(text="提示：如无法访问，请切换 IP 或端口重新扫码")

    def on_cf_message(self, text: str):
        """CF 模式收到消息回调"""
        self.root.after(0, lambda: self._handle_cf_message(text))

    def _handle_cf_message(self, text: str):
        """处理 CF 消息并粘贴"""
        paste_text(text)
        # 更新提示
        display = text[:30] + '...' if len(text) > 30 else text
        self.tip_label.config(text=f"已粘贴: {display}")

    def on_cf_status(self, state: str, text: str):
        """CF 模式状态回调"""
        self.root.after(0, lambda: self._update_cf_status(state, text))

    def _update_cf_status(self, state: str, text: str):
        """更新 CF 状态显示"""
        colors = {
            'connected': '#34c759',
            'connecting': '#f59e0b',
            'disconnected': '#888',
            'error': '#ff3b30'
        }
        self.tip_label.config(text=text, fg=colors.get(state, '#888'))

    def on_mode_changed(self, event=None):
        """模式/IP 改变时切换界面"""
        selected = self.ip_var.get()

        if selected == 'Cloudflare Chat Workers':
            # 切换到 CF 模式界面
            self.lan_frame.pack_forget()
            self.cf_frame.pack(fill='x', pady=(0, 10), before=self.button_frame)
        else:
            # 切换到局域网模式界面
            self.cf_frame.pack_forget()
            self.lan_frame.pack(fill='x', pady=(0, 10), before=self.button_frame)

            # 如果运行中且是 0.0.0.0 模式，更新二维码
            if self.is_running and hasattr(self, 'listen_on_all') and self.listen_on_all:
                self._update_lan_qr()

    def _update_lan_qr(self):
        """更新局域网模式二维码"""
        host_ip = self.ip_var.get()
        port = int(self.port_var.get())

        if host_ip.startswith('0.0.0.0'):
            self.show_all_ips_display(port, started=True)
            all_ips = [ip for ip in self.all_ips if not ip.startswith('0.0.0.0') and not ip.startswith('Cloudflare')]
            self.url_label.config(text="请手动输入上方地址")
            self.current_url = f"http://{all_ips[0]}:{port}" if all_ips else ""
            self.tip_label.config(text="")
        else:
            url = f"http://{host_ip}:{port}"
            try:
                qr_size = min(self.root.winfo_width() - 80, 250)
                self.qr_img = self.generate_qr(url, target_size=qr_size)
                self.qr_label.config(image=self.qr_img, width=qr_size, height=qr_size,
                                    bg="white", text='', font=("Arial", 10))
            except Exception as e:
                self.qr_label.config(text=f"二维码生成失败\n{e}")

            self.url_label.config(text=url)
            self.current_url = url
            self.tip_label.config(text="提示：如无法访问，请切换 IP 重新扫码")

    def create_tray_icon(self):
        """创建系统托盘图标"""
        # 尝试加载 icon.ico，保持与窗口图标一致
        try:
            icon_path = get_icon_path()
            if icon_path:
                icon_image = Image.open(icon_path)
            elif os.path.exists('icon.png'):
                icon_image = Image.open('icon.png')
            else:
                # 创建一个简单的蓝色图标
                icon_image = Image.new('RGB', (64, 64), color='#007AFF')
        except Exception:
            # 如果加载失败，创建简单图标
            icon_image = Image.new('RGB', (64, 64), color='#007AFF')

        # 创建托盘菜单
        menu = pystray.Menu(
            item('显示窗口', self.show_window),
            item('退出', self.quit_app)
        )

        # 创建托盘图标
        self.tray_icon = pystray.Icon("QAA-AirType", icon_image, "QAA AirType", menu)

        # 在后台线程运行托盘图标
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self):
        """隐藏窗口到系统托盘"""
        self.root.withdraw()

    def show_window(self, icon=None, item=None):
        """显示窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_app(self, icon=None, item=None):
        """退出应用"""
        # 停止 CF 客户端
        if self.cf_client:
            self.cf_client.stop()
            self.cf_client = None
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()

    def open_browser(self, event):
        if hasattr(self, 'current_url'):
            import webbrowser
            webbrowser.open(self.current_url)

if __name__ == '__main__':
    root = tk.Tk()
    app_gui = ServerApp(root)
    root.mainloop()