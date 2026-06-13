# 使用request库去获取数据
# 快速认识与入门
import random

import time

from typing import List

from base_utils.request_utils import HttpRequest, ImageFormat
from base_utils.char_utils import CharUtils as charUtils
import logging as log

    # get请求
    # r = requests.get("http://jsonplaceholder.typicode.com/posts")
    # print(r.json())
    # 基于session复用机制
    # current_session = self.req.session()

    # 任务 抓取baidu的图片
    # 百度图片的产生是通过ai底层引擎推送的，主要聚焦于用户的输入参数
    # 先拿到预选参数



class BaiduImageCrawler:

    def __init__(self):
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://image.baidu.com',
            'Referer': 'https://image.baidu.com/search/index?tn=baiduimage&fm=result&ie=utf-8&word=%E6%A1%A5%E6%A2%81',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }
        cookies = {
            'BDUSS': 'h1TjR6U3pzSHk3YXNWSXYySUVnYjNXRTZHbmg3VGowd1UtZnhDOHhrV0czbjFvRVFBQUFBJCQAAAAAAAAAAAEAAABv4xP1c2JubXNsY25tYgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIZRVmiGUVZoTk',
            'BDUSS_BFESS': 'h1TjR6U3pzSHk3YXNWSXYySUVnYjNXRTZHbmg3VGowd1UtZnhDOHhrV0czbjFvRVFBQUFBJCQAAAAAAAAAAAEAAABv4xP1c2JubXNsY25tYgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIZRVmiGUVZoTk',
            'BIDUPSID': 'F217901715A2A53560AA7DD797A15380',
            'PSTM': '1780836941',
            'BDORZ': 'B490B5EBF6F3CD402E515D22BCDA1598',
            'BAIDUID': '130F6B7F14915B585A2909B8FE8AB0DC:FG=1',
            'BAIDUID_BFESS': '130F6B7F14915B585A2909B8FE8AB0DC:FG=1',
        }
        self.req = HttpRequest(headers = headers, cookies = cookies)
        self.log = log
        # 设置日志界别
        log.basicConfig(level=log.INFO)
        self.image_category = None


    def get_baidu_image_category(self, request_url, data=None) -> tuple[dict, dict]:
        """

        :param request_url:
        :param data:
        :return:
        """
        image_category_json_resp = self.req.do_post(request_url, data=data )
        # self.log.info(image_category_json_resp)
        if not isinstance(image_category_json_resp, dict):
            log.error(f'百度图片类目获取失败，返回数据结构异常，请稍后再试')
            raise Exception('百度图片类目获取失败，返回数据结构异常，请稍后再试')
        if image_category_json_resp['status'] != 0:
            log.error(f'百度图片类目获取失败，请稍后再试')
            raise Exception('百度图片类目获取失败，status 非 0')
        # 获取图片的最终类目数据
        desc_list_resp_json = image_category_json_resp['descList']
        cur_category_dict_normal = {(category_index + 1): category_str for category_index, category_str in enumerate(desc_list_resp_json)}
        cur_category_dict_reverse = {category_str : (category_index + 1) for category_index, category_str in enumerate(desc_list_resp_json)}
        return cur_category_dict_normal, cur_category_dict_reverse

    def get_baidu_image_urls_by_category(self, request_url, params=None) -> list[str]:
        """
        :param request_url:
        :param params:
        :return: 图片 URL 列表
        """
        resp = self.req.do_get(request_url, params=params)
        self.log.info(f'图片列表接口原始返回: {resp}')
        if not isinstance(resp, dict):
            self.log.error('图片列表接口返回格式异常')
            return []
        self.log.info(f'返回的所有 key: {list(resp.keys())}')
        data = resp.get('data', {}).get('images', [])
        urls = []
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get('thumburl') or item.get('objurl')
            if url:
                urls.append(url)
        self.log.info(f'共获取到 {len(urls)} 张图片')
        return urls

    def download_baidu_image_with_urls(self, urls: List[str]) :
        for url in urls:
            self.log.info(f'开始下载图片: {url}')
            self.req.do_download_image_with_format(url, f'outputs/images/{current_user_choice_int}_{url.split("/")[-1]}.jpg', ImageFormat.JPEG)
            # 暂停  3 ～ 5秒
            time.sleep(random.randint(3, 5))
            self.log.info(f'图片下载完成: {url}')

if __name__ == '__main__':
    baidu_image_crawler = BaiduImageCrawler()
    category_request_url = 'https://image.baidu.com/aigc/generate'
    data = {
        'query83': '38',
        'query970': '25',
        'querycate': '20',
        'query': '桥梁',
    }
    category_dict_normal, category_dict_reverse = baidu_image_crawler.get_baidu_image_category(category_request_url, data=data)
    print('当前百度图片类目如下所示：')
    print('\n'.join(f'{category_index + 1}-{category_str}'  for category_index, category_str in enumerate(category_dict_reverse)))
    x = input("请输入你需要选择的类目：")
    current_user_choice_int = 0 # 默认
    current_user_choice_str = '' # 默认
    if x.isdigit():
        # 是通过数字输入的 默认写实
        current_category_str = category_dict_normal.get(int(x), '写实')
        current_user_choice_int = int(x)
        # 打印用户所选择的类目
        print(f'当前用户所选择的类目是: 【 {current_category_str} 】' )
    elif charUtils.is_chinese(x):
        # 是通过文本输入的 其实这里还需要校验特殊字符之类的，这里跳过了
        current_user_choice_int = category_dict_reverse.get(x, 11)
        # 打印用户所选择的类目
        # log.info(f'当前数据{x}, 对应的类目id是：{current_user_choice_int}')
        print(f'当前用户所选择的类目是: 【 {x} 】')

    image_url_request_params = {
        'tn': 'resulttagjson',
        'word': '桥梁',
        'ie': 'utf-8',
        'fp': 'result',
        'fr': '',
        'ala': '0',
        'applid': '8074698100461062453',
        'pn': '0',
        'rn': '30',
        'nojc': '0',
        'gsm': '1e',
        'newReq': '1',
        'data_type': 'json',
        'queryWord': '桥梁',
        'cl': '2',
        'lm': '-1',
        'width': '',
        'height': '',
        'ic': str(current_user_choice_int),
    }
    image_url_request_params['word'] = image_url_request_params['word'] + current_user_choice_str
    image_request_url = 'https://image.baidu.com/search/acjson'
    urls = baidu_image_crawler.get_baidu_image_urls_by_category(image_request_url, params=image_url_request_params)
    print(f'共获取到 {len(urls)} 张图片URL：')
    for i, url in enumerate(urls):
        print(f'{i + 1}: {url}')
    # 下载图片
    baidu_image_crawler.download_baidu_image_with_urls(urls)

#
#
# data = {
#             'query83': '38',
#             'query970': '25',
#             'querycate': '20',
#             'query': '桥梁',
#         }
#
#
# category_request_url = 'https://image.baidu.com/aigc/generate'
#
# # 拿到百度图片的泪目的响应
# category_resp = current_session.post(category_request_url, cookies= current_cookie, headers = headers, data=data)
# category_resp.close()
#
# # 打印测试
# # print(category_resp.json())
#
# # 获取泪目最终数据
# descList_resp_json = category_resp.json()['descList']
# # print(descList_resp_json)
# print('当前百度图片类目如下所示：')
# # 展示为console待选择category：['夜晚', '泡泡', '体积', '泡泡马特风格', '黄色', '绚丽', '开心', '侧面', '电脑', '科技感', '立体', '光滑', '体积光', '中国风', '8k高清壁纸', '全身', '国潮', '8k', '中式', '帅气']
# category_dict_normal = {(category_index + 1) :category_str for category_index, category_str in enumerate(descList_resp_json) }
# category_dict_reverse = {category_str : (category_index + 1) for category_index, category_str in enumerate(descList_resp_json) }

#
