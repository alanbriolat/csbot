# coding=utf-8
from StringIO import StringIO

from twisted.trial import unittest
from httpretty import httprettified, HTTPretty
from lxml.etree import LIBXML_VERSION
from mock import Mock, patch, call
from urlparse import urlparse

from csbot.core import Bot


class TestHandlers(unittest.TestCase):
    bot_config = """
    [@bot]
    plugins = linkinfo
    """

    def setUp(self):
        self.bot = Bot(StringIO(self.bot_config))
        self.linkinfo = self.bot.plugins['linkinfo']
        # Catch things which fall through to default HTML scraper, preventing
        # external requests
        scrape_patcher = patch.object(self.linkinfo, 'scrape_html_title', return_value=None)
        self.scrape_mock = scrape_patcher.start()
        self.addCleanup(scrape_patcher.stop)

    def test_filters(self):
        raw_url = 'http://example.com/foo/bar.html'
        parsed_url = urlparse(raw_url)

        # A single handler with a failing filter should fall back to the default
        # HTML title scraper
        f1 = Mock(return_value=False)
        h1 = Mock()
        self.linkinfo.register_handler(f1, h1)
        self.assertEqual(self.linkinfo.get_link_info(raw_url),
                         self.scrape_mock.return_value)
        f1.assert_called_once_with(parsed_url)
        assert not h1.called

        # A later handler with a passing filter should get called, and a
        # non-None result prevents further handlers getting called
        f1.reset_mock()
        f2 = Mock(return_value=True)
        h2 = Mock()
        f3 = Mock(return_value=True)
        h3 = Mock()
        self.linkinfo.register_handler(f2, h2)
        self.linkinfo.register_handler(f3, h3)

        # Result should be the return value of the handler associated with the
        # first passing filter
        self.assertEqual(self.linkinfo.get_link_info(raw_url), h2.return_value)

        # First filter is called, but fails so first handler is not called
        f1.assert_called_once_with(parsed_url)
        assert not h1.called
        # Second filter is called, passes, handler is called with URL and
        # the filter result
        f2.assert_called_once_with(parsed_url)
        h2.assert_called_once_with(parsed_url, f2.return_value)
        # Because the second filter and handler succeeded, third is not called
        assert not f3.called
        assert not h3.called

    def test_fallthrough(self):
        raw_url = 'http://example.com/foo/bar.html'
        parsed_url = urlparse(raw_url)

        # Returning None from a handler should continue as if the filter failed
        f1 = Mock(return_value=True)
        h1 = Mock(return_value=None)
        self.linkinfo.register_handler(f1, h1)
        # One None-returning handler, should fall back to the HTML title scraper
        self.assertEqual(self.linkinfo.get_link_info(raw_url),
                         self.scrape_mock.return_value)
        f1.assert_called_once_with(parsed_url)
        h1.assert_called_once_with(parsed_url, f1.return_value)

        # If another handler exists and returns a non-None result then that
        # should be used
        self.scrape_mock.reset_mock()
        f2 = Mock(return_value=True)
        h2 = Mock()
        self.linkinfo.register_handler(f2, h2)
        self.assertEqual(self.linkinfo.get_link_info(raw_url), h2.return_value)
        f2.assert_called_once_with(parsed_url)
        h2.assert_called_once_with(parsed_url, f2.return_value)
        assert not self.scrape_mock.called


class TestEncoding(unittest.TestCase):
    bot_config = """
    [@bot]
    plugins = linkinfo
    """

    def setUp(self):
        self.bot = Bot(StringIO(self.bot_config))
        self.linkinfo = self.bot.plugins['linkinfo']

    @httprettified
    def _run_encoding_test(self, url, content_type, body, expected_title):
        HTTPretty.register_uri(HTTPretty.GET, url, body=body,
                               content_type=content_type)
        _, _, title = self.linkinfo.get_link_info(url)
        self.assertEqual(title, expected_title, url)

    def test_encoding_handling(self):
        # UTF-8 with Content-Type header encoding only
        self._run_encoding_test(
            "http://example.com/utf8-content-type-only",
            "text/html; charset=utf-8",
            "<html><head><title>EM DASH \xe2\x80\x94 &mdash;</title></head><body></body></html>",
            u'"EM DASH \u2014 \u2014"')
        # UTF-8 with meta http-equiv encoding only
        self._run_encoding_test(
            "http://example.com/utf8-meta-http-equiv-only",
            "text/html",
            ('<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
             '<title>EM DASH \xe2\x80\x94 &mdash;</title></head><body></body></html>'),
            u'"EM DASH \u2014 \u2014"')
        # UTF-8 with XML encoding declaration only
        self._run_encoding_test(
            "http://example.com/utf8-xml-encoding-only",
            "text/html",
            ('<?xml version="1.0" encoding="UTF-8"?><html><head>'
             '<title>EM DASH \xe2\x80\x94 &mdash;</title></head><body></body></html>'),
            u'"EM DASH \u2014 \u2014"')

        # (The following are real test cases the bot has barfed on in the past)

        # Content-Type encoding, XML encoding declaration *and* http-equiv are all
        # present (but no UTF-8 in title).  If we give lxml a decoded string with
        # the XML encoding declaration it complains.
        self._run_encoding_test(
            "http://www.w3.org/TR/REC-xml/",
            "text/html; charset=utf-8",
            """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html
  PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="EN">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <title>Extensible Markup Language (XML) 1.0 (Fifth Edition)</title>
        <!-- snip -->
    </head>
    <body>
    <!-- snip -->
    </body>
</html>
            """,
            u'"Extensible Markup Language (XML) 1.0 (Fifth Edition)"')
        # No Content-Type encoding, but has http-equiv encoding.  Has a mix of
        # UTF-8 literal em-dash and HTML entity em-dash - both should be output as
        # unicode em-dash.
        self._run_encoding_test(
            "http://docs.python.org/2/library/logging.html",
            "text/html",
            """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <title>15.7. logging \xe2\x80\x94 Logging facility for Python &mdash; Python v2.7.3 documentation</title>
    <!-- snip -->
  </head>
  <body>
  <!-- snip -->
  </body>
</html>
            """,
            u'"15.7. logging \u2014 Logging facility for Python \u2014 Python v2.7.3 documentation"')

    def test_encoding_handling_html5(self):
        if LIBXML_VERSION < (2, 8, 0):
            raise unittest.SkipTest(
                "HTML5 meta charset unsupported before libxml 2.8.0")

        # UTF-8 with meta charset encoding only
        self._run_encoding_test(
            "http://example.com/utf8-meta-charset-only",
            "text/html",
            ('<html><head><meta charset="UTF-8"><title>EM DASH \xe2\x80\x94 &mdash;'
             '</title></head><body></body></html>'),
            u'"EM DASH \u2014 \u2014"')
