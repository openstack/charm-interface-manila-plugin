# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

import charmhelpers.core.hookenv as hookenv
import charms.reactive as reactive


class ManilaPluginRequires(reactive.RelationBase):
    """The is the Manila 'end' of the relation.

    The auto accessors are underscored as for some reason RelationBase only
    provides these as 'calls'; i.e. they have to be used as `self._name()`.
    This class therefore provides @properties `name` and `plugin_data` that can
    be used directly.

    This side of the interface sends the manila service user authentication
    information to the plugin charm (which is a subordinate) and gets
    configuration segments for the various files that the manila charm 'owns'
    and, therefore, writes out.

    The most important property is the 'ready' property which indicates that
    the configuration data on the interface is valid and thus can be written to
    the configuration files by the manila charm.
    """
    scope = reactive.scopes.UNIT

    # These remote data fields will be automatically mapped to accessors
    # with a basic documentation string provided.
    auto_accessors = ['_name', '_configuration_data']

    @reactive.hook('{requires:manila-plugin}-relation-joined')
    def joined(self):
        """At least one manila-plugin has joined. Thus we set the connected
        state to allow the consumer to start setting authentication data.

        We also update the status, as this may or may not be another plugin.
        """
        self.set_state('{relation_name}.connected')
        self.update_status()

    @reactive.hook('{requires:manila-plugin}-relation-changed')
    def changed(self):
        """Something has changed in one of the plugins, so we use update_status
        to update the relation states to allow the consumer of the interface to
        update any structures that it needs.
        """
        self.update_status()

    @reactive.hook('{requires:manila-plugin}-relation-{broken,departed}')
    def departed(self):
        self.update_status()

    def update_status(self):
        """Set the .available and .changed state if at least one of the
        conversations (with the subordinate) has a name and some configuration
        data (regardless of whether it is complete).

        As there can be multiple conversations, it is up to the subordinate
        charm to flag up problems with its juju status as the principal charm
        deals with multiple backends.

        Note that the .changed state can be used if a plugin changes the data.
        Thus, Manila can watch changes and then clear it using the method
        clear_changed() to update configuration files as needed.

        The interface will NOT set .changed without having .available at the
        same time.
        """
        count_available = 0
        count_changed = 0
        count_conversations = 0
        for conversation in self.conversations():
            if conversation.scope is None:
                # the conversation has gone away; ignore it
                continue
            count_conversations += 1
            # try to see if we've already had this conversation
            conversation_available = self.get_local(
                '_available', default=None, scope=conversation.scope)
            name = self.get_remote(
                '_name', default=None, scope=conversation.scope)
            configuration_data = self.get_remote(
                '_configuration_data',
                default=None,
                scope=conversation.scope)
            if name is not None and configuration_data is not None:
                count_available += 1
                available = True
            else:
                available = False
            # if we've changed state (or just connected)
            if available != conversation_available:
                self.set_local(_available=available, scope=conversation.scope)
                count_changed += 1

        # now update the relation states to convey what is happening.
        if count_changed:
            self.set_state('{relation_name}.changed')
        if count_available:
            self.set_state('{relation_name}.available')
        else:
            self.remove_state('{relation_name}.available')
        if not count_conversations:
            self.remove_state('{relation_name}.connected')
            self.remove_state('{relation_name}.changed')

    def clear_changed(self):
        """Provide a convenient method to clear the .changed relation"""
        self.remove_state('{relation_name}.changed')

    def set_authentication_data(self, value, name=None):
        """Set the authentication data to the plugin charm.  This is to enable
        the plugin to either 'talk' to OpenStack or to provide authentication
        data into the configuraiton sections that it needs to set (the generic
        backend needs to do this).

        The authentication data format is:
        {
            'username': <value>
            'password': <value>
            'project_domain_id': <value>
            'project_name': <value>
            'user_domain_id': <value>
            'auth_uri': <value>
            'auth_url': <value>
            'auth_type': <value>  # 'password', typically
        }

        :param value: a dictionary of data to set.
        :param name: OPTIONAL - target the config at a particular name only
        """
        keys = {'username', 'password', 'project_domain_id', 'project_name',
                'user_domain_id', 'auth_uri', 'auth_url', 'auth_type'}
        passed_keys = set(value.keys())
        if passed_keys.difference(keys) or keys.difference(passed_keys):
            hookenv.log(
                "Setting Authentication data; there may be missing or mispelt "
                "keys: passed: {}".format(passed_keys),
                level=hookenv.WARNING)
        # need to check for each conversation whether we've sent the data, or
        # whether it is different, and then set the local & remote only if that
        # is the case.
        for conversation in self.conversations():
            if conversation.scope is None:
                # the conversation has gone away; ignore it
                continue
            if name is not None:
                conversation_name = self.get_remote('_name', default=None,
                                                    scope=conversation.scope)
                if name != conversation_name:
                    continue
            existing_auth_data = self.get_local('_authentication_data',
                                                default=None,
                                                scope=conversation.scope)
            if existing_auth_data is not None:
                # see if they are different
                existing_auth = json.loads(existing_auth_data)["data"]
                if (existing_auth.keys() == value.keys() and
                        all([v == value[k]
                             for k, v in existing_auth.items()])):
                    # the values haven't changed, so don't set them again
                    continue
            self.set_local(_authentication_data=json.dumps({"data": value}),
                           scope=conversation.scope)
            self.set_remote(_authentication_data=json.dumps({"data": value}),
                            scope=conversation.scope)

    @property
    def names(self):
        """Response with a list of names of backends where there is
        configuration data on the interface.

        :returns: list of names from the interfaces which have config data
        """
        names = []
        for conversation in self.conversations():
            if conversation.scope is None:
                # the conversation has gone away; ignore it
                continue
            name = self.get_remote('_name', default=None,
                                   scope=conversation.scope)
            config = self.get_remote('_configuration_data', default=None,
                                     scope=conversation.scope)
            if name and config:
                names.append(name)
        return names

    def get_configuration_data(self, name=None):
        """Return the configuration_data from the plugin if it is available.

        The format of the data returned is:
        {
            '<config file>': {
                '<section>: (
                    (key, value),
                    (key, value),
                    "or string",
            )
        }

        if 'name' is provided, then only the configuration data for that name
        is returned, otherwise all of the configuration data for all
        conversations is returned as an amalgamated dict.

        :param name: OPTIONAL: specify the name of the interface (_name)
        :returns: data object that was passed.
        """
        result = {}
        for conversation in self.conversations():
            if conversation.scope is None:
                # the conversation has gone away; ignore it
                continue
            if name:
                _name = self.get_remote('_name', default=None,
                                        scope=conversation.scope)
                if _name != name:
                    continue
            config = self.get_remote('_configuration_data', default=None,
                                     scope=conversation.scope)
            if config:
                result.update(json.loads(config)["data"])
        return result
