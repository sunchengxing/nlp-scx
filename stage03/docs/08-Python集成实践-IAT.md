# Python 集成实践指南

## 接入前置准备

### 步骤 1：注册并创建应用
1. 访问 https://www.xfyun.cn/ 注册开发者账号
2. 控制台 → 创建应用 → 获取 **APPID、APIKey、APISecret**
3. 在应用服务列表中找到目标服务（如"语音听写"）→ 开通并查看可用量

### 步骤 2：实名认证
应用调试通过后，正式商用前必须完成实名认证。企业用户不能以个人身份认证。

### 步骤 3：购买服务量
正式上线前按需购买交互量/时长套餐包。

---

## 一、IAT 流式听写 Python 示例

### 核心依赖
```bash
pip install websocket-client
```

### 鉴权函数

```python
import base64
import hashlib
import hmac
import time
from datetime import datetime, timezone

def generate_auth(host, api_key, api_secret, request_line="GET /v2/iat HTTP/1.1"):
    """生成 IAT WebSocket 鉴权参数"""
    # 1. GMT 时间
    now = datetime.now(timezone.utc)
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    # 2. 构建签名字符串
    signature_origin = f"host: {host}\ndate: {date}\n{request_line}"

    # 3. HMAC-SHA256 签名
    signature_sha = hmac.new(
        api_secret.encode('utf-8'),
        signature_origin.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode()

    # 4. authorization 原始字符串
    auth_origin = (
        f'api_key="{api_key}",'
        f'algorithm="hmac-sha256",'
        f'headers="host date request-line",'
        f'signature="{signature}"'
    )
    authorization = base64.b64encode(auth_origin.encode()).decode()

    # 5. 构建完整 URL
    url = (f"wss://{host}/v2/iat?"
           f"authorization={authorization}&"
           f"date={date}&"
           f"host={host}")

    return url
```

### WebSocket 主流程

```python
import websocket
import json
import threading

class IATClient:
    def __init__(self, app_id, api_key, api_secret,
                 host="iat-api.xfyun.cn", audio_rate=16000):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = host
        self.audio_rate = audio_rate
        self.result = []
        self.ws = None

    def on_message(self, ws, message):
        msg = json.loads(message)
        code = msg.get("code", 0)
        if code != 0:
            raise Exception(f"Error {code}: {msg.get('message')}")

        data = msg.get("data", {})
        if data.get("status") == 2:  # 最后一片
            ws.close()

        result = data.get("result", {})
        if result:
            ws_list = result.get("ws", [])
            for item in ws_list:
                for cw in item.get("cw", []):
                    self.result.append(cw.get("w", ""))

    def on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status, close_msg):
        pass

    def on_open(self, ws):
        def run():
            # 首帧：发送参数
            common = {"app_id": self.app_id}
            business = {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "ptt": 1,       # 添加标点
                "dwa": "wpgs",  # 开启动态修正
            }
            data_params = {
                "status": 0,
                "format": f"audio/L16;rate={self.audio_rate}",
                "encoding": "raw",
                "audio": base64.b64encode(audio_data).decode()
            }
            req = {
                "common": common,
                "business": business,
                "data": data_params
            }
            ws.send(json.dumps(req))

            # 中间帧 + 末帧
            # status=1 中间帧，status=2 末帧(audio="")
            # 每40ms发送一帧

        threading.Thread(target=run).start()

    def recognize(self, audio_data: bytes) -> str:
        """识别 PCM 音频数据"""
        url = generate_auth(self.host, self.api_key, self.api_secret)
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        # 运行 WebSocket（阻塞直到完成）
        self.ws.run_forever()
        return "".join(self.result)
```
