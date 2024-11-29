import datetime
import logging
import os
import re
import traceback

import requests
import urllib3

import utils
from BiliLive import BiliLive
import subprocess

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BiliLiveRecorder(BiliLive):
    def __init__(self, config: dict, global_start: datetime.datetime):
        BiliLive.__init__(self, config)
        self.record_dir = utils.init_record_dir(
            self.room_id, global_start, config.get('root', {}).get('data_path', "./"))
        self.recording_dir = os.path.join(
            os.getcwd(),
            'recording'
        )
        self.record_dir = os.path.join(
            os.getcwd(),
            'recorded'
        )

    def record(self, record_url: str, output_filename: str) -> None:
        try:
            live_count = 0
            logging.info(self.generate_log('√ 正在录制...' + self.room_id))
            default_headers = {
                'Accept-Encoding': 'identity',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Referer': 'https://live.bilibili.com/'
            }
            headers = {**default_headers, **
                       self.config.get('root', {}).get('request_header', {})}
            resp = requests.get(record_url, stream=True,
                                headers=headers,
                                timeout=self.config.get(
                                    'root', {}).get('check_interval', 120))
            with open(output_filename, "wb") as f: # 1KB
                for chunk in resp.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                    if not self.live_status:
                        live_count += 1
                        # 100MB
                    if live_count > 300000:
                        raise Exception(f'{self.room_id} is not live anymore.')
        except Exception as e:
            logging.error(self.generate_log(
                'Error while recording:' + str(e)))

    def run(self) -> None:
        logging.basicConfig(level=utils.get_log_level(self.config),
                            format='%(asctime)s %(thread)d %(threadName)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            handlers=[logging.FileHandler(os.path.join(self.config.get('root', {}).get('logger', {}).get('log_path', "./log"), "LiveRecoder_"+datetime.datetime.now(
                            ).strftime('%Y-%m-%d_%H-%M-%S')+'.log'), "a", encoding="utf-8")])
        while True:
            try:
                if self.live_status:
                    urls = self.get_live_urls()

                    filename = utils.generate_filename(self.room_id, room_status=self.get_room_info())
                    c_filename = os.path.join(self.recording_dir, filename)
                    self.record(urls[0], c_filename)
                    logging.info(self.generate_log('录制完成' + c_filename))
                    if os.path.getsize(c_filename) < 200:
                        logging.warning(self.generate_log('recorded size is too small; removing' + c_filename))
                        os.remove(c_filename)
                    else:                       
                        os.replace(c_filename, os.path.join(self.record_dir, filename))
                else:
                    logging.info(self.generate_log('下播了'))
                    # recorded streams for whatever reason dont have duration metadata stored; to solve 
                    # we do a ffmpeg copy.  copy -c:a copy
                    break
            except Exception as e:
                logging.error(self.generate_log(
                    'Error while checking or recording:' + str(e)+traceback.format_exc()))
