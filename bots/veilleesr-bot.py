#!/usr/bin/env python
# veilleesr-bots/favretweet.py

import tweepy
import logging
from config import create_api
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

class FavRetweetListener(tweepy.StreamListener):
    def __init__(self, api):
        self.api = api
        self.me = api.me()

    def on_status(self, tweet):
        logger.info(f"Processing tweet id {tweet.id}")
        if tweet.in_reply_to_status_id is not None or \
            tweet.user.id == self.me.id:
            # This tweet is a reply or I'm its author so, ignore it
            return
        if not tweet.favorited:
            # Mark it as Liked, since we have not done it yet
            try:
                tweet.favorite()
            except Exception as e:
                logger.error("Error on fav", exc_info=True)
        if not tweet.retweeted:
            # Retweet, since we have not retweeted it yet
            try:
                tweet.retweet()
            except Exception as e:
                logger.error("Error on fav and retweet", exc_info=True)

    def on_error(self, status):
        logger.error(status)
        
class AutoTweet:
    def __init__(self, api, urlfilename):
        self.api = api
        urlfile = open("url-list.txt","r")
        self.urls = urlfile.readlines()
        
    def tweet(self, delay):
        i = 0
        while True:
            logger.info(f"Processing url {self.urls[i]}")
            try:
                self.api.update_status(self.urls[i])
            except Exception as e:
                logger.error("Error on autotweet", exc_info=True)               
            time.sleep(delay)
            i = (i+1) % len(self.urls)

def main():
    api = create_api()
    tweets_listener = FavRetweetListener(api)
    stream = tweepy.Stream(api.auth, tweets_listener)
    stream.filter(track=["#VeilleESR", "#DataESR"], languages=["fr","en"], is_async = True)
    
    autotweet = AutoTweet(api, "url-list.txt")
    autotweet.tweet(86400)
    
    

if __name__ == "__main__":
    main()
