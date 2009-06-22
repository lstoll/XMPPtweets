from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.loader import get_template
from django.template import Context
from django.core.cache import cache
from app.models import *
import urllib
import urllib2
from math import floor
from time import time
from google.appengine.api import mail

def index(request):
  return render_to_response('index.html')

