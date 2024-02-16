from collections import Counter

import ctypes
import datetime
import logging
import os
import platform
import threading
from enum import Enum
import yaml
import subprocess
import glob
import shutil
import re
import shlex
import prettytable as pt



def is_windows() -> bool:
    plat_sys = platform.system()
    return plat_sys == "Windows"


if is_windows():
    import winreg


def get_log_level(config: dict) -> int:
    if config['root']['logger']['log_level'] == 'DEBUG':
        return logging.DEBUG
    if config['root']['logger']['log_level'] == 'INFO':
        return logging.INFO
    if config['root']['logger']['log_level'] == 'WARN':
        return logging.WARN
    if config['root']['logger']['log_level'] == 'ERROR':
        return logging.ERROR
    return logging.INFO


def check_and_create_dir(dirs: str) -> None:
    if not os.path.exists(dirs):
        os.mkdir(dirs)


def init_data_dirs(root_dir: str = os.getcwd()) -> None:
    check_and_create_dir(os.path.join(root_dir, 'data'))
    check_and_create_dir(os.path.join(root_dir, 'data', 'records'))
    check_and_create_dir(os.path.join(root_dir, 'data', 'merged'))
    check_and_create_dir(os.path.join(root_dir, 'data', 'merge_confs'))
    check_and_create_dir(os.path.join(root_dir, 'data', 'danmu'))
    check_and_create_dir(os.path.join(root_dir, 'data', 'outputs'))
    check_and_create_dir(os.path.join(root_dir, 'data', 'splits'))
    check_and_create_dir(os.path.join(root_dir, 'data', 'cred'))
    check_and_create_dir(os.path.join(root_dir, 'recording'))
    check_and_create_dir(os.path.join(root_dir, 'recorded'))


def init_record_dir(room_id: str, global_start: datetime.datetime, root_dir: str = os.getcwd()) -> str:
    dirs = os.path.join(root_dir, 'data', 'records',
                        f"{room_id}_{global_start.strftime('%Y-%m-%d_%H-%M-%S')}")
    check_and_create_dir(dirs)
    return dirs


def init_danmu_log_dir(room_id: str, global_start: datetime.datetime, root_dir: str = os.getcwd()) -> str:
    log_dir = os.path.join(
        root_dir, 'data', 'danmu', f"{room_id}_{global_start.strftime('%Y-%m-%d_%H-%M-%S')}")
    check_and_create_dir(log_dir)
    return log_dir


def generate_filename(room_id: str, room_status: dict = None) -> str:
    if room_status is not None:
        # {'room_name': '小唱一下寻找状态', 'site_name': 'BiliBili', 'site_domain': 'live.bilibili.com', 'status': True, 'hostname': '内德维德'}
        return f"[{room_status['hostname']}] {room_status['room_name']} {datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.flv"
    return f"{room_id}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.flv"


def get_global_start_from_records(record_dir: str) -> datetime.datetime:
    base = os.path.basename(record_dir)
    return datetime.datetime.strptime(" ".join(base.split("_")[1:3]), '%Y-%m-%d %H-%M-%S')


def get_merged_filename(room_id: str, global_start: datetime.datetime, root_dir: str = os.getcwd()) -> str:
    filename = os.path.join(root_dir, 'data', 'merged',
                            f"{room_id}_{global_start.strftime('%Y-%m-%d_%H-%M-%S')}_merged.mp4")
    return filename


def init_outputs_dir(room_id: str, global_start: datetime.datetime, root_dir: str = os.getcwd()) -> str:
    dirs = os.path.join(root_dir, 'data', 'outputs',
                        f"{room_id}_{global_start.strftime('%Y-%m-%d_%H-%M-%S')}")
    check_and_create_dir(dirs)
    return dirs


def init_splits_dir(room_id: str, global_start: datetime.datetime, root_dir: str = os.getcwd()) -> str:
    dirs = os.path.join(root_dir, 'data', 'splits',
                        f"{room_id}_{global_start.strftime('%Y-%m-%d_%H-%M-%S')}")
    check_and_create_dir(dirs)
    return dirs


def get_merge_conf_path(room_id: str, global_start: datetime.datetime, root_dir: str = os.getcwd()) -> str:
    filename = os.path.join(root_dir, 'data', 'merge_confs',
                            f"{room_id}_{global_start.strftime('%Y-%m-%d_%H-%M-%S')}_merge_conf.txt")
    return filename


def get_cred_filename(room_id: str, root_dir: str = os.getcwd()) -> str:
    filename = os.path.join(root_dir, 'data', 'cred',
                            f"{room_id}_cred.json")
    return filename


def del_files_and_dir(dirs: str) -> None:
    for filename in os.listdir(dirs):
        os.remove(os.path.join(dirs, filename))
    os.rmdir(dirs)


def get_rough_time(hour: int) -> str:
    if 0 <= hour < 6:
        return "凌晨"
    elif 6 <= hour < 12:
        return "上午"
    elif 12 <= hour < 18:
        return "下午"
    else:
        return "晚上"


def refresh_reg() -> None:
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x1A

    SMTO_ABORTIFHUNG = 0x0002

    result = ctypes.c_long()
    SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
    SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                        u'Environment', SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))


def add_path(path: str) -> None:
    abs_path = os.path.abspath(path)
    path_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                              'Environment', 0, winreg.KEY_ALL_ACCESS)
    path_value = winreg.QueryValueEx(path_key, 'Path')
    if path_value[0].find(abs_path) == -1:
        winreg.SetValueEx(path_key, "Path", 0,
                          winreg.REG_EXPAND_SZ, path_value[0]+(";" if path_value[0][-1] != ";" else "")+abs_path+";")
        refresh_reg()


class state(Enum):
    ERROR = -1
    WAITING_FOR_LIVE_START = 0
    LIVE_STARTED = 1
    PROCESSING_RECORDS = 2
    UPLOADING_TO_BILIBILI = 3
    UPLOADING_TO_BAIDUYUN = 4

    def __str__(self):
        if self.value == -1:
            return "错误！"
        if self.value == 0:
            return "摸鱼中"
        if self.value == 1:
            return "正在录制"
        if self.value == 2:
            return "正在处理视频"
        if self.value == 3:
            return "正在上传至Bilibili"
        if self.value == 4:
            return "正在上传至百度网盘"

    def __int__(self):
        return self.value


def print_log(runner_list: list) -> str:
    tb = pt.PrettyTable()
    tb.field_names = ["TID", "平台", "房间号", "直播状态", "程序状态", "状态变化时间"]
    for runner in runner_list.values():
        tb.add_row([runner.native_id, runner.mr.bl.site_name, runner.mr.bl.room_id, "是" if runner.mr.bl.live_status else "否",
                    str(state(runner.mr.current_state.value)), datetime.datetime.fromtimestamp(runner.mr.state_change_time.value)])
    print(
        f"    DDRecorder  当前时间：{datetime.datetime.now()} 正在工作线程数：{threading.activeCount()}\n")
    print(tb)
    print("\n")


def get_words(txts, topK=5):
    seg_list = []
    for txt in txts:
        seg_list.extend(model(txt)[0])
    c = Counter()
    for x in seg_list:  # 进行词频统计
        if len(x) > 1 and x != '\r\n' and x != '\n':
            c[x] += 1
    try:
        return list(list(zip(*c.most_common(topK)))[0])
    except IndexError:
        return []


def initialize_config(
        config_dir: str,
        default: dict = {},
        reset: bool = False) -> dict:
    if not os.path.isfile(config_dir) or reset:
        save_config(config_dir, default)
        return default


def load_config(config_dir: str, default: dict={}, encoding: str='utf-8') -> dict:
    try:
        try:
            return yaml.safe_load(open(config_dir, 'r', encoding=encoding))
        except FileNotFoundError:
            return yaml.safe_load(open(config_dir + '.old', 'r', encoding=encoding))
    except BaseException:
        return initialize_config(config_dir, default, reset=True)


def save_config(config_dir: str, default: dict={}) -> None:
    try: os.replace(config_dir, config_dir + '.old', )
    except FileNotFoundError: pass 
    yaml.dump(default, open(config_dir, 'w'),)


def cell_stdout(cmd, silent=False, encoding=None):
    print('calling', cmd, 'in terminal:')
    with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                          universal_newlines=True, encoding=encoding) as p:
        if not silent:
            try:
                for i in p.stdout:  # .decode("utf-8"):
                    print(i, end='')
            except UnicodeDecodeError:
                # 锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷
                print('decode failed! but at least you have this eror message...')
        p.wait()
    return p.returncode

    
def bili_name_trim(fn, base, char_lim=75):
    file = fn[len(base) - len(os.path.splitext(base)[1]) + 1:]
    filename = file[:file.rfind('.')]
    fileext = file[len(filename):]
    '''

    line = [u'x', u'y', u'z', u'쭌', u'a']

    if any([re.search(u'[\u3131-\ucb4c]', x) for x in line[3:]]):
        print "found character"

    '''
    return filename[:char_lim] + fileext

def strip_medianame_out(outdir, media):
    mediab = os.path.basename(media)
    r = []
    for file in glob.glob(os.path.join(
        outdir, '*' + mediab[1:mediab.rfind('.')] + '*'
    )):
        if file == media:
            continue
        outfile = os.path.join(
            os.path.dirname(file),
            bili_name_trim(os.path.basename(file), mediab)
        )
        shutil.move(
            file,
            outfile
        )
        r.append(outfile)
    return r

def put_medianame_backin(filelists, media, shazamed='', nonshazamed=''):
    mediab = os.path.basename(media)
    mediab = mediab[:mediab.rfind('.')]
    r = []
    for file in filelists:
        if not os.path.isfile(file):
            continue
        if ' by ' in os.path.basename(file):
            outdir = shazamed if os.path.isdir(
                shazamed) else os.path.dirname(file)
        else:
            outdir = nonshazamed if os.path.isdir(
                nonshazamed) else os.path.dirname(file)
        outfile = os.path.join(
            outdir,
            mediab + '_' + os.path.basename(file))
        shutil.move(
            file,
            outfile
        )
        r.append(outfile)
    return r

def split_in_half(filename, length:str = None, run: bool = True):
    if not length:
        length = timestamp2sec(get_length(filename)) / 2
    cmds = [
        'ffmpeg -i "{}" {} -c:v copy -c:a copy "{}"'.format(
            filename,
            '-to {}'.format(str(length)),
            filename[:filename.rfind('.')] + "a" + filename[filename.rfind('.'):]),
        'ffmpeg -i "{}" {} -c:v copy -c:a copy "{}"'.format(
            filename,
            '-ss {} '.format(str(length)),
            filename[:filename.rfind('.')] + "b" + filename[filename.rfind('.'):]),

    ]
    if not run:
        print(';'.join(cmds))
        return
    import subprocess
    for i in cmds:
        c = subprocess.Popen(shlex.split(i))
        c.wait()
    os.remove(filename)

def url_filter(r: list, or_keywords:list=[], no_keywords: list = []) -> list:
    '''
    keep item in r if item has one of the or keywords
    '''
    r2 = []
    for i in r:
        if not (True in [x in i[0] for x in or_keywords]):
            continue
        if i in no_keywords:
            continue
        r2.append(i[1])
    return r2

FILTERS = {
    None: lambda r: [x[1] for x in r],
    'karaoke': lambda r: url_filter(r, or_keywords=['歌','唱', "Live", "LIVE", "live"]),
    '570': lambda r: url_filter(r, or_keywords=['歌','唱', "Live", "LIVE", "live","早台"], no_keywords=['唱完']),
    'moonlight': lambda r: url_filter(r, or_keywords=['歌','唱','黑听','猫猫头播放器']),
}

from difflib import SequenceMatcher as SM
from subprocess import Popen, PIPE
import time

def ytbdl(
        url: str,
        outdir: str,
        soundonly: str = ' -f bestaudio',
        aria: int = None,
        out_format: str = '[%(uploader)s] %(title)s %(upload_date)s.%(ext)s',
        additional_args: list = [],
        ) -> list:
    r = ''  # --restrict-filenames
    if os.path.isfile(url):
        batch_file = '--batch-file '
    else:
        batch_file = ''
    fname = None
    cmd = ['yt-dlp', url, '-o', os.path.join(outdir, "[%(uploader)s] %(title)s %(upload_date)s.%(ext)s")]
    if aria is not None: 
        cmd.append('--external-downloader')
        cmd.append('aria2c')
        cmd.append('--external-downloader-args')
        cmd.append('-x {} -s {} -k 1M'.format(str(aria), str(aria)))        
    passed_download = False
    while not passed_download:
        passed_download = True
        with Popen(cmd, stdout=PIPE,
                universal_newlines=True) as p:
            for line in p.stdout:
                print(line, end='')
                if '[download] Destination' in line:
                    fname = line[len('[download] Destination: '):-1]
                elif 'has already been downloaded' in line:
                    fname = line[len('[download] '):-
                                len(' has already been downloaded') - 1]
                elif '[Merger]' in line:
                    fname = line[len('[Merger] Merging formats into "'):-2]
                elif 'error' in line.lower():
                    passed_download = False
            if not passed_download: 
                logging.info('yt-dlp message log contained error, now repeating yt-dlp in 10 seconds:')
                time.sleep(10)
    if fname is None:
        raise Exception('no ytbdl resutls!')
    print('mathcing', fname)
    ext = fname[fname.rfind('.'):]
    r = []
    for i in glob.glob(os.path.join(
        os.path.dirname(fname),
        '*' + ext
    )):
        r.append([i, SM(isjunk=None, a=os.path.basename(
            fname), b=os.path.basename(i)).ratio()])
    return sorted(r, key=lambda x: x[1], reverse=True)[0][0]

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    import argparse
    parser = argparse.ArgumentParser(description='inaUploader')
    parser.add_argument(
        '--file',
        dest='file',
        type=str,
        help='watch sleep interval in seconds')
    parser.add_argument(
        '--timestamp',
        dest='timestamp',
        type=str,
        help='watch sleep interval in seconds')
    args = parser.parse_args()

    split_in_half(os.path.join(
        os.path.dirname(
        os.path.abspath(__file__)),
        'recorded',
        args.file), args.timestamp)