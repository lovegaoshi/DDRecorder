import os, re, json
from utils import load_config, save_config, cell_stdout, strip_medianame_out, put_medianame_backin, ytbdl
import logging
import sqlite3

keystamps = json.load(
    open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'config/biliWrapper.json',), 
        encoding='utf-8'))
PROCESSED_CONFIG_DIR = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'inaseged.yaml',)

def bilibili_upload(
        globbed,
        media_basename,
        source=None,
        description=None,
        episode_limit=180,
        route='kodo'):
    # because my ytbdl template is always "[uploader] title.mp4" I can extract 
    # out uploader like this and use as a tag:
    ripped_from = re.findall(r'\[.+\]', media_basename)[0][1:-1]
    if source is None:
        try:
            source = keystamps[ripped_from][0]
        except KeyError:
            raise KeyError('cant determine source url for this repost', ripped_from)
    if description is None:
        try:
            description = keystamps[ripped_from][1]
        except IndexError:
            description = '关注{}：{}'.format(
                ripped_from,
                source,)
    try:
        tags = keystamps[ripped_from][2]
    except IndexError:
        tags = [ripped_from]
    title = media_basename[:media_basename.rfind('.')][:60]
    # title rework: [歌切][海德薇Hedvika] 20220608
    title = '[{}] {}'.format(tags[0], os.path.splitext(media_basename)[0][-8:])
    title = media_basename[:media_basename.rfind('.')][:60]
    globbed = sorted(globbed)
    globbed_episode_limit = []
    for i in range(len(globbed) // episode_limit + 1):
        if globbed[i] == media_basename:
            continue
        globbed_episode_limit.append(
            globbed[i * episode_limit: (i + 1) * episode_limit])

    for i in range(len(globbed_episode_limit)):
        if i > 0:
            episode_limit_prefix = '_' + chr(97 + i)
        else:
            episode_limit_prefix = ''
        retry = 0
        cmd = [
                './biliup',
                'upload',
            ]
        for x in globbed_episode_limit[i]: cmd.append(x)
        cmd.append('--copyright=2')
        cmd.append('--desc={}'.format(description))
        cmd.append('--tid=31')
        cmd.append('--tag={}'.format(','.join(tags)))
        cmd.append('--title=[歌切]{}'.format(title[:60] + episode_limit_prefix))
        cmd.append('--source={}'.format(source))
        cmd.append('-l=' + route)

        while cell_stdout(cmd, encoding="utf-8") != 0:
            rescue = []
            for item in globbed_episode_limit[i]:
                if os.path.isfile(item):
                    rescue.append(item)
            globbed_episode_limit[i] = rescue
            retry += 1
            print('upload failed, retry attempt', retry)
            if retry > 5:
                raise Exception(
                    'biliup failed for a total of {} times'.format(
                        str(retry)))


def get_shazam(shazam_dict: dict, index: int):
    try:
        return '_' + shazam_dict[index]
    except KeyError:
        return ''


def ffmpeg(media: str, timestamps: list, shazam: list, executing = cell_stdout):
    '''recording is the file path; timestamps is owrking as expected,
    shazam is not; its onyl keeping the ones shazamed; we need to parse this a bit
    ''' 
    shazamed = {}
    for i in shazam:
        try:
            shazamed_index, filename = re.findall(r'.+_(\d+)_+(.+)\..+', i)[0]
            shazamed[int(shazamed_index)] = filename
        except:
            pass
    for index, i in enumerate(timestamps):
        executing(
            [
                'ffmpeg',
                '-i',
                media,
                '-c:v','copy','-c:a', 'copy',
                '-ss',
                i[0],
                '-to',
                i[1],
                os.path.join(
                    os.getcwd(), 
                    'recorded',
                    os.path.splitext(os.path.basename(media))[0] + "_" +
                    str(index).zfill(2) + 
                    get_shazam(shazamed, index) +
                    os.path.splitext(os.path.basename(media))[1]
                )
            ]
        )


class Biliup():
    def __init__(
        self,
        outdir: str,
        media: str,
        route: str = 'kodo',
        cleanup: bool = True,
        ):
        self.outdir = outdir
        self.media = media
        self.route = route
        self.cleanup = cleanup
        self.episode_limit = 180
    
    def run(self):
        outdir = self.outdir
        media = self.media
        stripped_media_names = strip_medianame_out(outdir, media)
        bilibili_upload(stripped_media_names, os.path.basename(media), source=None, episode_limit=self.episode_limit, route=self.route)
        print('finished stripping and uploading', media)
        # i always do not keep original stream
        os.remove(media)
        # for a router uploader, remove everything; i only have so much sapce!
        if self.cleanup:
            for i in stripped_media_names: os.remove(i)
        else: put_medianame_backin(stripped_media_names, media, shazamed=outdir, nonshazamed=r'D:\tmp\ytd\extract')

class Uploader():
    def __init__(self):
        pass

    def run(self):
        '''
        frist read file; 
        '''
        content = load_config(PROCESSED_CONFIG_DIR)
        content2 = {}
        for i in content:
            try:
                if 'http' in i: 
                    logging.info(('found routerup link of ', i, 'now downloading...'))
                    media = ytbdl(
                    i,
                    soundonly='',
                    outdir=os.path.join(os.getcwd(), 'recorded'), 
                    aria=8,
                )
                else:
                    media = os.path.join(os.getcwd(), 'recorded', i)
                if not os.path.isfile(media): 
                    logging.debug((i, ' does not exist on disk; skipped.'))
                    continue
                logging.info(('stripping and uploading', i))
                ffmpeg(
                    media,
                    content[i]['timestamps'],
                    content[i]['shazam'],
                )
                Biliup(
                    outdir=os.path.join(os.getcwd(), 'recorded'),
                    media=media,
                    cleanup=True,
                ).run()
            except KeyError:
                # stuck at shazam; save and come back later
                logging.warning((i, ' is missing shazam or inaseg; coming back later.'))
                content2[i] = content[i]
                raise
        save_config(PROCESSED_CONFIG_DIR, content2)

if __name__ == "__main__":
    import time
    from datetime import datetime
    logging.basicConfig(level=logging.DEBUG)
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='inaUploader')
    parser.add_argument(
        '--watch-interval',
        dest='interval',
        type=int,
        default=900,
        help='watch sleep interval in seconds')
    args = parser.parse_args()
    logging.info(('inaupload started'))
    while True:
        Uploader().run()
        logging.info(('uploader finished watching at', datetime.now().ctime(), 'now waiting for 30 min.'))
        if args.interval < 1: sys.exit(1)
        time.sleep(args.interval)
