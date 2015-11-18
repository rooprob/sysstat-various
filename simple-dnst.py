# Experiments in tornado + web and threaded dns

import datetime
import functools
import threading
import logging
import os.path
import pkg_resources
import re
import signal
import sys
import time
import random
from collections import defaultdict

import tornado.ioloop
import tornado.httpserver
import tornado.process
import tornado.web
from tornado.web import asynchronous

from tornado.options import define, options
from tornado.netutil import bind_sockets, bind_unix_socket

sys.path.append("/home/vagrant/dnspython.old")
from dns.resolver import Resolver
from dns.exception import *
import dns.name
import dns.version

define("port", default=2000, help="run on the given port", type=int)

class Application(tornado.web.Application):
    def __init__(self):

        handlers = [
            (r"/resolve/([a-z0-9\.\-]+)", DNSThreadHandler),
            (r"/app/([a-z0-9]+)/([a-z0-9\.\-]+)", TestAppHandler),
            (r"/hello", MainHandler),
            (r"/busyblock", BusyBlockHandler),
            (r"/longpoll/([0-9]+)", LongPollHandler),
            (r"/pingpong/([0-9]+)", PingPongHandler),
            (r"/blockcacheme", BlockingCacheHandler),
            (r"/batchcacheme", BatchCacheHandler),
            (r"/busy", BusyHandler),
            (r"/pump", PumpHandler),
            (r"/", HomeHandler),
        ]
        settings = dict(
            blog_title=u"Tornado Simple App",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            cookie_secret="11oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            autoescape=None,
        )
        tornado.web.Application.__init__(self, handlers, **settings)

class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db
    def adb(self):
        return self.application.adb
    def error(self, status, message):
        self.set_status(status)
        self.write(message)
        self.finish()


class MainHandler(BaseHandler):
    def get(self):
        self.write("Greeting from Puppet!")

class PumpHandler(BaseHandler):

    _p = None

    @tornado.web.asynchronous
    def get(self):
        logging.info("client opened")
        self.ping()
        #self._p = tornado.ioloop.PeriodicCallback(functools.partial(self.ping), 1000, tornado.ioloop.IOLoop.instance())
        self._p = tornado.ioloop.PeriodicCallback(self.ping, 300000, tornado.ioloop.IOLoop.instance())
        self._p.start()

    def ping(self):
        self.write("pump %s\n" % self)
        self.flush()

    def cleanup(self):
        self._p.stop()

    def on_connection_close(self):
        logging.info("client closed")
        self.cleanup()

    def on_finish(self):
        logging.info("finished")
        self.cleanup()


class PingPongHandler(BaseHandler):
    timeout = 60

    @tornado.web.asynchronous
    def get(self, timeout):
        self.timeout = int(timeout)
        self.write("handing ping pong GET request\n")
        self.flush()
        tornado.ioloop.IOLoop.instance().add_callback(functools.partial(self.ping))
        tornado.ioloop.IOLoop.instance().add_callback(functools.partial(self.done))

    def ping(self):
        self.write("ping (%d)\n" % self.timeout)
        self.flush()
        if self.timeout > 0:
            self.timeout = self.timeout - 1
            tornado.ioloop.IOLoop.instance().add_callback(functools.partial(self.ping))

    def done(self):
        #self.write("completed\n")
        #self.flush()a
        self.finish()

class BlockingCacheHandler(BaseHandler):

    cache = {}
    uuid = None

    def prepare(self):
        self.uuid = self.get_argument("uuid")

        if self.uuid not in self.cache:
            self.cache[self.uuid] = 1
            time.sleep(8)

    def get(self):
        self.write("Found in cache, yay!")

class CacheCore(object):

    __instance__ = None
    _pending = defaultdict(set)
    pending = defaultdict(set)
    key_map = {}
    REFILL_TIMEOUT = 4 * 1000 # ms
    NOT_FOUND = "__NOT_FOUND__"

    @classmethod
    def instance(cls):
        if cls.__instance__ is None:
            cls.__instance__ = cls()
        logging.info("returning CacheCore instance")

        return cls.__instance__

    def __init__(self, memcache=None, io_loop=None):
        self.memcache = memcache or defaultdict(dict)
        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()

        self._pending = defaultdict(set)

        tornado.ioloop.PeriodicCallback(
            self._fill, self.REFILL_TIMEOUT, self.io_loop).start()

        logging.info("Initialized CacheStore < %s, %s", self.memcache, self.io_loop)

    def get(self, uuid):
        if uuid in self.key_map:
            return self.key_map[uuid]
        else:
            return None

    def add_pending(self, uuid, callback):
        logging.info("adding pending callback %s for uuid %s" % (callback, uuid))
        self._pending[uuid].add(callback)

    def remove_pending(self, uuid, callback):
        logging.info("remove pending callback %s for uuid %s" % (callback, uuid))
        callbacks = self._pending[uuid]
        if callback in callbacks:
            logging.info("removed callback: %s" % callback)
            callbacks.remove(callback)
        del self._pending[uuid]
        logging.info("inside remove_pending with %d" % len(self._pending))

    def _fill(self):
        raise Exception("fill me")

class MyCache(CacheCore):

    def _fill(self):
        if not self._pending:
            return

        logging.info("inside _fill with %s %d" % (self._pending, len(self._pending)))
        self.pending = self._pending
        self._pending = defaultdict(set)

        for uuid in self.pending:
            self.key_map[uuid] = self.NOT_FOUND

        try:
            logging.info("filling %d caches", len(self.pending))

            # XXX Test with random data
            for x in self.key_map.keys():
                self.key_map[x] = random.randint(0,100)
            logging.info("long task taking ...")
            time.sleep(2)

            # schedule the outrun
            for callbacks in self.pending.itervalues():
                for callback in callbacks:
                    logging.info("dispatching callbacks %s" % callback)
                    self.io_loop.add_callback(callback)

        except Exception:
            logging.exception("Unexpected Error when filling aes key cache")

class MyAsyncCacheHandler(BaseHandler):

    CACHE_MISS_LIM = 3
    cache = None
    uuid = None
    callback = None

    def prepare(self):
        self.cache = MyCache.instance()
        self.uuid = self.get_argument("uuid")

    @classmethod
    def async_expensive(cls, method):
        @functools.wraps(method)
        @tornado.web.asynchronous
        def wrapper(self, *args, **kwargs):
            self.callback = None
            self._expensive(0, lambda: method(self, *args, **kwargs))
        return wrapper

    def _expensive(self, count, callback):
        key = self.cache.get(self.uuid)
        if key is None:
            logging.info("cache miss for %s with count %d" % (self.uuid, count))
            if count < self.CACHE_MISS_LIM:
                self.callback = lambda: self._expensive(count + 1, callback)

                self.cache.add_pending(self.uuid, self.callback)
            else:
                self.error(500, "Cache fill timedout for uuid %s" % self.uuid)

        elif key == self.cache.NOT_FOUND:
            self.error(400, "expensive failed, not exist!")

        else:
            logging.info("cache hit! [%s] for %s %s" % (key, self.uuid, callback))
            callback()

    def cleanup(self):
        logging.info("cleaning up for %s" % self.uuid)
        self.cache.remove_pending(self.uuid, self.callback)

    def on_finish(self):
        logging.info("finished with %s" % self.uuid)
        self.cleanup()

    def on_connection_close(self):
        self.on_finish()


class BatchCacheHandler(MyAsyncCacheHandler):

    @MyAsyncCacheHandler.async_expensive
    def get(self):
        logging.info("processing get....")
        self.uuid = self.get_argument("uuid")
        self.write("handing GET request for uuid %s\n" % self.uuid)
        self.flush()
        self.finish()

class xxxBatchCacheHandler(BaseHandler):

    cache = {}
    waiting_lookups = set([])
    uuid = None
    io_loop = None
    tries = {}
    __rw = None
    def prepare(self):

        if self.__rw is None:
            # XXX no need to add too many of these; just this one one more in
            # this + 4 seconds.
            logging.info("starting resolve_waiting")
            io_loop = tornado.ioloop.IOLoop.instance()
            self.__rw = tornado.ioloop.PeriodicCallback(self.resolve_waiting, 4000, io_loop)
            self.__rw.start()

        self.uuid = self.get_argument("uuid")

        if self.uuid not in self.cache:
            self.waiting_lookups.add(self.uuid)
            logging.info("adding %s to waiting lookup, scheduling checkout" % self.uuid)

    def resolve_waiting(self):
        if len(self.waiting_lookups) > 0:
            # XXX lock adding to waiting_lookups, or retry three times
            my_waiting = set()
            [ my_waiting.add(x) for x in self.waiting_lookups ]
            logging.info("resolve_waiting: following uuids %s" % my_waiting)
            # XXX implement lookupa
            for x in my_waiting:
                logging.info("adding to cache %s" % x)
                self.cache[x] = 1
                self.waiting_lookups.remove(x)
            # XXX fake blocking lookup
            logging.info("this bit takes ages.....")
            time.sleep(4)
            logging.info("... done")
        else:
            logging.info("resolve_waiting: no further waiting!")

    @tornado.web.asynchronous
    def get(self):
        self.io_loop = tornado.ioloop.IOLoop.instance()
        if self.uuid not in self.cache:
            self.tries[self.uuid] = 3
            logging.info("get() for %s not in cache, retry %d" % (self.uuid, self.tries[self.uuid]))
            self._timeout = tornado.ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=8), functools.partial(self.complete_get, self.uuid))
        else:
            logging.info("get() completing for %s" % self.uuid)
            tornado.ioloop.IOLoop.instance().add_callback(functools.partial(self.complete_get, self.uuid))

    def cleanup_cache(self, uuid):
        del(self.tries[uuid])

    def complete_get(self, uuid):
        if uuid not in self.tries or self.tries[uuid] == 0:
            # cleanup cache
            logging.info("failed for uuid %s" % uuid)
            self.cleanup_cache(uuid)

            self.set_status(408)
            self.write("Sorry, but we didn't work")
            self.finish()

        elif uuid not in self.cache:
            self.tries[uuid] -= 1
            logging.info("get() for %s not in cache, retry %d" % (uuid, self.tries[uuid]))
            logging.info("adding %s (tries %d) to waiting lookup, scheduling checkout" % (uuid, self.tries[uuid]))
            self._timeout = tornado.ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=8), functools.partial(self.complete_get, self.uuid))
        else:
            self.write("handing GET request for uuid %s\n" % uuid)
            self.finish()


class BusyBlockHandler(BaseHandler):
    def get(self):
        time.sleep(600)
        self.write("I was a busy blocker")

class BusyHandler(BaseHandler):

    @tornado.web.asynchronous
    def get(self):
        self.thread = threading.Thread(target=self.perform, args=(self.on_callback,))
        self.thread.start()

        self.write("handing busy GET request\n")
        self.flush()

    def on_callback(self, output):
        logging.info('on_callback() %s' % output)

        self.write("Thread complete %ss\n" % (output))
        self.finish()

    def perform(self, callback):
        try:
            sleep_time = 600
            time.sleep(sleep_time)
            output = sleep_time
        except Exception as ex:
            logging.error("perform() exception: %s" % ex)
            output = ex
        tornado.ioloop.IOLoop.instance().add_callback(functools.partial(callback, output))

class LongPollHandler(BaseHandler):

    TIMEOUT = 35

    @tornado.web.asynchronous
    def get(self, timeout):
        self.TIMEOUT = int(timeout)
        self._timeout = tornado.ioloop.IOLoop.instance().add_timeout(
            datetime.timedelta(seconds=self.TIMEOUT), self.on_timeout)

        self.write("handing long poll GET request\n")
        self.flush()

    def on_finish(self):
        """
        Clean up:
            1. Unregister tornado timeout callback
            2. Unregister ping_sockets device callback
        """
        if hasattr(self, '_timeout'):
            tornado.ioloop.IOLoop.instance().remove_timeout(self._timeout)

        super(LongPollHandler, self).on_finish()

    def on_timeout(self):
        self.set_status(408)
        self.write("Long poll command completed after %d seconds" % self.TIMEOUT)
        self.finish()


class HomeHandler(BaseHandler):

    def get(self):
        self.write("homepage")

class TestAppHandler(BaseHandler):

    def get(self, which, domain):

        timeout = 30

        if which == 'eval':
            # code from activation/domain.py line 244
            res = evalLegitMailHostForDomainLikelihood(domain, "m.google.com", timeout)
        logging.info("result was %s" % res)
        self.write("result was %s\n" % res)

class DNSThreadHandler(BaseHandler):

    def resolve(self, name, rrtype):
        domain = dns.name.from_text(name)
        dnsResolver = Resolver()
        dnsResolver.lifetime = 5
        # just an example
        result = ''
        try:
            answers = dnsResolver.query(domain, rrtype)
            for answer in answers:
                if rrtype == 'MX':
                    result = answer.exchange
                    logging.debug('%s is %s' % (rrtype, result))
                else:
                    raise Exception("unsupported type!")
        except DNSException as ex:
            logging.error("resolve() DNSException: %s" % ex.__class__)
            raise Exception(ex.__class__)

        except Exception as ex:
            logging.error("resolve() exception: %s" % ex)
            raise ex
        return result

    def perform(self, name, callback):
        try:
            output = self.resolve(name, 'MX')
        except Exception as ex:
            logging.error("perform() exception: %s" % ex)
            output = ex
        tornado.ioloop.IOLoop.instance().add_callback(functools.partial(callback, output))

    def initialize(self):
        self.thread = None

    @tornado.web.asynchronous
    def get(self, name):
        self.thread = threading.Thread(target=self.perform, args=(name, self.on_callback,))
        self.thread.start()

        self.write("handing GET request with name: %s\n" % name)
        self.flush()

    def on_callback(self, output):
        logging.info('on_callback() %s' % output)
        self.write("Thread output: %s\n" % output)
        self.finish()

def _log_blocking(arg1, arg2):
    logging.info("_log_blocking was fired! %s %s" % (arg1, arg2))


def main():
    logging.basicConfig()
    #logging.disable("INFO")
    tornado.options.parse_command_line()

    ioloop = tornado.ioloop.IOLoop.instance()
    # XXX must create new ports
    # tornado.process.fork_processes(5, max_restarts=100)

    dnspython_version = dns.version.version
    logging.warn("dnspython version %s" % dnspython_version)

    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)

    unix_socket = bind_unix_socket("/tmp/fdserver.sock", mode=0777, backlog=10000)
    http_server.add_socket(unix_socket)
    # Trigger timeout - will cause the blocking process to die.
    # ioloop.set_blocking_signal_threshold(2, _log_blocking)
    # ioloop.set_blocking_log_threshold(2)
    ioloop.start()

if __name__ == "__main__":
    main()
