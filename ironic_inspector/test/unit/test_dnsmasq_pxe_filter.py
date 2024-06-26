# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import builtins
try:
    import errno
except ImportError:
    import os.errno as errno
import datetime
import os
from unittest import mock

import fixtures
from openstack import exceptions as os_exc
from oslo_config import cfg

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import node_cache
from ironic_inspector.pxe_filter import base as pxe_filter
from ironic_inspector.pxe_filter import dnsmasq
from ironic_inspector.test import base as test_base
from ironic_inspector import utils

CONF = cfg.CONF


class DnsmasqTestBase(test_base.BaseTest):
    def setUp(self):
        super(DnsmasqTestBase, self).setUp()
        self.driver = dnsmasq.DnsmasqFilter()


class TestConfiguration(DnsmasqTestBase):

    def test_deny_unknown_macs_and_node_not_found_hook_bad(self):
        CONF.set_override('deny_unknown_macs', True, 'pxe_filter')
        CONF.set_override('node_not_found_hook', True, 'processing')
        self.assertRaisesRegex(utils.Error, 'Configuration error:',
                               self.driver.__init__)


class TestShouldEnableUnknownHosts(DnsmasqTestBase):
    def setUp(self):
        super(TestShouldEnableUnknownHosts, self).setUp()
        self.mock_introspection_active = self.useFixture(
            fixtures.MockPatchObject(node_cache, 'introspection_active')).mock

    def test_introspection_active(self):
        self.mock_introspection_active.return_value = True
        self.assertTrue(dnsmasq._should_enable_unknown_hosts())

    def test_introspection_not_active(self):
        self.mock_introspection_active.return_value = False
        self.assertFalse(dnsmasq._should_enable_unknown_hosts())


class TestDnsmasqDriverAPI(DnsmasqTestBase):
    def setUp(self):
        super(TestDnsmasqDriverAPI, self).setUp()
        self.mock__execute = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_execute')).mock
        self.driver._sync = mock.Mock()
        self.driver._tear_down = mock.Mock()
        self.mock__purge_dhcp_hostsdir = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_purge_dhcp_hostsdir')).mock
        self.mock_ironic = mock.Mock()
        get_client_mock = self.useFixture(
            fixtures.MockPatchObject(ir_utils, 'get_client')).mock
        get_client_mock.return_value = self.mock_ironic
        self.start_command = '/far/boo buzz -V --ack 42'
        CONF.set_override('dnsmasq_start_command', self.start_command,
                          'dnsmasq_pxe_filter')
        self.stop_command = '/what/ever'
        CONF.set_override('dnsmasq_stop_command', self.stop_command,
                          'dnsmasq_pxe_filter')

    def test_init_filter(self):
        self.driver.init_filter()

        self.mock__purge_dhcp_hostsdir.assert_called_once_with()
        self.driver._sync.assert_called_once_with(self.mock_ironic)
        self.mock__execute.assert_called_once_with(self.start_command)

    def test_sync(self):
        self.driver.init_filter()
        # NOTE(milan) init_filter performs an initial sync
        self.driver._sync.reset_mock()
        self.driver.sync(self.mock_ironic)

        self.driver._sync.assert_called_once_with(self.mock_ironic)

    def test_tear_down_filter(self):
        mock_reset = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'reset')).mock
        self.driver.init_filter()
        self.driver.tear_down_filter()

        mock_reset.assert_called_once_with()

    def test_reset(self):
        self.driver.init_filter()
        # NOTE(milan) init_filter calls _base_cmd
        self.mock__execute.reset_mock()
        self.driver.reset()

        self.mock__execute.assert_called_once_with(
            self.stop_command, ignore_errors=True)


class TestExclusiveWriteOrPass(test_base.BaseTest):
    def setUp(self):
        super(TestExclusiveWriteOrPass, self).setUp()
        self.mock_open = self.useFixture(fixtures.MockPatchObject(
            builtins, 'open', new=mock.mock_open())).mock
        self.mock_fd = self.mock_open.return_value
        self.mock_fcntl = self.useFixture(fixtures.MockPatchObject(
            dnsmasq.fcntl, 'flock', autospec=True)).mock
        self.path = '/foo/bar/baz'
        self.buf = 'spam'
        self.fcntl_lock_call = mock.call(
            self.mock_fd, dnsmasq.fcntl.LOCK_EX | dnsmasq.fcntl.LOCK_NB)
        self.fcntl_unlock_call = mock.call(self.mock_fd, dnsmasq.fcntl.LOCK_UN)
        self.mock_log = self.useFixture(fixtures.MockPatchObject(
            dnsmasq.LOG, 'debug')).mock
        self.mock_sleep = self.useFixture(fixtures.MockPatchObject(
            dnsmasq.time, 'sleep')).mock

    def test_write(self):
        wrote = dnsmasq._exclusive_write_or_pass(self.path, self.buf)
        self.assertTrue(wrote)
        self.mock_open.assert_called_once_with(self.path, 'w', 1)
        self.mock_fcntl.assert_has_calls(
            [self.fcntl_lock_call, self.fcntl_unlock_call])
        self.mock_fd.write.assert_called_once_with(self.buf)
        self.mock_log.assert_not_called()

    def test_write_would_block(self):
        err = IOError('Oops!')
        err.errno = errno.EWOULDBLOCK
        # lock/unlock paired calls
        self.mock_fcntl.side_effect = [
            # first try
            err, None,
            # second try
            None, None]
        wrote = dnsmasq._exclusive_write_or_pass(self.path, self.buf)

        self.assertTrue(wrote)
        self.mock_open.assert_called_once_with(self.path, 'w', 1)
        self.mock_fcntl.assert_has_calls(
            [self.fcntl_lock_call, self.fcntl_unlock_call],
            [self.fcntl_lock_call, self.fcntl_unlock_call])
        self.mock_fd.write.assert_called_once_with(self.buf)
        self.mock_log.assert_called_once_with(
            '%s locked; will try again (later)', self.path)
        self.mock_sleep.assert_called_once_with(
            dnsmasq._EXCLUSIVE_WRITE_ATTEMPTS_DELAY)

    def test_write_would_block_too_many_times(self):
        self.useFixture(fixtures.MonkeyPatch(
            'ironic_inspector.pxe_filter.dnsmasq._EXCLUSIVE_WRITE_ATTEMPTS',
            1))
        err = IOError('Oops!')
        err.errno = errno.EWOULDBLOCK
        self.mock_fcntl.side_effect = [err, None]

        wrote = dnsmasq._exclusive_write_or_pass(self.path, self.buf)
        self.assertFalse(wrote)
        self.mock_open.assert_called_once_with(self.path, 'w', 1)
        self.mock_fcntl.assert_has_calls(
            [self.fcntl_lock_call, self.fcntl_unlock_call])
        self.mock_fd.write.assert_not_called()
        retry_log_call = mock.call('%s locked; will try again (later)',
                                   self.path)
        failed_log_call = mock.call(
            'Failed to write the exclusively-locked path: %(path)s for '
            '%(attempts)s times', {
                'attempts': dnsmasq._EXCLUSIVE_WRITE_ATTEMPTS,
                'path': self.path
            })
        self.mock_log.assert_has_calls([retry_log_call, failed_log_call])
        self.mock_sleep.assert_called_once_with(
            dnsmasq._EXCLUSIVE_WRITE_ATTEMPTS_DELAY)

    def test_write_custom_ioerror(self):

        err = IOError('Oops!')
        err.errno = errno.EBADF
        self.mock_fcntl.side_effect = [err, None]

        self.assertRaisesRegex(
            IOError, 'Oops!', dnsmasq._exclusive_write_or_pass, self.path,
            self.buf)

        self.mock_open.assert_called_once_with(self.path, 'w', 1)
        self.mock_fcntl.assert_has_calls(
            [self.fcntl_lock_call, self.fcntl_unlock_call])
        self.mock_fd.write.assert_not_called()
        self.mock_log.assert_not_called()


class TestMACHandlers(test_base.BaseTest):
    def setUp(self):
        super(TestMACHandlers, self).setUp()
        self.mac = 'ff:ff:ff:ff:ff:ff'
        self.dhcp_hostsdir = '/far'
        CONF.set_override('dhcp_hostsdir', self.dhcp_hostsdir,
                          'dnsmasq_pxe_filter')
        self.mock_join = self.useFixture(
            fixtures.MockPatchObject(os.path, 'join')).mock
        self.mock_join.return_value = "%s/%s" % (self.dhcp_hostsdir, self.mac)
        self.mock__exclusive_write_or_pass = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_exclusive_write_or_pass')).mock
        self.mock_stat = self.useFixture(
            fixtures.MockPatchObject(os, 'stat')).mock
        self.mock_listdir = self.useFixture(
            fixtures.MockPatchObject(os, 'listdir')).mock
        self.mock_remove = self.useFixture(
            fixtures.MockPatchObject(os, 'remove')).mock
        self.mock_log = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, 'LOG')).mock
        self.mock_introspection_active = self.useFixture(
            fixtures.MockPatchObject(node_cache, 'introspection_active')).mock

    def test__allowlist_unknown_hosts(self):
        self.mock_join.return_value = "%s/%s" % (self.dhcp_hostsdir,
                                                 dnsmasq._UNKNOWN_HOSTS_FILE)
        self.mock_introspection_active.return_value = True
        dnsmasq._configure_unknown_hosts()

        self.mock_join.assert_called_once_with(self.dhcp_hostsdir,
                                               dnsmasq._UNKNOWN_HOSTS_FILE)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value,
            '%s' % dnsmasq._ALLOW_UNKNOWN_HOSTS)
        self.mock_log.debug.assert_called_once_with(
            'A %s record for all unknown hosts using wildcard mac '
            'created', 'allow')

    def test__denylist_unknown_hosts(self):
        self.mock_join.return_value = "%s/%s" % (self.dhcp_hostsdir,
                                                 dnsmasq._UNKNOWN_HOSTS_FILE)
        self.mock_introspection_active.return_value = False
        dnsmasq._configure_unknown_hosts()

        self.mock_join.assert_called_once_with(self.dhcp_hostsdir,
                                               dnsmasq._UNKNOWN_HOSTS_FILE)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value,
            '%s' % dnsmasq._DENY_UNKNOWN_HOSTS)
        self.mock_log.debug.assert_called_once_with(
            'A %s record for all unknown hosts using wildcard mac '
            'created', 'deny')

    def test__macs_unknown_hosts_deny_unknown(self):
        self.mock_join.return_value = "%s/%s" % (self.dhcp_hostsdir,
                                                 dnsmasq._UNKNOWN_HOSTS_FILE)
        self.mock_introspection_active.return_value = True
        CONF.set_override('deny_unknown_macs', True, 'pxe_filter')

        dnsmasq._configure_unknown_hosts()

        self.mock_join.assert_called_once_with(self.dhcp_hostsdir,
                                               dnsmasq._UNKNOWN_HOSTS_FILE)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value,
            '%s' % dnsmasq._DENY_UNKNOWN_HOSTS)
        self.mock_log.debug.assert_called_once_with(
            'A %s record for all unknown hosts using wildcard mac '
            'created', 'deny')

    def test__configure_removedlist_allowlist(self):
        self.mock_introspection_active.return_value = True
        self.mock_stat.return_value.st_size = dnsmasq._MAC_DENY_LEN

        dnsmasq._configure_removedlist({self.mac})

        self.mock_join.assert_called_with(self.dhcp_hostsdir, self.mac)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value, '%s\n' % self.mac)

    def test__configure_removedlist_denylist(self):
        self.mock_introspection_active.return_value = False
        self.mock_stat.return_value.st_size = dnsmasq._MAC_ALLOW_LEN

        dnsmasq._configure_removedlist({self.mac})

        self.mock_join.assert_called_with(self.dhcp_hostsdir, self.mac)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value, '%s,ignore\n' % self.mac)

    def test__configure_removedlist_denylist_deny_unknown(self):
        self.mock_introspection_active.return_value = True
        self.mock_stat.return_value.st_size = dnsmasq._MAC_ALLOW_LEN
        CONF.set_override('deny_unknown_macs', True, 'pxe_filter')

        dnsmasq._configure_removedlist({self.mac})

        self.mock_join.assert_called_with(self.dhcp_hostsdir, self.mac)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value, '%s,ignore\n' % self.mac)

    def test__allowlist_mac(self):
        dnsmasq._add_mac_to_allowlist(self.mac)

        self.mock_join.assert_called_once_with(self.dhcp_hostsdir, self.mac)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value, '%s\n' % self.mac)

    def test__denylist_mac(self):
        dnsmasq._add_mac_to_denylist(self.mac)

        self.mock_join.assert_called_once_with(self.dhcp_hostsdir, self.mac)
        self.mock__exclusive_write_or_pass.assert_called_once_with(
            self.mock_join.return_value, '%s,ignore\n' % self.mac)

    def test__get_denylist(self):
        self.mock_listdir.return_value = [self.mac]
        self.mock_stat.return_value.st_size = len('%s,ignore\n' % self.mac)
        denylist, allowlist = dnsmasq._get_deny_allow_lists()

        self.assertEqual({self.mac}, denylist)
        self.mock_listdir.assert_called_once_with(self.dhcp_hostsdir)
        self.mock_join.assert_called_with(self.dhcp_hostsdir, self.mac)
        self.mock_stat.assert_called_with(self.mock_join.return_value)

    def test__get_allowlist(self):
        self.mock_listdir.return_value = [self.mac]
        self.mock_stat.return_value.st_size = len('%s\n' % self.mac)
        denylist, allowlist = dnsmasq._get_deny_allow_lists()

        self.assertEqual({self.mac}, allowlist)
        self.mock_listdir.assert_called_once_with(self.dhcp_hostsdir)
        self.mock_join.assert_called_with(self.dhcp_hostsdir, self.mac)
        self.mock_stat.assert_called_with(self.mock_join.return_value)

    def test__get_no_denylist(self):
        self.mock_listdir.return_value = [self.mac]
        self.mock_stat.return_value.st_size = len('%s\n' % self.mac)
        denylist, allowlist = dnsmasq._get_deny_allow_lists()

        self.assertEqual(set(), denylist)
        self.mock_listdir.assert_called_once_with(self.dhcp_hostsdir)
        self.mock_join.assert_called_with(self.dhcp_hostsdir, self.mac)
        self.mock_stat.assert_called_with(self.mock_join.return_value)

    def test__get_no_allowlist(self):
        self.mock_listdir.return_value = [self.mac]
        self.mock_stat.return_value.st_size = len('%s,ignore\n' % self.mac)
        denylist, allowlist = dnsmasq._get_deny_allow_lists()

        self.assertEqual(set(), allowlist)
        self.mock_listdir.assert_called_once_with(self.dhcp_hostsdir)
        self.mock_join.assert_called_with(self.dhcp_hostsdir, self.mac)
        self.mock_stat.assert_called_with(self.mock_join.return_value)

    def test__purge_dhcp_hostsdir(self):
        self.mock_listdir.return_value = [self.mac]
        dnsmasq._purge_dhcp_hostsdir()

        self.mock_listdir.assert_called_once_with(self.dhcp_hostsdir)
        self.mock_join.assert_called_once_with(self.dhcp_hostsdir, self.mac)
        self.mock_remove.assert_called_once_with('%s/%s' % (self.dhcp_hostsdir,
                                                            self.mac))

    def test_disabled__purge_dhcp_hostsdir(self):
        CONF.set_override('purge_dhcp_hostsdir', False, 'dnsmasq_pxe_filter')
        # NOTE(dtantsur): set_override uses os.path internally
        self.mock_join.reset_mock()

        dnsmasq._purge_dhcp_hostsdir()
        self.mock_listdir.assert_not_called()
        self.mock_join.assert_not_called()
        self.mock_remove.assert_not_called()


class TestSync(DnsmasqTestBase):
    def setUp(self):
        super(TestSync, self).setUp()
        self.mock__get_deny_allow_lists = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_get_deny_allow_lists')).mock
        self.mock__add_mac_to_allowlist = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_add_mac_to_allowlist')).mock
        self.mock__add_mac_to_denylist = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_add_mac_to_denylist')).mock
        self.mock__configure_unknown_hosts = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_configure_unknown_hosts')).mock
        self.mock__configure_removedlist = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, '_configure_removedlist')).mock

        self.mock_ironic = mock.Mock()
        self.mock_utcnow = self.useFixture(
            fixtures.MockPatchObject(dnsmasq.timeutils, 'utcnow')).mock
        self.timestamp_start = datetime.datetime.now(
            datetime.timezone.utc).replace(tzinfo=None)
        self.timestamp_end = (self.timestamp_start +
                              datetime.timedelta(seconds=42))
        self.mock_utcnow.side_effect = [self.timestamp_start,
                                        self.timestamp_end]
        self.mock_log = self.useFixture(
            fixtures.MockPatchObject(dnsmasq, 'LOG')).mock
        get_client_mock = self.useFixture(
            fixtures.MockPatchObject(ir_utils, 'get_client')).mock
        get_client_mock.return_value = self.mock_ironic
        self.mock_get_active_macs = self.useFixture(
            fixtures.MockPatchObject(pxe_filter, 'get_active_macs')).mock
        self.mock_get_active_macs.return_value = set()
        self.mock_active_macs = self.useFixture(
            fixtures.MockPatchObject(node_cache, 'active_macs')).mock
        self.ironic_macs = {'new_mac', 'active_mac'}
        self.active_macs = {'active_mac'}
        self.denylist = {'gone_mac', 'active_mac'}
        self.allowlist = {}
        self.mock__get_deny_allow_lists.return_value = (self.denylist,
                                                        self.allowlist)
        self.mock_ironic.ports.return_value = [
            mock.Mock(address=address) for address in self.ironic_macs]
        self.mock_active_macs.return_value = self.active_macs
        self.mock_should_enable_unknown_hosts = self.useFixture(
            fixtures.MockPatchObject(dnsmasq,
                                     '_should_enable_unknown_hosts')).mock
        self.mock_should_enable_unknown_hosts.return_value = True

    def test__sync_enable_unknown_hosts(self):
        self.mock_should_enable_unknown_hosts.return_value = True

        self.driver._sync(self.mock_ironic)
        self.mock__configure_unknown_hosts.assert_called_once_with()

    def test__sync_not_enable_unknown_hosts(self):
        self.mock_should_enable_unknown_hosts.return_value = False

        self.driver._sync(self.mock_ironic)
        self.mock__configure_unknown_hosts.assert_called_once_with()

    def test__sync(self):
        self.mock_get_active_macs.return_value = {'active_mac'}
        self.driver._sync(self.mock_ironic)

        self.mock_get_active_macs.assert_called_once_with(self.mock_ironic)
        self.mock__add_mac_to_allowlist.assert_called_once_with('active_mac')
        self.mock__add_mac_to_denylist.assert_called_once_with('new_mac')

        self.mock_ironic.ports.assert_called_once_with(
            fields=['address', 'extra'], limit=None)
        self.mock__get_deny_allow_lists.assert_called_once_with()
        self.mock__configure_unknown_hosts.assert_called_once_with()
        self.mock__configure_removedlist.assert_called_once_with({'gone_mac'})
        self.mock_log.debug.assert_has_calls([
            mock.call('Syncing the driver'),
            mock.call('The dnsmasq PXE filter was synchronized (took %s)',
                      self.timestamp_end - self.timestamp_start)
        ])

    @mock.patch('time.sleep', lambda _x: None)
    def test__sync_with_port_list_retries(self):
        self.mock_ironic.ports.side_effect = [
            os_exc.SDKException('boom'),
            [mock.Mock(address=address) for address in self.ironic_macs]
        ]
        self.mock_get_active_macs.return_value = {'active_mac'}
        self.driver._sync(self.mock_ironic)

        self.mock__add_mac_to_allowlist.assert_called_once_with('active_mac')
        self.mock__add_mac_to_denylist.assert_called_once_with('new_mac')

        self.mock_ironic.ports.assert_called_with(fields=['address', 'extra'],
                                                  limit=None)
        self.mock_get_active_macs.assert_called_once_with(self.mock_ironic)
        self.mock__get_deny_allow_lists.assert_called_once_with()
        self.mock__configure_removedlist.assert_called_once_with({'gone_mac'})
        self.mock_log.debug.assert_has_calls([
            mock.call('Syncing the driver'),
            mock.call('The dnsmasq PXE filter was synchronized (took %s)',
                      self.timestamp_end - self.timestamp_start)
        ])

    @mock.patch('time.sleep', lambda _x: None)
    def test__sync_ironic_unavailable(self):
        self.mock_ironic.ports.side_effect = os_exc.SDKException('boom')
        self.driver._sync(self.mock_ironic)
        self.mock__add_mac_to_allowlist.assert_not_called()
        self.mock__add_mac_to_denylist.assert_not_called()

        self.mock_ironic.ports.assert_called_with(fields=['address', 'extra'],
                                                  limit=None)
        self.mock_get_active_macs.assert_called_once_with(self.mock_ironic)
        self.mock__get_deny_allow_lists.assert_not_called()
        self.mock__configure_removedlist.assert_not_called()
        self.mock_log.debug.assert_called_once_with('Syncing the driver')
        self.mock_log.exception.assert_called_once_with(
            "Could not list ironic ports, can not sync dnsmasq PXE filter")


class Test_Execute(test_base.BaseTest):
    def setUp(self):
        super(Test_Execute, self).setUp()
        self.mock_execute = self.useFixture(
            fixtures.MockPatchObject(dnsmasq.processutils, 'execute')
        ).mock
        CONF.set_override('rootwrap_config', '/path/to/rootwrap.conf')
        self.rootwrap_cmd = dnsmasq._ROOTWRAP_COMMAND.format(
            rootwrap_config=CONF.rootwrap_config)
        self.useFixture(fixtures.MonkeyPatch(
            'ironic_inspector.pxe_filter.dnsmasq._ROOTWRAP_COMMAND',
            self.rootwrap_cmd))
        self.command = 'foobar baz'

    def test__execute(self):
        dnsmasq._execute(self.command)
        self.mock_execute.assert_called_once_with(
            self.command, run_as_root=True, shell=True,
            check_exit_code=True, root_helper=self.rootwrap_cmd)

    def test__execute_ignoring_errors(self):
        dnsmasq._execute(self.command, ignore_errors=True)
        self.mock_execute.assert_called_once_with(
            self.command, run_as_root=True, shell=True,
            check_exit_code=False, root_helper=self.rootwrap_cmd)

    def test__execute_empty(self):
        dnsmasq._execute()

        self.mock_execute.assert_not_called()
