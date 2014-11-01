from ..plugin import Plugin
from ..util import simple_http_get
from .linkinfo import LinkInfoResult


def _pad(items, length, value=None):
    """Pad *items* to at least *length*, filling spaces with *value*.
    """
    return items + [value] * max(0, length - len(items))


class Reddit(Plugin):
    LINK_RESPONSE = ('/r/{l[subreddit]}: "{l[title]}" (by {l[author]}) '
                     '[{l[score]} points, {l[num_comments]} comments]')
    COMMENT_RESPONSE = ('/r/{l[subreddit]}: {c[author]}\'s comment '
                        '[{c[score]} points] on ') + \
                       LINK_RESPONSE.split(None, 1)[1]
    SUBREDDIT_RESPONSE = ('/r/{r[display_name]}: "{r[title]}" '
                          '[{r[subscribers]} subscribers]')
    USER_RESPONSE = ('/u/{u[name]}: {u[link_karma]} link '
                     'karma, {u[comment_karma]} comment karma')

    @Plugin.integrate_with('linkinfo')
    def integrate_with_linkinfo(self, linkinfo):
        """Register URL handler with the linkinfo plugin.
        """
        linkinfo.register_handler(
            lambda url: url.netloc in ('reddit.com',
                                       'www.reddit.com',
                                       'redd.it'),
            self.linkinfo_handler)

    def linkinfo_handler(self, url, match):
        """Handle recognised reddit URLs.
        """
        # Split up the path so we can process it chunk by chunk
        parts = _pad(url.path.strip('/').split('/'), 6, None)

        # redd.it/<linkid>
        if url.netloc == 'redd.it' and parts[0]:
            linkid = parts[0]
            return self._linkinfo_link(parts[0])
        # /r/<subreddit>/...
        elif parts[0] == 'r' and parts[1]:
            # /r/<subreddit>/comments/<linkid>/...
            if parts[2] == 'comments' and parts[3]:
                linkid, slug, commentid = parts[3:]
                # /r/<subreddit>/comments/<linkid>/<slug>/<commentid>
                if commentid:
                    return self._linkinfo_comment(linkid, commentid)
                # /r/<subreddit>/comments/<linkid>
                else:
                    return self._linkinfo_link(linkid)
            # /r/<subreddit>
            else:
                subreddit = parts[1]
                return self._linkinfo_subreddit(subreddit)
        # /comments/<linkid>/...
        elif parts[0] == 'comments' and parts[1]:
            linkid, slug, commentid = parts[1:4]
            # /comments/<linkid>/<slug>/<commentid>
            if commentid:
                return self._linkinfo_comment(linkid, commentid)
            # /comments/<linkid>
            else:
                return self._linkinfo_link(linkid)
        # /tb/<linkid>
        elif parts[0] == 'tb' and parts[1]:
            linkid = parts[1]
            return self._linkinfo_link(linkid)
        # /u/<username>, /user/<username>
        elif parts[0] in ('u', 'user') and parts[1]:
            username = parts[1]
            return self._linkinfo_user(username)

        # URL not handled, let somebody else deal with it
        return None

    def _linkinfo_link(self, linkid):
        """Respond with information about a reddit submission.
        """
        r = simple_http_get('http://www.reddit.com/by_id/t3_{}.json'
                            .format(linkid))
        if r.status_code != 200:
            return None

        data = r.json()['data']['children'][0]['data']
        reply = self.LINK_RESPONSE.format(l=data)
        return LinkInfoResult(None, reply, nsfw=data['over_18'])

    def _linkinfo_comment(self, linkid, commentid):
        """Respond with information about a reddit comment.
        """
        r = simple_http_get('http://www.reddit.com/comments/' + linkid + '.json',
                            params={'comment': commentid, 'limit': 1})
        if r.status_code != 200:
            return None

        link = r.json()[0]['data']['children'][0]['data']
        comment = r.json()[1]['data']['children'][0]['data']
        reply = self.COMMENT_RESPONSE.format(l=link, c=comment)
        return LinkInfoResult(None, reply, nsfw=link['over_18'])

    def _linkinfo_subreddit(self, subreddit):
        """Respond with information about a subreddit.
        """
        r = simple_http_get('http://www.reddit.com/r/{}/about.json'
                            .format(subreddit))
        if r.status_code != 200:
            return None

        data = r.json()['data']
        reply = self.SUBREDDIT_RESPONSE.format(r=data)
        return LinkInfoResult(None, reply, nsfw=data['over18'])

    def _linkinfo_user(self, username):
        """Respond with information about a reddit user.
        """
        r = simple_http_get('http://www.reddit.com/user/{}/about.json'
                            .format(username))
        if r.status_code != 200:
            return None

        data = r.json()['data']
        reply = self.USER_RESPONSE.format(u=data)
        return LinkInfoResult(None, reply)
