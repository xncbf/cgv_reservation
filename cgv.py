import math
import os
import sys
import time
from systrace import trace

t1 = time.time()


try:
    import gi
    gi.require_version('Soup', '2.4')
    gi.require_version('Gtk', '3.0')
    gi.require_version('WebKit', '3.0')
    from gi.repository import GLib, Soup, Gtk, WebKit
except (ValueError, ImportError):
    packageName = 'gir1.2-webkit-3.0'
    print('Please install %s package' % packageName)
    print('$ sudo apt-get install %s' % packageName)
    sys.exit(1)

BASE_PATH = os.path.join(os.getenv('HOME'), ".cgv")
DATABASE_PATH = os.path.join(BASE_PATH, "database")
COOKIE_FILE = os.path.join(BASE_PATH, "cookie.txt")

from auth import *
from config import *

DEBUG = False
# 왕십리 2013년 4월 25일
START_URI = "http://m.cgv.co.kr/Theater/Theater.aspx?TheaterCd=%s&AreaCd=&PlayYMD=%s" % (THEATER_CODE, PLAY_YMD)
# START_URI = "http://m.cgv.co.kr/Theater/Special.aspx?TheaterType=02&TheaterCd=%s&PlayYMD=%s" % (THEATER_CODE, PLAY_YMD)

if DEBUG:
    START_URI = "http://m.cgv.co.kr/Theater/Special.aspx?TheaterType=02&TheaterCd=0074&PlayYMD=20130421"

HOME_URL = "http://m.cgv.co.kr/"
LOGIN_URI = "http://m.cgv.co.kr/Member/Login.aspx"
THEATER_URI = "http://m.cgv.co.kr/Theater/Special.aspx"
SEAT_URI = "http://m.cgv.co.kr/Reservation/Seat.aspx"
CHECK_URI = "http://m.cgv.co.kr/Reservation/CheckRsvMovie.aspx"
PAYTYPE_URI = "http://m.cgv.co.kr/MPG/Paytype.aspx"
SUCCESS_URI = "http://m.cgv.co.kr/MPG/Success.aspx"

SEAT_X = range(11, 23)
SEAT_Y = range(5, 19)

APP_NAME = "CGV"


def iter_dom(node_list, start=0):
    if node_list:
        length = node_list.get_length()
    else:
        length = 0
    for i in range(start, length):
        yield node_list.item(i)


class Timer:
    def __init__(self, duration, cb, *args):
        self.tag = GLib.timeout_add(duration, cb, *args)

    def __del__(self):
        GLib.source_remove(self.tag)


class Window(Gtk.Window, object):
    @trace()
    def __init__(self):
        object.__init__(self)
        Gtk.Window.__init__(self)
        scroll = Gtk.ScrolledWindow()
        view = WebKit.WebView()
        scroll.add(view)
        self.add(scroll)
        self.webview = view

        self.setup_webview(view)

        self.connect("destroy", Gtk.main_quit)
        view.connect("notify::load-status", self.handle_load_status)
        view.connect("script-alert", self.handle_alert)
        self.set_default_size(800, 600)
        self.load_uri(START_URI)

    def load_uri(self, uri):
        self.webview.load_uri(uri)

    @trace()
    def handle_alert(self, *args):
        # skip alert dialog
        return True

    @trace()
    def login(self):
        self.load_uri(LOGIN_URI)

    @trace()
    def handle_uri(self, uri):
        if '?' in uri:
            uri = uri.split('?', 1)[0]
        cb = {
            LOGIN_URI: self.handle_login,
            HOME_URL: self.handle_home,
            THEATER_URI: self.handle_theater,
            SEAT_URI: self.handle_seat,
            CHECK_URI: self.handle_check,
            PAYTYPE_URI: self.handle_pay_type,
            SUCCESS_URI: self.handle_success,
        }.get(uri)

        if cb:
            cb()
        else:
            print('unhandled uri: %s' % uri)

    @trace()
    def handle_load_status(self, webview, psepc):
        status = webview.get_load_status()
        if status == WebKit.LoadStatus.FINISHED:
            self.handle_uri(webview.props.uri)
        elif status == WebKit.LoadStatus.PROVISIONAL:
            self.reload_tag = None
        elif status == WebKit.LoadStatus.FAILED:
            self.load_uri(START_URI)

    @trace()
    def handle_login(self):
        dom = self.webview.get_dom_document()
        dom.get_element_by_id('Login_tbUserID').set_value(USERNAME)
        dom.get_element_by_id('Login_tbPassword').set_value(PASSWORD)
        dom.get_element_by_id('Login_cbRememberUserID').set_value('on')
        dom.get_element_by_id('Login_cbRememberPassword').set_value('on')
        dom.get_element_by_id('Login_ibLogin').click()

    @trace()
    def handle_home(self):
        self.load_uri(START_URI)

    @trace()
    def handle_theater(self):
        self.reload_tag = Timer(1000, self.load_uri, START_URI)

        dom = self.webview.get_dom_document()
        for movie_set in iter_dom(dom.query_selector_all("div[class='theater_movie_set']")):
            text = ''
            for title in iter_dom(movie_set.query_selector_all("div[class='tlt']")):
                text = title.get_text_content()
                if text.strip():
                    break
            # process IMAX only
            if not 'imax' in text.lower():
                continue

            timelist = movie_set.query_selector_all("li[class='list on']")
            for item in iter_dom(timelist):
                link = item.get_children().item(0)
                text = link.get_text_content()
                time, count = text.split()
                count = count[1:-1]
                print('%s %s %s' % (time, count, link))
                # FIXME
                link.click()
                break

    @trace()
    def handle_seat(self):
        self.reload_tag = Timer(1000, self.webview.reload)
        dom = self.webview.get_dom_document()
        COUNT_ID = 'dr_general_count'
        SCRIPT = """
            count = document.getElementById('%s');
            count.selectedIndex = %d;
            count.onchange();
        """ % (COUNT_ID, NUM_SEAT)
        self.webview.execute_script(SCRIPT)

        items = list(iter_dom(dom.get_elements_by_class_name('pointer available')))
        if not items:
            return

        CENTER_X = 16.5
        CENTER_Y = 6

        def get_xy(i):
            try:
                return int(i.get_attribute('x')), int(i.get_attribute('y'))
            except ValueError:
                return -1, -1

        def sort_seat(a, b):
            bx, by = get_xy(b)
            if (bx, by) == (-1, -1):
                return -1
            ax, ay = get_xy(a)
            if (ax, ay) == (-1, -1):
                return 1

            def dist(x, y):
                return math.sqrt((x - CENTER_X) ** 2 + (y - CENTER_Y) ** 2)

            ad = dist(ax, ay)
            bd = dist(bx, by)
            if ad < bd:
                return -1
            elif ad > bd:
                return 1
            return 0

        items.sort(sort_seat)
        if True:
            item = items[0]
            x, y = get_xy(item)
            if not x in SEAT_X:
                return
            if not y in SEAT_Y:
                return
            item.click()
            dom.get_element_by_id('ibSelectTicket').click()
            return

        # for test
        def do_something():
            for item in items[:8]:
                item.click()
                yield True
                item.click()
                yield True

        it = do_something()

        GLib.timeout_add(1000, it.next)

    @trace()
    def handle_check(self):
        dom = self.webview.get_dom_document()
        dom.get_element_by_id('ibPayment').click()

    @trace()
    def handle_pay_type(self):
        dom = self.webview.get_dom_document()
        card = dom.get_element_by_id('ibCard')
        if card:
            card.click()
            return
        cardtype = dom.get_element_by_id('ddlCardType')
        if not cardtype:
            return
        cardtype.set_value(CARDTYPE)

        for i, data in enumerate(CARDNUM.split()):
            cardno = dom.get_element_by_id('tbCardNo%d' % (i + 1))
            cardno.set_value(data)

        mm = dom.get_element_by_id('ddlCardMonth')
        mm.set_value(CARDVALID.split('/')[0])
        yy = dom.get_element_by_id('ddlCardYear')
        yy.set_value(CARDVALID.split('/')[1])

        ssn2 = dom.get_element_by_id('tbCardSsn2')
        ssn2.set_value(SSN.split('-')[1])

        passwd = dom.get_element_by_id('tbCardPwd')
        passwd.set_value(CARDPASS[:2])

        dom.get_element_by_id('ibCardPayment').click()

    @trace()
    def handle_success(self):
        print('payment checkout is done. Total time: %s sec' % (time.time() - t1))

    @trace()
    def setup_webview(self, webview):
        try:
            os.makedirs(BASE_PATH)
        except:
            pass
        session = WebKit.get_default_session()
        jar = Soup.CookieJarText.new(COOKIE_FILE, False)
        jar.set_accept_policy(Soup.CookieJarAcceptPolicy.ALWAYS)
        session.add_feature(jar)

        WebKit.set_web_database_directory_path(DATABASE_PATH)
        settings = webview.get_settings()
        settings.props.enable_page_cache = True
        settings.props.enable_default_context_menu = False
        # for speed up
        settings.props.auto_load_images = False
        settings.props.enable_dns_prefetching = True

        webview.set_settings(settings)


if __name__ == '__main__':
    win = Window()
    win.show_all()

    exchook = sys.excepthook


    def new_hook(type, value, traceback):
        if isinstance(value, KeyboardInterrupt):
            Gtk.main_quit()
            return
        return exchook(type, value, traceback)


    sys.excepthook = new_hook

    # it should raise KeyboardInterrupt
    GLib.timeout_add(500, lambda: True)

    Gtk.main()
