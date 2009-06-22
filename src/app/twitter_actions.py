from app import twitter
import urllib2
from app.views_bot import *
import logging
from datetime import datetime


def run_user_poll(user):
  # try:
    #get_new_dms(user)
    #get_new_mentions(user)
    get_new_tweets(user)
  
  # except urllib2.HTTPError:
  #     user.twitter_username = ''
  #     user.twitter_password = ''
  #     send_message(user, "There was a login failure. Please enter your twitter username")
  #     user.login_step = 1
  #     user.logged_in = False
  #     user.put()


# ON ERRORS - 
# Reset session
# Send username promp, and set to step 2 - so username is read.

def valid_login(user):
  api = get_api(user)
  try:
   api.GetFriends()
   return True
  except urllib2.HTTPError:
    # todo - handle other codes.
    return False
    
def get_new_tweets(user):
  # Find all tweets newer than user.last_tweet_id and return
  # for now, keep the default max (20)
  # later, maybe keep polling all to keep above this.  
  api = get_api(user)
  tweets =  api.GetUserTimeline(since_id=user.last_tweet_id)
  rpcs = []
  for tweet in tweets:
    # save & send
    if tweet.id > user.last_tweet_id:
      user.last_tweet_id = tweet.id
    # save a copy
    db.put(Tweet(message=tweet.text, tid=tweet.id, fromusername=tweet.user.name, fromuserid=tweet.user.id, \
      created_at=datetime.fromtimestamp(tweet.created_at_in_seconds), user=user))
    # send the tweet
    rpc = urlfetch.create_rpc()
    send_message(user, "%s - %s" % (tweet.user, tweet.text),async_rpc=rpc)
    
  user.put()
  for rpc in rpcs:
    rpc.wait()
    
  # save to db
  # update user
  #return tweets
  
def get_new_mentions(user):
  # find all tweets newer than user.last_mention_id
  api = get_api(user)
  mentions =  api.GetUserTimeline(since_id=user.last_mention_id)
  # save to db
  # update user
  return mentions

  
def get_new_dms(user):
  # find all dms newer than user.last_dm_id
  api = get_api(user)
  dms = api.GetDirectMessages(since_id=user.last_tweet_id)
  # save to db
  # update user
  return dms
  
def send_tweet(user, message):
  # send a tweet to 
  return
  
def send_dm(user, to_name, message):
  # send a dm to to_name
  return
  
  
  
def get_api(user):
  return twitter.Api(username=user.twitter_username, password=user.twitter_password)