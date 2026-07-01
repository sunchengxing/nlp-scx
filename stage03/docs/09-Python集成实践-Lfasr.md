# Python 集成实践 — Lfasr 语音转写（长音频）

## Lfasr 签名函数

```python
import base64
import hashlib
import hmac
import time

def generate_lfasr_sign(app_id, secret_key):
    """生成 Lfasr 鉴权 signa"""
    ts = str(int(time.time()))
    base_string = app_id + ts
    md5_hash = hashlib.md5(base_string.encode()).digest()
    signa = base64.b64encode(
        hmac.new(secret_key.encode(), md5_hash, hashlib.sha1).digest()
    ).decode()
    return signa, ts
```

## 完整转写流程

```python
import requests
import os

class LfasrClient:
    BASE_URL = "https://raasr.xfyun.cn/api"

    def __init__(self, app_id, secret_key):
        self.app_id = app_id
        self.secret_key = secret_key

    def _sign(self):
        signa, ts = generate_lfasr_sign(self.app_id, self.secret_key)
        return {"app_id": self.app_id, "signa": signa, "ts": ts}

    def prepare(self, file_path, slice_size=10*1024*1024):
        """第 1 步：预处理"""
        file_len = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        slice_num = max(1, (file_len + slice_size - 1) // slice_size)

        params = {
            **self._sign(),
            "file_len": str(file_len),
            "file_name": file_name,
            "slice_num": slice_num,
            "lfasr_type": "0",
            "has_participle": "false",
            "speaker_number": "2",
        }
        resp = requests.post(
            f"{self.BASE_URL}/prepare",
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        result = resp.json()
        if result.get("ok") != 0:
            raise Exception(f"Prepare failed: {result}")
        return result["data"]  # task_id

    def upload(self, task_id, file_path, slice_size=10*1024*1024):
        """第 2 步：分片上传（串行）"""
        file_len = os.path.getsize(file_path)
        slice_num = max(1, (file_len + slice_size - 1) // slice_size)

        with open(file_path, "rb") as f:
            for i in range(slice_num):
                # 生成 slice_id（"aaaaaaaaaa" 起递增）
                slice_id = self._gen_slice_id(i)

                chunk = f.read(slice_size)
                params = {**self._sign(), "task_id": task_id, "slice_id": slice_id}
                resp = requests.post(
                    f"{self.BASE_URL}/upload",
                    data=params,
                    files={"content": chunk}
                )
                if resp.json().get("ok") != 0:
                    raise Exception(f"Upload slice {i} failed: {resp.json()}")

    def _gen_slice_id(self, idx):
        """生成分片 ID（base-30 用 a-z+数字）"""
        chars = "abcdefghijklmnopqrstuvwxyz01234"
        result = ["a"] * 10
        pos = 9
        n = idx
        while n > 0 and pos >= 0:
            result[pos] = chars[n % 30]
            n //= 30
            pos -= 1
        return "".join(result)

    def merge(self, task_id):
        """第 3 步：合并"""
        params = {**self._sign(), "task_id": task_id}
        resp = requests.post(
            f"{self.BASE_URL}/merge",
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        return resp.json().get("ok") == 0

    def get_progress(self, task_id):
        """第 4 步：查询进度（返回 status 数字）"""
        params = {**self._sign(), "task_id": task_id}
        resp = requests.post(
            f"{self.BASE_URL}/getProgress",
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        result = resp.json()
        if result.get("ok") != 0:
            raise Exception(f"Progress query failed: {result}")
        data = json.loads(result["data"])
        return data["status"]

    def get_result(self, task_id):
        """第 5 步：获取结果"""
        params = {**self._sign(), "task_id": task_id}
        resp = requests.post(
            f"{self.BASE_URL}/getResult",
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        result = resp.json()
        if result.get("ok") != 0:
            raise Exception(f"Get result failed: {result}")
        return json.loads(result["data"])

    def transcribe(self, file_path, poll_interval=600):
        """一键转写（阻塞直到完成）"""
        import json
        task_id = self.prepare(file_path)
        self.upload(task_id, file_path)
        self.merge(task_id)

        # 轮询等待完成
        while True:
            status = self.get_progress(task_id)
            if status == 9:
                return self.get_result(task_id)
            time.sleep(poll_interval)
```
