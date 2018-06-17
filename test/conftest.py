"""
Configuration for Pytest
"""

from unittest.mock import MagicMock
from itertools import islice
from collections import defaultdict
import time
import pytest
from slackclient import SlackClient

import uqcsbot as uqcsbot_module
from uqcsbot.api import APIWrapper
from uqcsbot.base import UQCSBot, Command

# Arbitrary channel and user ids for use in testing
TEST_CHANNEL_ID = "C1234567890"
TEST_GROUP_ID = "G1234567890"
TEST_DIRECT_ID = "D1234567890"
TEST_USER_ID = "U1234567890"
TEST_BOT_ID = "B1234567890"


class MockUQCSBot(UQCSBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_users = {
            TEST_BOT_ID: {'id': TEST_BOT_ID, 'name': TEST_BOT_ID, 'deleted': False,
                           'profile': {'display_name': TEST_BOT_ID}, 'is_bot': True},
            TEST_USER_ID: {'id': TEST_USER_ID, 'name': TEST_USER_ID, 'deleted': False,
                           'profile': {'display_name': TEST_USER_ID}}
        }
        self.test_messages = defaultdict(list)
        self.test_channels = {
            # Public channel
            TEST_CHANNEL_ID: {'id': TEST_CHANNEL_ID, 'name': TEST_CHANNEL_ID,
                              'is_public': True, 'members': [TEST_USER_ID]},
            # Group channel
            TEST_GROUP_ID: {'id': TEST_GROUP_ID, 'name': TEST_GROUP_ID,
                            'is_group': True, 'is_private': True,
                            'members': [TEST_USER_ID]},
            # Direct channel
            TEST_DIRECT_ID: {'id': TEST_DIRECT_ID, 'name': TEST_DIRECT_ID,
                             'is_im': True, 'is_private': True,
                             'is_user_deleted': False, 'user': TEST_USER_ID}
        }

        def mocked_api_call(method, **kwargs):
            '''
            Called the mocked version of a Slack API call.
            '''
            mocked_method = 'mocked_' + method.replace('.', '_')
            if mocked_method not in dir(type(self)):
                raise NotImplementedError(f'{method} has not been mocked.')
            return getattr(self, mocked_method)(**kwargs)

        self.mocked_client = MagicMock(spec=SlackClient)
        self.mocked_client.api_call = mocked_api_call

    @property
    def api(self):
        return APIWrapper(self.mocked_client)

    def mocked_users_info(self, **kwargs):
        '''
        Mocks users.info api call.
        '''
        user_id = kwargs.get('user')

        user = self.test_users.get(user_id)
        if user is None:
            return {'ok': False}

        return {'ok': True, 'user': user}

    def mocked_conversations_members(self, **kwargs):
        '''
        Mocks conversations.members api call.
        '''
        channel_id = kwargs.get('channel')
        cursor = kwargs.get('cursor', 0)
        limit = kwargs.get('limit', 100)

        channel = self.test_channels.get(channel_id)
        if channel is None:
            return {'ok': False}

        all_members = channel.get('members', [])
        sliced_members = all_members[cursor : cursor + limit + 1]
        cursor += len(sliced_members)
        if cursor == len(all_members):
            cursor = None

        return {'ok': True, 'members': sliced_members, 'cursor': cursor}

    def mocked_conversations_history(self, **kwargs):
        '''
        Mocks conversations.history api call.
        '''
        channel_id = kwargs.get('channel')
        cursor = kwargs.get('cursor', 0)
        limit = kwargs.get('limit', 100)

        if channel_id not in self.test_channels:
            return {'ok': False}

        all_messages = self.test_messages.get(channel_id, [])
        ordered_messages = all_messages[::-1] # Most recent first
        sliced_messages = list(islice(ordered_messages, cursor, cursor + limit + 1))
        cursor += len(sliced_messages)
        if cursor == len(all_messages):
            cursor = None

        return {'ok': True, 'messages': sliced_messages, 'cursor': cursor}

    def mocked_groups_list(self, **kwargs):
        '''
        Mocks groups.list api call.
        '''
        return self.mocked_channels_list(channel_type='groups', **kwargs)

    def mocked_im_list(self, **kwargs):
        '''
        Mocks im.list api call.
        '''
        return self.mocked_channels_list(channel_type='ims', **kwargs)

    def mocked_channels_list(self, channel_type='channels', **kwargs):
        '''
        Mocks channels.list api call.
        '''
        cursor = kwargs.get('cursor', 0)
        limit = kwargs.get('limit', 100)

        if channel_type == 'channels':
            filter_function = lambda x: x.get('is_public', False)
        elif channel_type == 'groups':
            filter_function = lambda x: x.get('is_group', False)
        elif channel_type == 'ims':
            filter_function = lambda x: x.get('is_im', False)
        else:
            return {'ok': False}

        all_channels = list(filter(filter_function, self.test_channels.values()))
        sliced_channels = all_channels[cursor : cursor + limit + 1]
        cursor += len(sliced_channels)
        if cursor == len(all_channels):
            cursor = None

        return {'ok': True, channel_type: sliced_channels, 'cursor': cursor}

    def mocked_users_list(self, **kwargs):
        '''
        Mocks users.list api call.
        '''
        cursor = kwargs.get('cursor', 0)
        limit = kwargs.get('limit', 100)

        all_members = list(self.test_users.values())
        sliced_members = all_members[cursor : cursor + limit + 1]
        cursor += len(sliced_members)
        if cursor == len(all_members):
            cursor = None

        return {'ok': True, 'members': sliced_members, 'cursor': cursor}

    def get_channel_message(self, **kwargs) -> dict:
        '''
        Convenience function which returns the message at the given channel
        and timestamp.
        '''
        channel_id_or_name = kwargs.get('channel')
        timestamp = kwargs.get('timestamp')

        channel = self.channels.get(channel_id_or_name)
        if channel is None or timestamp is None:
            return None

        channel_messages = self.test_messages.get(channel.id, [])
        channel_message = [message for message in channel_messages
                           if message['ts'] == timestamp]
        return None if len(channel_message) != 1 else channel_message[0]

    def mocked_reactions_add(self, **kwargs):
        '''
        Mocks reactions.add api call.
        '''
        name = kwargs.get('name')
        message = self.get_channel_message(**kwargs)
        if name is None or message is None:
            return {'ok': False}
        # Note: 'user' is not a part of Slack API for reactions.add, just a
        # convenient way to set the calling user during testing. If not passed,
        # message is assumed to be from bot.
        user = kwargs.get('user', TEST_BOT_ID)

        if 'reactions' not in message:
            message['reactions'] = []

        reaction_object = next((r for r in message['reactions'] if r['name'] == name), None)
        message['reactions'] = [r for r in message['reactions'] if r['name'] != name]

        if reaction_object is None:
            reaction_object = {'name': name, 'count': 0, 'users': []}
        if user not in reaction_object['users']:
            reaction_object['count'] += 1
            reaction_object['users'].append(user)

        message['reactions'].append(reaction_object)
        return {'ok': True}


    def mocked_reactions_remove(self, **kwargs):
        '''
        Mocks reactions.remove api call.
        '''
        name = kwargs.get('name')
        message = self.get_channel_message(**kwargs)
        if name is None or message is None:
            return {'ok': False}
        # Note: 'user' is not a part of Slack API for reactions.add, just a
        # convenient way to set the calling user during testing. If not passed,
        # message is assumed to be from bot.
        user = kwargs.get('user', TEST_BOT_ID)

        if 'reactions' not in message:
            return {'ok': False}

        reaction_object = next((r for r in message['reactions'] if r['name'] == name), None)
        message['reactions'] = [r for r in message['reactions'] if r['name'] != name]

        if reaction_object is None:
            return {'ok': False}
        if user not in reaction_object['users']:
            return {'ok': False}

        reaction_object['count'] -= 1
        reaction_object['users'].append(user)
        message['reactions'].append(reaction_object)
        return {'ok': True}

    def mocked_chat_postMessage(self, **kwargs):
        '''
        Mocks chat.postMessage api call.
        '''
        channel_id_or_name = kwargs.get('channel')
        # Note: 'user' is not a part of Slack API for chat.postMessage, just a
        # convenient way to set the calling user during testing. If not passed,
        # message is assumed to be from bot.
        user = kwargs.get('user', TEST_BOT_ID)

        channel = self.channels.get(channel_id_or_name)
        if channel is None:
            return {'ok': False}

        # Strip the kwargs down to only ones which are valid for this api call.
        # Note: if there is an additional argument you need supported, add it
        # here.
        stripped_kwargs = {k: v for k, v in kwargs.items()
                           if k in ('text', 'attachments', 'user')}
        message = {'type': 'message', 'ts': str(time.time()), 'user': user,
                   **stripped_kwargs}
        # In case we were given a channel name, set channel strictly by the id.
        message['channel'] = channel.id
        self.test_messages[channel.id].append(message)
        self._run_handlers(message)

        return {'ok': True, 'channel': channel.id, 'ts': message['ts'],
                'message': message}

    def _handle_command(self, message: dict) -> None:
        '''
        Handles commands without using an executor.
        '''
        command = Command.from_message(message)
        if command is None:
            return None
        if command.name not in self._command_registry:
            raise NotImplementedError('{command.name} is not a registered command.')
        for handler in self._command_registry[command.name]:
            handler(command)

    def _run_handlers(self, event: dict):
        '''
        Runs handlers without using an executor.
        '''
        handlers = self._handlers[event['type']] + self._handlers['']
        return [handler(event) for handler in handlers]


@pytest.fixture(scope="session")
def _uqcsbot():
    """
    Create a mocked UQCSBot and allow it to find handlers. Persists for the
    whole test session.
    """
    uqcsbot_module.bot = MockUQCSBot()
    uqcsbot_module.import_scripts()
    return uqcsbot_module.bot


@pytest.fixture()
def uqcsbot(_uqcsbot: MockUQCSBot):
    """
    Setup and tear-down steps to run around tests.
    """
    # Anything before yield will be run before test
    # Initialise channels and users
    _uqcsbot.channels._initialise()
    _uqcsbot.users._initialise()
    yield _uqcsbot
    # Anything after yield will be run after test
    # Clear channel messages
    _uqcsbot.test_messages.clear()
