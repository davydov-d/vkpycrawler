'''
Dependencies: pip install vk==2.0.2
Compatible with VK API v5.52
Usage: python vkpycrawler.py -dir <dest_dir_full_path> -token <access_token>
To get access token, go to
https://oauth.vk.com/authorize?client_id=5810848&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=messages&response_type=token&v=5.52
'''
import json
import os
import sys
import time
import argparse
import logging
from urllib import request
from vk import API, Session


__author__ = 'ddavydov'

logger = logging.getLogger('vkpycrawler')
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

TIME_DELAY = 0.2  # seconds

argparser = argparse.ArgumentParser()
argparser.add_argument('-dir', required=True)
argparser.add_argument('-token', required=True)


class VKAPIWrapper(API):
    def __getattr__(self, item):
        if item in ['messages', 'users']:
            # workaround to avoid `too many requests` API error
            time.sleep(TIME_DELAY)
        return super().__getattr__(item)


class VKSessionWrapper(Session):
    def make_request(self, method_request, captcha_response=None):
        response = self.send_api_request(method_request,
                                         captcha_response=captcha_response)
        return json.loads(response.text)


class Worker(object):
    MESSAGES_PER_PAGE = 200
    PHOTOS_PER_PAGE = 200
    MEDIA_TYPE = 'photo'

    def __init__(self, dir, token, *args, **kwargs):
        self.dir = dir
        self.api = VKAPIWrapper(VKSessionWrapper(token))

    def _prepare_directory(self):
        if os.path.exists(self.dir):
            if not os.path.isdir(self.dir):
                raise Exception('%s is not a directory!' % self.dir)
        else:
            os.mkdir(self.dir)
        logger.info('Prepared directory')

    def _get_user_by_id(self, uids):
        return self.api.users.get(user_ids=uids)['response']

    def _scan_dialogues(self):
        logger.info('Getting list of dialogs..')
        offset = 0
        uids = []
        while offset <= len(uids):
            resp = self.api.messages.getDialogs(count=self.MESSAGES_PER_PAGE,
                                                offset=offset)
            offset += self.MESSAGES_PER_PAGE
            uids.extend([item['uid'] for item in resp['response'][1:]])
        return self._get_user_by_id(uids)

    def _scan_chats(self):
        # TODO: implement chat scan and fetch photos sent by user
        # TODO: as well as received by user
        return []

    def _get_photo_url(self, object: dict):
        ordered_keys = ['src_xxxbig', 'src_xxbig', 'src_xbig',
                        'src_big', 'src']
        for key in ordered_keys:
            if key in object.keys():
                return object[key]

    def _save_images(self, dest_dir, sources):
        logger.info('saving..')
        for url in sources:
            name = url.split('/')[-1]
            dest_file = os.path.join(dest_dir, name)
            if not os.path.exists(dest_file):
                request.urlretrieve(url, dest_file)

    def _fetch_files(self, peers_list):
        for item in peers_list:
            logger.info('Fetching files from {first_name} {last_name}..'
                        .format(**item))
            sources = []
            start_from = None
            dest_dir = os.path.join(self.dir,
                                    '{first_name}_{last_name}'.format(**item))
            while start_from != '':
                logger.info('getting photo urls(page {page_num})..'
                            .format(page_num=len(sources) // self.PHOTOS_PER_PAGE))
                kwargs = {'peer_id': item['uid'], 'media_type': self.MEDIA_TYPE,
                          'count': self.PHOTOS_PER_PAGE}
                if start_from:
                    kwargs.update({'start_from': start_from})
                resp = self.api.messages.getHistoryAttachments(**kwargs)
                if (type(resp) != dict or 'response' not in resp or
                    type(resp['response']) != dict): break
                sources.extend([self._get_photo_url(photo['photo'])
                                for photo in resp['response'].values()
                                if type(photo) == dict])
                if not start_from and sources:
                    if not os.path.exists(dest_dir) or not os.path.isdir(dest_dir):
                        os.mkdir(dest_dir)
                start_from = resp.get('next_from', '')
            self._save_images(dest_dir, sources)

    def run(self):
        self._prepare_directory()
        peers_list = self._scan_dialogues()
        peers_list.extend(self._scan_chats())
        self._fetch_files(peers_list)
        logger.info('Finished!')

if __name__ == '__main__':
    args = argparser.parse_args(sys.argv[1:])
    worker = Worker(args.dir, args.token)
    worker.run()
