# Copyright 2011 Google Inc. All Rights Reserved.

"""Simple X Window to notify when a remote JSON value has changed."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import logging
import json
import Queue
import os
import urllib2
import sys
import time
import threading
import traceback

# Wildcard imports makes baby jesus cry.
from Tkinter import *

THREAD_UNSAFE_TK = False
global_message_queue = Queue.Queue()
global_last_message = None


def window_close_handler():
  print 'Au revoir, mes amis!'
  sys.exit(1)


def add_msg(message, root_window=None, backup_notifier=None, **kwargs):
  """Add a message to the global queue for output."""
  global global_message_queue
  global global_last_message
  global THREAD_UNSAFE_TK

  logging.debug("add_msg: %s -> %s" % (message, root_window))

  if message != global_last_message:
    global_message_queue.put(message)

  if root_window:
    try:
      root_window.event_generate('<<msg>>', when='tail')
      logging.debug("Generated event")
      global_last_message = message
    # Tk thread-safety workaround #1
    except TclError:
      # If we aren't thread safe, we already assume this won't work.
      if not THREAD_UNSAFE_TK:
        print 'First TCL Error:'
        traceback.print_exc()
      try:
        backup_notifier(-1)
        THREAD_UNSAFE_TK = 1
      except:
        print 'Backup notifier failure:'
        traceback.print_exc()


class JsonBiffGui(object):

  def __init__(self, url, var, poll_seconds):
    self.url = url
    self.var = var
    self.poll_seconds = poll_seconds

  def run(self):
    self.root = Tk()
    app = MainWindow(self.root, self.url, self.var, self.poll_seconds)
    app.draw_window()
    self.root.bind('<<msg>>', app.message_handler)
    self.root.mainloop()

class MainWindow(Frame):
  def __init__(self, root, url, var, poll_seconds):
    Frame.__init__(self)
    self.root = root
    self.url = url
    self.var = var
    self.last_msg = None
    self.poll_seconds = poll_seconds
    self.root.protocol('WM_DELETE_WINDOW', window_close_handler)

  def draw_window(self):
    """Draws the user interface."""
    self.root.title('jsonbiff')
    #self.status = StringVar()
    self.outer_frame = Frame(self.root)
    self.outer_frame.grid(row=0, padx=6, pady=6)

    self.text = Text(self.outer_frame, height=1, width=10)
#    status = Label(outer_frame, text='...', textvariable=self.status)
#    status.grid(row=15, sticky=W, column=0)
    self.update_status('Starting.')
    self.start_job()

  def message_handler(self, unused_event):
    """Pinged when there is a new message in our queue to handle."""
    logging.debug("message_handler called. Queue: %s" %
                  global_message_queue.qsize())
    while global_message_queue.qsize():
      m = global_message_queue.get()
      self.update_status(m)

  def update_status(self, msg):
    if not isinstance(msg, list):
      self.send_notification(msg)
      msg = [msg]
    elif isinstance(self.last_msg, list):
      new = set(msg).difference(set(self.last_msg))
      self.send_notification('New Items\n\n' + '\n\n'.join(new))

    self.text.configure(height=len(msg))
    self.text.delete(1.0, END)
    for i, item in enumerate(msg):
      logging.warning('Inserting text [%s]: %s' % (i, item))
      self.text.insert(END, '%s\n' % item)
    self.text.pack()
    self.last_msg = msg

  def send_notification(self, msg):
    """gnome only?"""
    os.system('notify-send jsonbiff \"%s\"' % msg)

  def start_job(self):
    logging.info('starting job?')
    thread = WorkerThread(self.url, self.var, self.poll_seconds, root_window=self.root,
                          backup_notifier=self.message_handler)
    thread.start()

class WorkerThread(threading.Thread):

  def __init__(self, url, var, poll_seconds, root_window=None,
               backup_notifier=None):
    self.json_biff = JsonFetcher(url, var)
    self.poll_seconds = poll_seconds
    self.root_window = root_window
    self.backup_notifier = backup_notifier
    threading.Thread.__init__(self)

  def run(self):
    while True:
      logging.debug("Run loop")
      value = self.json_biff.get_value()
      logging.debug("Value: %s" % value)
      add_msg(value, root_window=self.root_window,
              backup_notifier=self.backup_notifier)
      time.sleep(self.poll_seconds)

class JsonFetcher(object):

  def __init__(self, url, var):
    self.url = url
    self.var = var

  def get_value(self):
    return self.evaluate(self.fetch())

  def fetch(self):
    return urllib2.urlopen(self.url).read()

  def evaluate(self, data):
    json_data = json.loads(data)
    logging.debug('data: %s' % json_data)
    if self.var in json_data:
      return json_data.get(self.var)
    else:
      logging.warning('%s not in %s' % (self.var, json_data))
      return None


if __name__ == '__main__':

  if len(sys.argv) != 3:
    print 'jsonbiff'
    print '--------'
    print './jsonbiff.py <url> <var>'
    sys.exit(1)

  url, expression = sys.argv[1:]
  if not os.getenv('DISPLAY', None):
    logging.critical('No DISPLAY variable set.')
    sys.exit(2)


  ui = JsonBiffGui(url, expression, poll_seconds=10)
  ui.run()