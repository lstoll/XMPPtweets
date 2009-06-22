from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.loader import get_template
from django.template import Context
from django.core.cache import cache
import urllib
import urllib2
from google.appengine.api import mail
import yaml
import os
import re
import logging
import base64
from google.appengine.api import urlfetch
from app import twitter
from datetime import datetime
from app.models import *
from google.appengine.api.urlfetch import DownloadError

HTML_ELEMENTS = re.compile(r'<(/?).*?>')

# This handles incoming requests
def index(request):
  userkey = request.REQUEST.get('userkey')
  
  if not userkey:
    return HttpResponse('No userkey specified. Fail.')
  
  network = request.REQUEST.get('network')
  # remove any markup from messages
  msg = HTML_ELEMENTS.sub('', request.REQUEST.get('msg'))
  step = int(request.REQUEST.get('step'))
  
  user = None
  # Try and find the user
  users = User.all().filter('userkey = ', userkey).fetch(1)
  for u in users:
    user = u
    
  if not user:
    user = User(userkey = userkey, network = network, twitter_username = '', twitter_password = '')
    db.put(user)
    
  # catch the resetme magic command
  if msg == 'resetme':
    user.twitter_username = ''
    user.twitter_password = ''
    user.login_step = 0
    user.logged_in = False
    user.put()


  # we try and create the message
  message = Message(
      userkey = userkey,
      network = network,
      msg = msg,
      step = step,
      user = user
  )   
  message.put()
  
  # we now have a user and a message. Let's work on it.
  if (user.twitter_username == '' or user.twitter_password == ''):
    # bad credentials. Set off the signup process - keep steps in mind
    
    if user.login_step == 0:
      send_message(user, "Welcome to the bot of awesome. Please enter your twitter username")
      user.login_step = 1
      user.put()
    elif user.login_step == 1:
      user.twitter_username = msg
      user.login_step = 2
      user.put()
      send_message(user, "Now please enter your password")
    elif user.login_step == 2:
      user.twitter_password = msg
      # validate
      if valid_login(user):
        # all good, save, and wait for the poller to kick in
        user.login_step = 3
        user.logged_in = True
        user.put()
        send_message(user, "Thanks! Your login has been successful")
        run_user_poll(user)
      else:
        user.login_step = 1
        user.twitter_password = ''
        user.put()
        # dont save, and reset to step 2
        send_message(user, "Your credentials were incorrect. Please try your login name again")
    else:
      # something went wrong - we shouldn't be here. reset.
      logging.error("Reached the else in the multistep login process - should never be here. user id: %s" % str(user.key()))
      user.login_step = 0
      user.twitter_username = ''
      user.twitter_password = ''
      user.put()
  # we have valid credentials in DB.
  else:
    # we have a setup user. Roll with the punches.
    #send_message(user, "I'd be listening to you commands, if I was coded that way.")
    
    logging.debug("Message is: %s" % msg.lower())
    
    if msg.lower() == '-help':
      send_message(user, "-stop , -pause , -play, d username msg, -fetch to manually chec, -search term or just tweet")
    elif msg.lower() == '-stop':
      user.stopped = True
      user.put()
      send_message(user, "You will receive nothing more from me until you send -play")
    elif msg.lower() == '-pause':
      user.paused = True
      user.stopped = False
      user.put()
      send_message(user, "You will only receive mentions and DMs from me until you send -play")
    elif msg.lower() == '-play':
      user.stopped = False
      user.paused = False
      user.put()
      send_message(user, "You will now receive all tweets, mentions and dms. Send -stop to stop all traffic, or -pause to halt tweets")
    elif msg.lower() == '-fetch':
      send_message(user, 'Fetching...')
      run_user_poll(user)
      send_message(user, 'Done.')
    else:
      # check if this is a DM
      words = msg.split(' ')
      first_word = words.pop(0).lower()
      if (first_word == 'd'):
        # this is a dm.
        touser = words.pop(0)
        # this is nasty - replace with join
        sendmessage = ''
        for word in words:
          sendmessage = sendmessage + word + ' '
        logging.debug("DM the following to %s: %s" % (touser, sendmessage))
        send_dm(user, touser, sendmessage)
      elif first_word == '-search':
        # this is nasty - replace with join
        term = ''
        for word in words:
          term = term + word + ' '
          
        search(user, term)
          
      else:
        # just a tweet
        logging.debug("Tweet the following: %s" % msg)
        send_tweet(user, msg)
      
  return HttpResponse()
  
def poller(request):
  # Get a list of user
  users = User.all().filter("logged_in =", True).fetch(1000)
  for user in users:
    run_user_poll(user)
    
  return HttpResponse()
  
  
  
  # watch for 401 errors across this. if one occurs, invalidate the user
  # (remove username and password), and put them back on the create 
  # account track.
  
# work out how to stash this in a global static in py.
config = yaml.load(open(os.path.dirname(__file__) + '/config.yaml'))
  
def send_message(user, message, async_rpc=None):
  url = "https://www.imified.com/api/bot/"
  
  form_fields = {
    "botkey": config['imbot_key'],    # Your bot key goes here.
    "apimethod": "send",  # the API method to call.
    "userkey": user.userkey,  # User Key to lookup with getuser.
    "msg" : message, #the message
  }
  
  base64string = base64.encodestring('%s:%s' % (config['imbot_username'], config['imbot_password']))[:-1]
  authString = 'Basic %s' % base64string
  
  form_data = urllib.urlencode(form_fields)
  
  if async_rpc:
    urlfetch.make_fetch_call(async_rpc, url=url, payload=form_data, method=urlfetch.POST, headers={'AUTHORIZATION' : authString})
  else:
    response = urlfetch.fetch(url=url, payload=form_data, method=urlfetch.POST, headers={'AUTHORIZATION' : authString}) 
    if response.status_code == 200:
      # all good
      logging.debug('IM send response (for message "%s") content: %s' % (message, response.content))
      return True
    else:
      logging.error('There was an error sending IM. status code: %s' % response.status_code)
      #self.response.out.write(response.headers)
      return False
  

###
#
# Twitter Interactions
#
##


def run_user_poll(user):
  # Send tweets first, followed by any mentions, then dms.
  # do this so the more important items are at the bottom
  # of the list, and are more visible.
  try:
    if not (user.paused or user.stopped):
      logging.debug('GET TWEETS')
      get_new_tweets(user)
    if not user.stopped:
      logging.debug("GET MENTION AND DMS")
      get_new_mentions(user)
      get_new_dms(user)

  except urllib2.HTTPError:
     user.twitter_username = ''
     user.twitter_password = ''
     send_message(user, "There was a login failure. Please enter your twitter username")
     user.login_step = 1
     user.logged_in = False
     user.paused = False
     user.stopped = False
     user.put()


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
  tweets =  api.GetFriendsTimeline(since_id=user.last_tweet_id)
  rpcs = []
  #Reverse the order, so newest is sent last
  for tweet in reversed(tweets):
    # save & send
    if tweet.id > user.last_tweet_id:
      user.last_tweet_id = tweet.id
    # save a copy
    db.put(Tweet(message=tweet.text, tid=tweet.id, fromusername=tweet.user.name, fromscreenname=tweet.user.screen_name, fromuserid=tweet.user.id, \
      created_at=datetime.fromtimestamp(tweet.created_at_in_seconds), user=user))
    # send the tweet
    rpc = urlfetch.create_rpc()
    send_message(user, "%s (%s): %s" % (tweet.user.name, tweet.user.screen_name, tweet.text),async_rpc=rpc)
    logging.debug('Appending RPC')
    rpcs.append(rpc)

  
  if wait_on_rpc_response(user, rpcs):
    # all good, save user. if it failed we don't save, so the next fetch
    # starts where it left off from
    user.put()


def wait_on_rpc_response(user, rpcs):
  "Takes a hash of RPC objects, and waits on their response"
  logging.debug("Array length: %d" % len(rpcs))
  try:
    for rpc in rpcs:
      # Todo - catch the download error in here, and retry.
      logging.debug("Waiting on rpc result")
      response = rpc.get_result()
      if response.status_code == 200:
        # all good
        logging.debug('IM send responsecontent: %s' % (response.content))
      else:
        logging.error('There was an error sending IM. status code: %s' % response.status_code)
  except DownloadError:
    logging.error('A download error occured...')
    send_message(user, "I'm sorry, I had an error. Please try again soon.")
    return False
  return True

def get_new_mentions(user):
  # find all tweets newer than user.last_mention_id
  api = get_api(user)
  mentions =  api.GetReplies(since_id=user.last_mention_id)
  rpcs = []
  #Reverse the order, so newest is sent last
  for mention in reversed(mentions):
    # save & send
    if mention.id > user.last_mention_id:
      user.last_mention_id = mention.id
    # save a copy
    db.put(Mention(message=mention.text, tid=mention.id, fromusername=mention.user.name, fromscreenname=mention.user.screen_name, fromuserid=mention.user.id, \
      created_at=datetime.fromtimestamp(mention.created_at_in_seconds), user=user))
    # send the tweet
    rpc = urlfetch.create_rpc()
    send_message(user, "Mentioned by %s (%s): %s" % (mention.user.name, mention.user.screen_name, mention.text),async_rpc=rpc)
    logging.debug('Appending RPC')
    rpcs.append(rpc)

  if wait_on_rpc_response(user, rpcs):
    # all good, save user. if it failed we don't save, so the next fetch
    # starts where it left off from
    user.put()


def get_new_dms(user):
  # find all dms newer than user.last_dm_id
  api = get_api(user)
  dms = api.GetDirectMessages(since_id=user.last_dm_id)
  # save to db
  # update user
  rpcs = []
  #Reverse the order, so newest is sent last
  for dm in reversed(dms):
    # save & send
    if dm.id > user.last_dm_id:
      user.last_dm_id = dm.id
    # save a copy
    db.put(DirectMessage(message=dm.text, tid=dm.id, fromusername=dm.sender_screen_name, fromuserid=dm.sender_id, \
      created_at=datetime.fromtimestamp(dm.created_at_in_seconds), user=user))
    # send the tweet
    rpc = urlfetch.create_rpc()
    send_message(user, "Direct Message from %s: %s" % (dm.sender_screen_name, dm.text),async_rpc=rpc)
    logging.debug('Appending RPC')
    rpcs.append(rpc)
  
  if wait_on_rpc_response(user, rpcs):
    # all good, save user. if it failed we don't save, so the next fetch
    # starts where it left off from
    user.put()

def send_tweet(user, message):
  api = get_api(user)
  api.PostUpdates(message)
  send_message(user, "Your tweet has been sent.")


def send_dm(user, to_name, message):
  try:
    api = get_api(user)
    api.PostDirectMessage(to_name, message)
    send_message(user, "Your direct message has been sent")
  except urllib2.HTTPError:
    send_message(user, "I couldn't send this message - maybe the user isn't following you?")
  
def search(user, term):
  api = get_api(user)
  results = api.GetSearch(term)
  rpcs = []
  for result in reversed(results):
    rpc = urlfetch.create_rpc()
    send_message(user, "Result for %s: %s - %s" % (term, result.user.screen_name, result.text),async_rpc=rpc)
    logging.debug('Appending RPC')
    rpcs.append(rpc)
    
  wait_on_rpc_response(user, rpcs)
    
def get_api(user):
    # @type api Api
    api = twitter.Api(username=user.twitter_username, password=user.twitter_password)
    api.SetXTwitterHeaders("xmpptweets", 'http://xmpptweets.appspot.com/static/twitter-client.xml', '0.1')
    return api