# MIT License
#
# Copyright (c) 2022 Julien Gossa
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

#!/usr/bin/env python


import logging
import time
from mastodon import Mastodon
import logging
import os
import json
from datetime import datetime

from os import path
import argparse
import datetime
import re
import urllib3
from bs4 import BeautifulSoup

import vbconfig
import mdconfig
from jorf import JORF


logger = logging.getLogger()

pm = urllib3.PoolManager()


def unshort_url(text):
    urls = re.findall("https://t.co/\w*", text)
    for url in urls:
        get = pm.request("GET", url, preload_content=False)
        long_url = get.geturl()
        get.release_conn()

        if long_url.startswith("https://twitter.com") and long_url.count("/") != 5:
            long_url = ""
        text = text.replace(url, long_url)

    return text



class APIMastodon:
    def __init__(self, client_id, client_secret, access_token, api_base_url, test=True):
        logger.info(f"Create mastodon api")
        self.api = Mastodon(
            client_id = client_id,
            client_secret = client_secret,
            access_token = access_token,
            api_base_url = api_base_url)

        self.user_id = self.api.me().id

        self.test = test


    def getVPost(self, toot):
        #print(toot)

        soup = BeautifulSoup(toot.content, features="lxml")
        vpost = {
            'text': re.sub("[^ ]https"," https",soup.get_text()),
            'card': None,
            'author': toot.account.url,
            'id' : toot.id,
            'url': toot.url,
            'images': [],
            'platform': "mastodon",
            'raw': toot }

        try:
            vpost['card'] = {
                'url': toot.card.url,
                'title': toot.card.title,
                'description': toot.card.description,
                'image': { 'url':toot.card.image } }
        except:
            pass

        for media in toot.media_attachments:
            if media.type == "image":
                vpost['images'].append({
                    'url':media.url,
                    'alt':media.description if media.description else ""})
        return vpost


    def getVeille(self, last_id = None):
        toots = self.api.timeline_hashtag("VeilleESR", since_id = last_id)

        veille = []
        for toot in toots:
            if toot.account.id != self.user_id:
                try:
                    if toot.account.username != "juliengossa":
                        veille.append(self.getVPost(toot))

                    self.api.status_reblog(toot.id)
                    self.api.account_follow(toot.account.id)
                    time.sleep(0.1)
                except Exception as e:
                    logger.error("Error on tagRetoot", exc_info=True)
                    pass

        return veille

    def post(self, text):
        if self.test:
            logger.info("Masto fake post "+text)
            return None

        try:
            self.api.status_post(text)
        except Exception as e:
            logger.error("Error on post toot", exc_info=True)


    def uploadImage(self, image):
        if 'url' in image:
            img = pm.request("GET", image['url'], preload_content=False)
            media = self.api.media_post(img, mime_type = img.headers['Content-Type'], description=image['alt'])
            img.release_conn()
        elif 'data' in image:
            media = self.api.media_post(image['data'], mime_type=image['content_type'], description=image['alt'])
        else:
            media = self.api.media_post(image['path'], mime_type='image/png', description=image['alt'])

        return media


    def postVPost(self, vpost, in_reply_to=None, visibility="public"):
        if self.test:
            logger.info("Masto fake vpost \""+vpost['text'][0:50]+"...\"")
            return "fakeid"

        text = vpost['text']
        if 'cardurl' in vpost:
            text = text +" "+ vpost['cardurl']
        try:
            text = text +" "+ vpost['card']['url']
        except:
            pass

        media_ids = []
        if 'images' in vpost:
            for image in vpost['images']:
                media = self.uploadImage(image)
                media_ids.append(media.id)

        # print("post on mastodon: "+vpost['text']+"\nirp: "+str(in_reply_to)+"\nmedias: "+str(media_ids))
        # return 1
        toot = self.api.status_post(
            status = text,
            in_reply_to_id = in_reply_to,
            media_ids = media_ids)

        return toot

    def postVThread(self, vthread):
        irp = None
        for vpost in vthread:
            toot = self.postVPost(vpost, in_reply_to = irp, visibility = "unlisted" if irp else "public")
            irp = toot

    def importVPost(self, vpost):
        if self.test:
            logger.info("Masto fake importvpost \""+vpost['text'][0:50]+"...\"")
            return "fakeid"

        toot = self.api.status_post(
            status="[#VeilleESR] "+vpost['card']['title']+"\n\n"+vpost['card']['url']+"\n\nVia "+vpost['url']
        )


    def deleteAllToots(self):
        if self.test:
            logger.info("Masto fake delete all toot")
            return None

        for m in self.api.timeline():
            print(m.get("id"))
            self.api.status_delete(m.get("id"))


if __name__ == "__main__":
    config = vbconfig.Config.load()
    apimasto = APIMastodon(
        config.get("MASTODON_ID"),
        config.get("MASTODON_SECRET"),
        config.get("MASTODON_ACCESS_TOKEN"),
        config.get("MASTODON_BASE_URL")
        )

    veille = apimasto.getVeille("111669063673926276")
    print(json.dumps(veille, indent=2, default=str))
