# Python 集成实践 — RTASR 实时语音转写

## RTASR 签名函数

```python
import base64
import hashlib
import hmac
import time

def generate_rtasr_sign(app_id, api_key):
    """生成 RTASR 鉴权 signa"""
    ts = str(int(time.time()))
    base_string = app_id + ts
    md5_hash = hashlib.md5(base_string.encode()).digest()
    signa = base64.b64encode(
        hmac.new(api_key.encode(), md5_hash, hashlib.sha1).digest()
    ).decode()
    return signa, ts

def build_rtasr_url(app_id, api_key, **kwargs):
    """构建 RTASR WebSocket URL"""
    signa, ts = generate_rtasr_sign(app_id, api_key)
    params = {"appid": app_id, "ts": ts, "signa": signa}
    params.update(kwargs)  # lang, pd, roleType 等
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"wss://rtasr.xfyun.cn/v1/ws?{query}"
```

## WebSocket 主流程

```python
import websocket
import json
import time

class RTASRClient:
    def __init__(self, app_id, api_key):
        self.app_id = app_id
        self.api_key = api_key
        self.results = []  # 收集所有结果
        self.ws = None

    def on_open(self, ws):
        """连接成功后开始发送音频"""
        pass  # 在外部调用 send_audio

    def on_message(self, ws, message):
        msg = json.loads(message)
        action = msg.get("action", "")

        if action == "started":
            print(f"握手成功: sid={msg.get('sid')}")
        elif action == "error":
            raise Exception(f"错误 {msg.get('code')}: {msg.get('desc')}")
        else:
            # 转写结果
            data_str = msg.get("data", "")
            if data_str:
                result = json.loads(data_str)
                self.results.append(result)

    def send_audio(self, pcm_data: bytes):
        """发送 PCM 音频（Binary Message），每 40ms 调用一次"""
        if self.ws:
            self.ws.send(pcm_data, opcode=websocket.ABNF.OPCODE_BINARY)

    def end_audio(self):
        """发送结束标志"""
        if self.ws:
            self.ws.send(json.dumps({"end": True}),
                         opcode=websocket.ABNF.OPCODE_BINARY)

    def recognize(self, pcm_generator, chunk_size=1280):
        """
        实时识别
        pcm_generator: 生成器，每次 yield 1280 字节 PCM 数据
        """
        url = build_rtasr_url(self.app_id, self.api_key, lang="cn")
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
        )

        def send_loop():
            for chunk in pcm_generator:
                self.send_audio(chunk)
                time.sleep(0.04)  # 40ms 间隔
            self.end_audio()

        import threading
        send_thread = threading.Thread(target=send_loop)
        send_thread.start()
        self.ws.run_forever()
        send_thread.join()

        return self.results
```

## Spark IAT 大模型版

### 与 IAT v2 的区别

```python
# IAT v2
HOST = "iat-api.xfyun.cn"
REQUEST_LINE = "GET /v2/iat HTTP/1.1"

# Spark IAT (大模型版)
HOST = "iat.xf-yun.com"
REQUEST_LINE = "GET /v1 HTTP/1.1"

# business 参数也不同
# IAT v2:
business = {"language": "zh_cn", "domain": "iat", "accent": "mandarin"}
# Spark IAT:
parameter = {"iat": {"domain": "slm", "language": "zh_cn", "accent": "mandarin"}}
```

鉴权函数和 WebSocket 流程与 IAT v2 完全一致，只需改 HOST 和 REQUEST_LINE。

---

## 官方 Python SDK

讯飞在 GitHub 提供了 Python Demo：
- IAT: GitHub `iflytek` 组织下搜索 `websocket-iat-python`
- RTASR: GitHub 搜索 `websocket-rtasr-python`
- Lfasr: GitHub 搜索 `lfasr-python`

也可通过 SDK 下载中心 (https://www.xfyun.cn/sdk/dispatcher) 下载对应的 Python/Java/go Demo。
