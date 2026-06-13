# Python requests 库快速总结

## 安装

```bash
pip install requests
```

---

## 基础请求

```python
import requests

resp = requests.get('https://api.example.com/users')
resp = requests.post('https://api.example.com/users', json={'name': 'Alice'})
requests.put(url, data=...)
requests.delete(url)
requests.patch(url, json=...)
```

---

## 传参方式

```python
# URL 查询参数
resp = requests.get(url, params={'page': 1, 'size': 10})

# 表单提交
resp = requests.post(url, data={'key': 'value'})

# JSON 请求体
resp = requests.post(url, json={'key': 'value'})

# 文件上传
resp = requests.post(url, files={'file': open('photo.jpg', 'rb')})
```

---

## 请求头 & 认证

```python
headers = {'Authorization': 'Bearer token123'}
resp = requests.get(url, headers=headers)

# Basic Auth
resp = requests.get(url, auth=('user', 'pass'))
```

---

## 处理响应

```python
resp.status_code   # 200
resp.text          # 字符串
resp.json()        # 解析 JSON -> dict
resp.content       # 原始字节（图片/文件）
resp.headers       # 响应头 dict
resp.url           # 最终 URL
```

---

## 超时 & 错误处理

```python
try:
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
except requests.Timeout:
    print('超时')
except requests.HTTPError as e:
    print(f'HTTP错误: {e.response.status_code}')
except requests.ConnectionError:
    print('网络连接失败')
```

---

## Session（复用连接 + Cookie）

```python
with requests.Session() as s:
    s.headers.update({'Authorization': 'Bearer token'})
    s.get('https://api.example.com/login')
    s.get('https://api.example.com/profile')
```

---

## 关键参数速查

| 参数 | 说明 |
|------|------|
| `params` | URL 查询字符串 |
| `data` | 表单数据 |
| `json` | JSON 请求体（自动设 Content-Type） |
| `headers` | 请求头 |
| `auth` | 认证 |
| `timeout` | 超时秒数，建议始终设置 |
| `verify` | SSL 验证，False 跳过 |
| `proxies` | 代理设置 |
| `allow_redirects` | 是否跟随重定向，默认 True |

---

**一句话总结：** `get/post` + `resp.json()` 搞定 90% 场景，复杂场景用 `Session` 复用连接。
