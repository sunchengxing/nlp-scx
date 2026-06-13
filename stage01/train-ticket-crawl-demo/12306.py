from logging import Logger

import sys
sys.path.append('/Users/scx/data/codeData/python/nlp-scx/stage01/baidu-crawl-demo')
from base_utils.request_utils import HttpRequest, ImageFormat
import logging as log

class P12306:

    def __init__(self):
        cookies = {
            '_uab_collina': '178106964127092443905042',
            'JSESSIONID': '3729B575ED5F076F43E1A099C4ADE904',
            'BIGipServerotn': '1457062154.24610.0000',
            'guidesStatus': 'off',
            'highContrastMode': 'defaltMode',
            'cursorStatus': 'off',
            'BIGipServerpassport': '971505930.50215.0000',
            '_big_fontsize': '0',
            'route': '9036359bb8a8a461c164a04f8f50b252',
            '_jc_save_fromStation': '%u5317%u4EAC%2CBJP',
            '_jc_save_toStation': '%u4E0A%u6D77%2CSHH',
            '_jc_save_toDate': '2026-06-10',
            '_jc_save_wfdc_flag': 'dc',
            '_jc_save_fromDate': '2026-06-10',
        }
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'If-Modified-Since': '0',
            'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc&fs=%E5%8C%97%E4%BA%AC,BJP&ts=%E4%B8%8A%E6%B5%B7,SHH&date=2026-06-10&flag=N,N,Y',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }
        self.http_request = HttpRequest(
            headers=headers,
            cookies=cookies)
        self.log = log
        # 设置日志级别为INFO
        self.log.basicConfig(level=log.INFO)
        self.log.info("12306爬虫初始化完成")


    def parse_train(self, raw: str, station_map: dict) -> dict:
        parts = raw.split('|')
        return {
            'train_no':     parts[3],
            'from_station': station_map.get(parts[4], parts[4]),
            'to_station':   station_map.get(parts[5], parts[5]),
            'depart_time':  parts[8],
            'arrive_time':  parts[9],
            'duration':     parts[10],
            'secret':       parts[0],
        }

    def get_12306_ticket_info(self, from_station, to_station, from_date):
        params = {
            'leftTicketDTO.train_date': from_date,
            'leftTicketDTO.from_station': from_station,
            'leftTicketDTO.to_station': to_station,
            'purpose_codes': 'ADULT',
        }
        resp = self.http_request.do_get('https://kyfw.12306.cn/otn/leftTicket/queryG', params=params)
        if not isinstance(resp, dict) or not resp.get('status'):
            self.log.error('接口返回异常')
            return
        station_map = resp['data']['map']
        trains = [self.parse_train(r, station_map) for r in resp['data']['result']]
        print(f"\n{'车次':<8}{'出发站':<10}{'到达站':<10}{'出发':<8}{'到达':<8}{'历时'}")
        print('-' * 55)
        for t in trains:
            print(f"{t['train_no']:<8}{t['from_station']:<10}{t['to_station']:<10}{t['depart_time']:<8}{t['arrive_time']:<8}{t['duration']}")


if __name__ == '__main__':
    p12306 = P12306()
    p12306.get_12306_ticket_info('BJP', 'SHH', '2026-06-10')