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

BASE_PATH = os.path.join(os.getenv('HOME'), ".megabox")
DATABASE_PATH = os.path.join(BASE_PATH, "database")
COOKIE_FILE = os.path.join(BASE_PATH, "cookie.txt")

from mauth import *

START_URI = "http://m.megabox.co.kr/Mobile/Theater/Default.aspx"

DATE = '2013-04-24'
M2_IMG = "/mobileImages/common/ico_M2%EA%B4%80_on.gif"
TITLE = "에반"
SEAT_X = range(8, 16 + 1)
SEAT_Y = range(4, 12 + 1)
DEBUG = False
if DEBUG:
    DATE = '2013-04-21'
    TITLE = "ATMOS"

HOME_URL = START_URI
LOGIN_URI = "http://m.megabox.co.kr/Mobile/Login/Login.aspx"
THEATER_URI = "http://m.megabox.co.kr/Mobile/Theater/TheaterDetail.aspx"
THEATER_TIMETABLE = "http://m.megabox.co.kr/Mobile/Theater/ajaxTheaterTimeTableList.aspx"
TICKET_URI = "http://m.megabox.co.kr/Mobile/Reservation/rsvBuyTickets.aspx"
SEAT_URI = "http://m.megabox.co.kr/Mobile/Reservation/rsvSelectSeats.aspx"
PAYTYPE_URI = "http://m.megabox.co.kr/Mobile/Reservation/rsvPaymentTickets.aspx"
SUCCESS_URI = "http://m.megabox.co.kr/Mobile/MyPage/Default.aspx"


APP_NAME = "Megabox"


def iter_dom(node_list, start=0):
    length = node_list.get_length()
    for i in range(start, length):
        yield node_list.item(i)


class Timer:
    def __init__(self, duration, cb, *args):
        self.tag = GLib.timeout_add(duration, cb, *args)

    def __del__(self):
        GLib.source_remove(self.tag)


class Connect:
    def __init__(self, gobject, signal, cb, *args):
        self.gobject = gobject
        self.tag = gobject.connect(signal, cb, *args)

    def __del__(self):
        self.gobject.disconnect(self.tag)


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
            TICKET_URI: self.handle_ticket,
            SEAT_URI: self.handle_seat,
            PAYTYPE_URI: self.handle_pay_type,
            SUCCESS_URI: self.handle_success,
        }.get(uri)

        if cb:
            print('handle uri: %s' % uri)
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
        dom.get_element_by_id('userid').set_value(USERNAME)
        dom.get_element_by_id('passwd').set_value(PASSWORD)
        SCRIPT = """memberLogin()"""
        self.webview.execute_script(SCRIPT)

    @trace()
    def handle_home(self):
        dom = self.webview.get_dom_document()
        area = dom.query_selector("dl[class='ingCnList wideList']")
        link = area.query_selector("a[href='']")
        link.click()
        theater = dom.query_selector("a[href='#1351#001003#코엑스#10#서울']")
        theater.click()

    @trace()
    def handle_theater(self):
        self.reload_tag = Timer(3000, self.webview.reload)

        SCRIPT = """
            date = document.querySelector("select[id='theaterplaydate']")
            date.value = '%s'
            goTheaterPlaydate(date)""" % DATE
        self.webview.execute_script(SCRIPT)
        self.select_tag = Connect(self.webview,
                                  'resource-load-finished',
                                  self.select_theater)

    def reset_seat(self):
        self.webview.execute_script("""goSelectPerson()""")

    @trace()
    def select_theater(self, webview, webframe, resource):
        uri = resource.get_uri()
        if uri != THEATER_TIMETABLE:
            return
        self.reload_tag = None
        self.select_tag = None

        dom = self.webview.get_dom_document()
        for item in iter_dom(dom.query_selector_all("div[class='seatCountWrap']")):
            img = item.query_selector('img')
            if not img.get_src().endswith(M2_IMG):
                continue
            em = item.query_selector('em')
            title = em.get_text_content()
            print('%s %s' % (title, repr(title)))
            if not TITLE in title:
                continue
            print(title)
            for span in iter_dom(item.query_selector_all('span')):
                link = span.get_children().item(0)
                print('%s %s' % (span, link))
                link.click()
                break
            break

    @trace()
    def handle_ticket(self):
        dom = self.webview.get_dom_document()
        # FIXME
        # sometimes id is changed
        select = dom.query_selector("a[id='applynum_YL_1']")
        if not select:
            return
        select.click()
        SCRIPT = """confirmPersonInfo()"""
        self.webview.execute_script(SCRIPT)

    @trace()
    def handle_seat(self):
        self.reload_tag = Timer(1000, self.reset_seat)

        dom = self.webview.get_dom_document()
        form = dom.query_selector("form[id='seatForm']")

        items = list(iter_dom(form.query_selector_all('img')))

        CENTER_X = 12.5
        CENTER_Y = 7

        def get_xy(item):
            id = item.get_id()
            if not id:
                return -1, -1
            i = id.split('z')
            x = (int(i[-1]) % 3) * 8 + int(i[4]) + 1
            y = int(i[1])
            return x, y

        def sort_seat(a, b):
            ax, ay = get_xy(a)
            if (ax, ay) == (-1, -1):
                return 1
            bx, by = get_xy(b)
            if (bx, by) == (-1, -1):
                return -1

            def dist(x, y):
                return math.sqrt((x - CENTER_X) ** 2 + (y - CENTER_Y) ** 2)
            ad = dist(ax, ay)
            bd = dist(bx, by)
            if ad < bd: return -1
            elif ad > bd: return 1
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
            self.webview.execute_script("confirmSeat()")
            return

        # for test
        def do_something():
            for item in items[:8]:
                item.click()
                print(get_xy(item))
                yield True
                item.click()
                yield True

        it = do_something()

        GLib.timeout_add(1000, it.next)

    @trace()
    def handle_pay_type(self):
        dom = self.webview.get_dom_document()
        dom.query_selector("em[class='pay01']").click()
        for i, data in enumerate(CARDNUM.split(), 1):
            dom.query_selector("input[name='cardNum%d']" % i).set_value(data)

        for i, data in enumerate(CARDVALID.split('/'), 1):
            dom.query_selector("input[name='cardPeriod%d']" % i).set_value(data)

        dom.query_selector("input[name='pwNum']").set_value(CARDPASS[:2])
        dom.query_selector("input[name='ssn']").set_value(SSN.split('-')[-1])
        dom.query_selector("a[href='#CREDIT']").click()

        if DEBUG:
            return

        SCRIPT = """confirmPayment()"""
        self.webview.execute_script(SCRIPT)

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
        #settings.props.auto_load_images = False
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
