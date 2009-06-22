from google.appengine.ext import db

class User(db.Model):
  "Represents a user of the system"
  twitter_username = db.StringProperty(default='')
  twitter_password = db.StringProperty(default='')
  userkey = db.StringProperty()
  network = db.StringProperty()
  last_tweet_id = db.IntegerProperty(default=0)
  last_dm_id = db.IntegerProperty(default=0)
  last_mention_id = db.IntegerProperty(default=0)
  login_step = db.IntegerProperty(default=0)
  logged_in = db.BooleanProperty(default=False)
  paused = db.BooleanProperty(default=False)
  stopped = db.BooleanProperty(default=False)
  # tracking
  date_added = db.DateTimeProperty(auto_now_add=True)
  
class Message(db.Model):
  "Represents an IM message from the IMified service"
  userkey = db.StringProperty(required=True)
  network = db.StringProperty(required=True)
  msg = db.StringProperty(required=True)
  step = db.IntegerProperty(required=True)
  user = db.ReferenceProperty(User)
  # tracking
  date_added = db.DateTimeProperty(auto_now_add=True)

class Tweet(db.Model):
  "Represents a tweet"
  message = db.StringProperty(required=True,multiline=True)
  fromusername = db.StringProperty(required=True)
  fromuserid = db.IntegerProperty(required=True)
  fromscreenname = db.StringProperty(required=True)
  tid = db.IntegerProperty(required=True)
  created_at = db.DateTimeProperty(required=True)
  # tracking
  user = db.ReferenceProperty(User)
  date_added = db.DateTimeProperty(auto_now_add=True)
  
class Mention(db.Model):
  "Represents a tweet"
  message = db.StringProperty(required=True,multiline=True)
  fromusername = db.StringProperty(required=True)
  fromscreenname = db.StringProperty(required=True)
  fromuserid = db.IntegerProperty(required=True)
  tid = db.IntegerProperty(required=True)
  created_at = db.DateTimeProperty(required=True)
  # tracking
  user = db.ReferenceProperty(User)
  date_added = db.DateTimeProperty(auto_now_add=True)
    
class DirectMessage(db.Model):
  "Represents a tweet"
  message = db.StringProperty(required=True,multiline=True)
  fromusername = db.StringProperty(required=True)
  fromuserid = db.IntegerProperty(required=True)
  tid = db.IntegerProperty(required=True)
  created_at = db.DateTimeProperty(required=True)
  # tracking
  user = db.ReferenceProperty(User)
  date_added = db.DateTimeProperty(auto_now_add=True)
  

# class Carrier(db.Model):
#     name = db.StringProperty(default = '')
#     apn = db.StringProperty()
#     username = db.StringProperty(default = '')
#     password = db.StringProperty(default = '')
#     listed = db.BooleanProperty(default = False)
# 
# class MessageSent(db.Model):
#     to = db.EmailProperty()
#     when = db.DateTimeProperty(auto_now_add=True)
#     carrier = db.ReferenceProperty(Carrier)
#     
# class BundleDownloaded(db.Model):
#     ip = db.StringProperty()
#     ua = db.StringProperty()
#     when = db.DateTimeProperty(auto_now_add=True)
#     carrier = db.ReferenceProperty(Carrier)
