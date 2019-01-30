import json

import pytest
import asynctest

from csbot import core
from csbot.test import read_fixture_file
from csbot.test.test_plugin_webserver import WebServer


class Bot(core.Bot):
    available_plugins = core.Bot.available_plugins.copy()
    available_plugins.update(
        webserver=WebServer,
    )


@pytest.fixture
def bot_helper_class(bot_helper_class):
    class Helper(bot_helper_class):
        @staticmethod
        def payload_and_headers_from_fixture(fixture):
            payload = read_fixture_file(f'{fixture}.payload.json')
            headers = json.loads(read_fixture_file(f'{fixture}.headers.json'))
            return payload, headers

    return Helper


class TestGitHubPlugin:
    BOT_CLASS = Bot
    CONFIG = """\
    [@bot]
    plugins = webserver webhook github

    [webhook]
    secret = foobar

    [github]
    # Re-usable format strings
    fmt.source = [{repository[name]}] {sender[login]}
    fmt.issue_text = {issue[title]} ({issue[html_url]})
    
    # Format strings for specific events
    fmt/create = {fmt.source} created {ref_type} {ref} ({repository[html_url]}/tree/{ref})
    fmt/delete = {fmt.source} deleted {ref_type} {ref}
    fmt/issues/* = {fmt.source} {action} issue #{issue[number]}: {fmt.issue_text}
    fmt/issues/assigned = {fmt.source} {action} issue #{issue[number]} to {assignee[login]}: {fmt.issue_text}
    
    [github/alanbriolat/csbot-webhook-test]
    notify = #mychannel
    """
    URL = f'/webhook/github/foobar'
    pytestmark = pytest.mark.bot(cls=Bot, config=CONFIG)

    @pytest.fixture
    def loop(self, event_loop):
        """Override pytest-aiohttp's loop fixture with pytest-asyncio's.
        """
        return event_loop

    @pytest.fixture
    async def client(self, bot_helper, aiohttp_client):
        return await aiohttp_client(bot_helper['webserver'].app)

    async def test_signature_check(self, bot_helper, client):
        # Test with a non-existent event name/handler
        event_name = '_test'
        with asynctest.patch.object(bot_helper['github'], f'handle_{event_name}',
                                    new=asynctest.CoroutineMock(), create=True) as m:
            payload, headers = bot_helper.payload_and_headers_from_fixture('github/github-ping-20190128-101509')
            headers['X-GitHub-Event'] = event_name
            # Signature is still intact, so handler should be called
            resp = await client.post(self.URL, data=payload, headers=headers)
            assert resp.status == 200
            m.assert_called_once()
            m.reset_mock()
            # Signature made to be incorrect, handler should *not* be called
            headers['X-Hub-Signature'] = 'sha1=0000000000000000000000000000000000000000'
            resp = await client.post(self.URL, data=payload, headers=headers)
            assert resp.status == 200
            m.assert_not_called()

    TEST_CASES = [
        # ping: https://developer.github.com/webhooks/#ping-event
        ('github/github-ping-20190128-101509', []),

        # create: https://developer.github.com/v3/activity/events/types/#createevent
        # -- branch
        ('github/github-create-20190129-215300', [
            ('NOTICE #mychannel :[csbot-webhook-test] alanbriolat created branch alanbriolat-patch-2 '
             '(https://github.com/alanbriolat/csbot-webhook-test/tree/alanbriolat-patch-2)'),
        ]),
        # -- tag
        ('github/github-create-20190130-101054', [
            ('NOTICE #mychannel :[csbot-webhook-test] alanbriolat created tag v0.0.2 '
             '(https://github.com/alanbriolat/csbot-webhook-test/tree/v0.0.2)'),
        ]),

        # delete: https://developer.github.com/v3/activity/events/types/#deleteevent
        # -- branch
        ('github/github-delete-20190129-215230', [
            'NOTICE #mychannel :[csbot-webhook-test] alanbriolat deleted branch alanbriolat-patch-1',
        ]),

        # issues: https://developer.github.com/v3/activity/events/types/#issuesevent
        # -- opened
        ('github/github-issues-opened-20190128-101904', [
            ('NOTICE #mychannel :[csbot-webhook-test] alanbriolat opened issue #2: '
             'Another test (https://github.com/alanbriolat/csbot-webhook-test/issues/2)'),
        ]),
        # -- closed
        ('github/github-issues-closed-20190128-101908', [
            ('NOTICE #mychannel :[csbot-webhook-test] alanbriolat closed issue #2: '
             'Another test (https://github.com/alanbriolat/csbot-webhook-test/issues/2)'),
        ]),
        # -- reopened
        ('github/github-issues-reopened-20190128-101912', [
            ('NOTICE #mychannel :[csbot-webhook-test] alanbriolat reopened issue #2: '
             'Another test (https://github.com/alanbriolat/csbot-webhook-test/issues/2)'),
        ]),
        # -- assigned
        ('github/github-issues-assigned-20190128-101919', [
            ('NOTICE #mychannel :[csbot-webhook-test] alanbriolat assigned issue #2 to alanbriolat: '
             'Another test (https://github.com/alanbriolat/csbot-webhook-test/issues/2)'),
        ]),
        # -- unassigned
        ('github/github-issues-unassigned-20190128-101924', [
            ('NOTICE #mychannel :[csbot-webhook-test] alanbriolat unassigned issue #2: '
             'Another test (https://github.com/alanbriolat/csbot-webhook-test/issues/2)'),
        ]),

        # pull_request: https://developer.github.com/v3/activity/events/types/#pullrequestevent
        # -- opened
        ('github/github-pull_request-opened-20190129-215304', []),
        # -- closed (merged)
        ('github/github-pull_request-closed-20190129-215221', []),
        # (and corresponding push to master)
        # github-push-20190129-215221
        # -- closed (not merged)
        ('github/github-pull_request-closed-20190129-215329', []),
        # -- reopened
        ('github/github-pull_request-reopened-20190129-215410', []),
        # -- review_requested
        ('github/github-pull_request-review_requested-20190130-194425', []),
        # -- assigned
        ('github/github-pull_request-assigned-20190129-215308', []),
        # -- unassigned
        ('github/github-pull_request-unassigned-20190129-215311', []),

        # pull_request_review: https://developer.github.com/v3/activity/events/types/#pullrequestreviewevent
        # -- submitted
        ('github/github-pull_request_review-submitted-20190129-220000', []),

        # push: https://developer.github.com/v3/activity/events/types/#pushevent
        # -- new branch
        ('github/github-push-20190129-215300', []),
        # -- existing branch
        ('github/github-push-20190129-215221', []),
        # -- forced
        ('github/github-push-20190130-195825', []),

        # release: https://developer.github.com/v3/activity/events/types/#releaseevent
        # -- published
        ('github/github-release-published-20190130-101053', []),
    ]

    # @pytest.mark.parametrize("event_name, fixture_file, expected", TEST_CASES)
    # async def test_handlers(self, bot_helper, client, event_name, fixture_file, expected):
    #     method_name = f'handle_{event_name}'
    #     payload, headers = bot_helper.payload_and_headers_from_fixture(event_name, fixture_file)
    #     with asynctest.patch.object(bot_helper['github'], method_name) as m:
    #         resp = await client.post(self.URL, data=payload, headers=headers)
    #         assert resp.status == 200
    #         m.assert_called_once_with(json.loads(payload))

    @pytest.mark.parametrize("fixture_file, expected", TEST_CASES)
    @pytest.mark.usefixtures("run_client")
    @pytest.mark.asyncio
    async def test_behaviour(self, bot_helper, client, fixture_file, expected):
        payload, headers = bot_helper.payload_and_headers_from_fixture(fixture_file)
        resp = await client.post(self.URL, data=payload, headers=headers)
        assert resp.status == 200
        bot_helper.assert_sent(expected)