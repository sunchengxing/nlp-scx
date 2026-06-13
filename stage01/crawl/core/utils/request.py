import os
import io
import requests
from enum import Enum


class HttpMethods(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    HEAD = "HEAD"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"

class ImageFormat(Enum):
    JPEG = "JPEG"
    PNG = "PNG"
    GIF = "GIF"
    BMP = "BMP"
    WEBP = "WEBP"

class RGB(Enum):
    RGB = "RGB"
    RGBA = "RGBA"

class ContentType(Enum):
    JSON = "application/json"
    FORM = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    TEXT = "text/plain"

class UserAgent(Enum):
    CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36"
    FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15"
    EDGE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.64"
    OPERA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 OPR/77.0.4054.277"
    CHROME_CURRENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"

class HttpHeaders(Enum):
    USER_AGENT = "User-Agent"
    ACCEPT = "Accept"
    ACCEPT_LANGUAGE = "Accept-Language"
    ACCEPT_ENCODING = "Accept-Encoding"
    CONNECTION = "Connection"
    CACHE_CONTROL = "Cache-Control"
    REFERER = "Referer"
    ORIGIN = "Origin"
    UPGRADE_INSECURE_REQUESTS = "Upgrade-Insecure-Requests"
    COOKIE = "Cookie"

class HttpRequest:

    def __init__(self, headers,  cookies, bearer_token, content_type:ContentType):
        self.session = requests.session()
        self.headers = headers
        self.cookies = cookies
        # Enum 值自动取 .value，确保 headers 里都是纯字符串
        clean_headers = {k.value if isinstance(k, Enum) else k: v.value if isinstance(v, Enum) else v
                         for k, v in headers.items()}
        self.session.headers.update(clean_headers)
        self.session.cookies.update(cookies)
        if bearer_token:
            self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})
        if content_type:
            self.session.headers.update({"Content-Type": content_type.value})
        self.get_request_params = None
        self.post_request_params = None
        self.request_url = None
        self.request_method = None
        self.response = None
        self.status_code = None


    def do_get(self, url, params=None, **kwargs) -> str:
        self.request_method = HttpMethods.GET
        self.request_url =  url
        self.get_request_params = params
        self.response = self.session.get(url, params=params, **kwargs)
        self.status_code = self.response.status_code
        return self.response.json()

    def do_post(self, url, data=None, json=None, **kwargs) -> str:
        """
        :param url:
        :param data:
        :param json:
        :param kwargs:
        :return:
        """
        self.request_method = HttpMethods.POST
        self.request_url = url
        self.post_request_params = data
        self.response = self.session.post(url, data=data, json=json, **kwargs)
        self.status_code = self.response.status_code
        return self.response.json()


    def do_download_image_with_format(self, url, save_path, image_format:ImageFormat=ImageFormat.JPEG,quality=95, chunky_size = 1024, rgb:RGB=RGB.RGB):
        self.request_method = HttpMethods.GET
        self.request_url = url
        self.response = self.session.get(url, stream=True)
        # 先看看文件夹是否存在
        if not os.path.exists(os.path.dirname(save_path)):
            # 创建文件夹
            os.makedirs(os.path.dirname(save_path))
        image_bytes = b''.join(chunky for chunky in self.response.iter_content(chunk_size=chunky_size) if chunky)
        image_cache = Image.open(io.BytesIO(image_bytes))
        if image_format == ImageFormat.PNG:
            image = image_cache.convert(rgb.RGBA.value)
            image.save(save_path, format= image_format.value)
        else:
            image = image_cache.convert(rgb.RGB.value)
            image.save(save_path, format= image_format.value, quality=quality)  # type: ignore