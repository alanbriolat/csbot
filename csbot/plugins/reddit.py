import requests

from csbot.plugin import Plugin


def _pad(items, length, value=None):
    return items + [value] * max(0, length - len(items))


class Reddit(Plugin):
    REPLY_PREFIX = 'Reddit'

    @Plugin.integrate_with('linkinfo')
    def integrate_with_linkinfo(self, linkinfo):
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
        r = requests.get('http://www.reddit.com/by_id/t3_{}.json'
                         .format(linkid))
        if r.status_code != requests.codes.ok:
            return None

        data = r.json['data']['children'][0]['data']
        reply = (u'"{l[title]}" in /r/{l[subreddit]}; '
                 u'{l[num_comments]} comments, '
                 u'{l[score]} points (+{l[ups]}/-{l[downs]})'
                ).format(l=data)
        return self.REPLY_PREFIX, data['over_18'], reply

    def _linkinfo_comment(self, linkid, commentid):
        """Respond with information about a reddit comment.
        """
        r = requests.get('http://www.reddit.com/comments/' + linkid + '.json',
                         params={'comment': commentid, 'limit': 1})
        if r.status_code != requests.codes.ok:
            return None

        link = r.json[0]['data']['children'][0]['data']
        comment = r.json[1]['data']['children'][0]['data']
        reply = (u"{c[author]}'s comment (+{c[ups]}/-{c[downs]}) "
                 u'on "{l[title]}" in /r/{l[subreddit]}'
                ).format(l=link, c=comment)
        return self.REPLY_PREFIX, link['over_18'], reply

    def _linkinfo_subreddit(self, subreddit):
        """Respond with information about a subreddit.
        """
        r = requests.get('http://www.reddit.com/r/{}/about.json'
                         .format(subreddit))
        if r.status_code != requests.codes.ok:
            return None

        data = r.json['data']
        reply = (u'/r/{r[display_name]}: "{r[title]}"; '
                 u'{r[subscribers]} subscribers'
                ).format(r=data)
        return self.REPLY_PREFIX, data['over18'], reply

    def _linkinfo_user(self, username):
        """Respond with information about a reddit user.
        """
        r = requests.get('http://www.reddit.com/user/{}/about.json'
                         .format(username))
        if r.status_code != requests.codes.ok:
            return None

        data = r.json['data']
        reply = (u'user "{u[name]}"; {u[link_karma]} link '
                 u'karma, {u[comment_karma]} comment karma'
                ).format(u=data)
        return self.REPLY_PREFIX, False, reply
