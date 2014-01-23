#!/usr/bin/env python
#!--encoding:utf-8--

from gevent import monkey
monkey.patch_all()

import os
import sys
import xmlrpclib
import time
from datetime import datetime
from datetime import timedelta
import urllib
import threading
from Queue import Queue

import gevent
from gevent import queue
from gevent import Timeout

from api.mongo_api import MongoExecuter
from api.mongo_driver import db_handler
import XenAPI
import settings
from logger import logger
from convert import converter


gs = []
thread_queue = Queue()
global_xenserver_conn = {}


def connect_to_xenserver():
    for host in settings.XEN:
        with Timeout(1.0):
            try:
                proxy = xmlrpclib.ServerProxy("http://" + host[0])
                result = proxy.session.login_with_password(host[1], host[2])
                session_id = result['Value']
                global_xenserver_conn[host[0]] = session_id
            except Exception, e:
                logger.exception(e)
                
connect_to_xenserver()


class TimeRange(object):
    def __init__(self):
        pass
    
    def get_now(self):
        return datetime.now()
    
    def ten_minutes_ago(self):
        now = self.get_now()
        return self.make_timestamp(now - timedelta(seconds=5))
    
    def two_hours_ago(self):
        now = self.get_now()
        return self.make_timestamp(now - timedelta(seconds=7200))
    
    def one_week_ago(self):
        now = self.get_now()
        return self.make_timestamp(now - timedelta(days=7))
    
    def one_year_ago(self):
        now = self.get_now()
        return self.make_timestamp(now - timedelta(days=365))
    
    def make_timestamp(self, t):
        return int(time.mktime(t.timetuple()))


class XenserverManager(object):
    def __init__(self, queue):
        self.queue = queue
    
    def all_hosts(self):
        for xen_host in settings.XEN:
            yield xen_host[0], xen_host[1], xen_host[2]
    
    def get_session_id(self, host):
        session_id = global_xenserver_conn.get(host, None)
        return session_id
    
    def make_10m_perf_url(self):
        while 1:
            try:
                for xen_host in self.all_hosts():
                    tr = TimeRange()
                    ten_minutes_ago = tr.ten_minutes_ago()
                    session_id = self.get_session_id(xen_host[0])
                    url_origin = "http://%s/rrd_updates?session_id=%s&start=%s&cf=AVERAGE"
                    url_formated = url_origin % (xen_host[0], session_id, ten_minutes_ago)
                    item = "10m", url_formated
                    self.queue.put(item)
            except Exception, e:
                logger.exception(e)
            gevent.sleep(5)
    
    def make_2h_perf_url(self):
        while 1:
            try:
                for xen_host in self.all_hosts():
                    tr = TimeRange()
                    two_hours_ago = tr.two_hours_ago()
                    session_id = self.get_session_id(xen_host[0])
                    url_origin = "http://%s/rrd_updates?session_id=%s&start=%s&cf=AVERAGE"
                    url_formated = url_origin % (xen_host[0], session_id, two_hours_ago)
                    item = "2h", url_formated
                    self.queue.put(item)
            except Exception, e:
                logger.exception(e)
            gevent.sleep(60)
            
    def make_1w_perf_url(self):
        while 1:
            try:
                for xen_host in self.all_hosts():
                    tr = TimeRange()
                    one_week_ago = tr.one_week_ago()
                    session_id = self.get_session_id(xen_host[0])
                    url_origin = "http://%s/rrd_updates?session_id=%s&start=%s&cf=AVERAGE"
                    url_formated = url_origin % (xen_host[0], session_id, one_week_ago)
                    item = "1w", url_formated
                    self.queue.put(item)
            except Exception, e:
                logger.exception(e)
            gevent.sleep(3600)
        
    def make_1y_perf_url(self):
        while 1:
            try:
                for xen_host in self.all_hosts():
                    tr = TimeRange()
                    one_year_ago = tr.one_year_ago()
                    session_id = self.get_session_id(xen_host[0])
                    url_origin = "http://%s/rrd_updates?session_id=%s&start=%s&cf=AVERAGE"
                    url_formated = url_origin % (xen_host[0], session_id, one_year_ago)
                    item = "1y", url_formated
                    self.queue.put(item)
            except Exception, e:
                logger.exception(e)
            gevent.sleep(86400)


def process():
    while 1:
        item = thread_queue.get()
        if item == "quit":
            logger.debug("Server exit...")
            return
        else:
            logger.info("got item")


def http_getter(url):
    """
        在1.0内获取GET URL的数据，否则超时
        使用Timeout类，否则是socket的默认超时
    """
    action_type = url[0]
    url = url[1]
    try:
        with Timeout(10.0):
            result = urllib.urlopen(url)
            if result.code == 401:
                logger.error("Maybe the session has expired.")
                connect_to_xenserver()
                return
            if result.code != 200:
                logger.error("Error in get data: HTTP %d" % result.code)
                return
            data = result.read()
            logger.info("action: %s, got data %dKB" % (action_type, len(data)/1024.0))
            result = converter(data)
            thread_queue.put(result)
    except Exception, e:
        logger.exception(e)


def spawner(queue):
    while 1:
        item = queue.get()
        if item == "quite":
            return
        else:
            gs.append(gevent.spawn(http_getter, item))


if __name__ == '__main__':
    #TODO: 设置监视greenlet
    process_thread = threading.Thread(target=process, args=())
    process_thread.start()
    
    q = queue.Queue()
    xen_manager = XenserverManager(q)
    gs.append(gevent.spawn(xen_manager.make_10m_perf_url))
    gs.append(gevent.spawn(xen_manager.make_2h_perf_url))
    gs.append(gevent.spawn(xen_manager.make_1w_perf_url))
    gs.append(gevent.spawn(xen_manager.make_1y_perf_url))
    g_spawner = gevent.spawn(spawner, q)
    gs.append(g_spawner)
    try:
        g_spawner.run()
    except KeyboardInterrupt:
        thread_queue.put("quit")
        q.put("quit")
        gevent.killall(gs, block=False, timeout=3)
    
