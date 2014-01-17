import datetime
import re

import pymongo

from csbot.plugin import Plugin


class Define(Plugin):
    PLUGIN_DEPENDS = ['mongodb']

    CONFIG_DEFAULTS = {
        # Don't let the parameterless !forget command look any further back
        # than this many minutes.
        'forget_timeout': 1,
        # Maximum number of words in a term.
        'max_term_words': 4,
    }

    LOOKUP_REGEX = re.compile(r"(\b(what|who)('s|\s+is)\s+|^)(?P<term>.+)\?$",
                              re.I)
    DEFINE_REGEX = re.compile(r"^(?P<term>.+)\s+is\s+(?P<definition>.*[^?])$",
                              re.I)

    @Plugin.integrate_with('mongodb')
    def _get_db(self, mongodb):
        self.db = mongodb.get_db(self.plugin_name())
        self.defns = self.db.definitions
        self.defns.ensure_index([('term_lower', pymongo.ASCENDING),
                                 ('datetime', pymongo.DESCENDING)])

    @Plugin.hook('core.message.privmsg')
    def privmsg(self, e):
        # TODO: remove/ignore leading "<nick>:"
        lookup_match = self.LOOKUP_REGEX.match(e['message'])
        define_match = self.DEFINE_REGEX.match(e['message'])

        if lookup_match is not None:
            term = lookup_match.group('term').strip()
            if len(term.split()) <= self.config_get('max_term_words'):
                self._lookup(e, term)
            else:
                self.log.debug('ignored "{}", >{} words'.format(
                    term, self.config_get('max_term_words')))
        elif define_match is not None:
            term = define_match.group('term').strip()
            definition = define_match.group('definition').strip()
            if len(term.split()) <= self.config_get('max_term_words'):
                self._define(e, term, definition)
            else:
                self.log.debug('ignored "{}", >{} words'.format(
                    term, self.config_get('max_term_words')))

    def _lookup(self, e, term):
        """Look up an existing term, responding with the definition if found.
        """
        self.log.debug('lookup: ' + term)
        record = self.defns.find_one({'term_lower': term.lower()},
                                     sort=[('datetime', pymongo.DESCENDING)])
        if record is not None:
            e.protocol.msg(e['reply_to'],
                           '{term} is {definition}'.format(**record))
        else:
            self.log.debug('"{}" is undefined'.format(term))

    def _define(self, e, term, definition):
        """Add a definition for a term, responding with an acknowledgement.

        TODO: disallow automatic redefinitions?
        """
        self.log.debug('define: {} = {}'.format(term, definition))
        record = {
            'term': term,
            'term_lower': term.lower(),
            'definition': definition,
            'datetime': datetime.datetime.now(),
        }
        self.defns.insert(record)
        e.protocol.msg(e['reply_to'],
                       'Got it, {} is {}'.format(term, definition))

    @Plugin.command('redefine')
    def redefine(self, e):
        pass

    @Plugin.command('forget')
    def forget(self, e):
        """Forget a definition, by default the most recent.

        Forget the n-th most recent definition of a term, or if no arguments are
        given the most recent definition saved.
        """
        pass
