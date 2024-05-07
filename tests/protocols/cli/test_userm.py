import re
from hashlib import md5
from .test_jcli import jCliWithoutAuthTestCases
from jasmin.routing.jasminApi import MtMessagingCredential, SmppsCredential
from twisted.internet import defer

class UserTestCases(jCliWithoutAuthTestCases):
    def add_user(self, finalPrompt, extraCommands=[], GID=None, Username=None):
        sessionTerminated = False
        commands = []

        if GID:
            commands.append({'command': 'group -a'})
            commands.append({'command': 'gid %s' % GID})
            commands.append({'command': 'ok', 'expect': r'Successfully added Group \['})

        commands.append({'command': 'user -a', 'expect': r'Adding a new User\: \(ok\: save, ko\: exit\)'})
        if GID:
            commands.append({'command': 'gid %s' % GID})
        if Username:
            password = 'RND_PWD'
            commands.append({'command': 'username %s' % Username})
            commands.append({'command': 'password %s' % password})
        for extraCommand in extraCommands:
            commands.append(extraCommand)

            if extraCommand['command'] in ['ok', 'ko']:
                sessionTerminated = True

        if not sessionTerminated:
            commands.append({'command': 'ok', 'expect': r'Successfully added User \['})

        return self._test(finalPrompt, commands)

    def update_user(self, finalPrompt, uid, extraCommands=[]):
        sessionTerminated = False
        commands = []

        commands.append(
            {'command': 'user -u %s' % uid, 'expect': r'Updating User id \[%s\]\: \(ok\: save, ko\: exit\)' % uid})
        for extraCommand in extraCommands:
            commands.append(extraCommand)

            if extraCommand['command'] in ['ok', 'ko']:
                sessionTerminated = True

        if not sessionTerminated:
            commands.append({'command': 'ok', 'expect': r'Successfully updated User \['})

        return self._test(finalPrompt, commands)


class BasicTestCases(UserTestCases):
    @defer.inlineCallbacks
    def test_list(self):
        commands = [{'command': 'user -l', 'expect': r'Total Users: 0'}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_add_with_minimum_args(self):
        extraCommands = [{'command': 'uid user_59'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

    @defer.inlineCallbacks
    def test_add_with_empty_uid(self):
        extraCommands = [{'command': 'uid  '},
                         {'command': 'ok', 'expect': r'Error: User uid syntax is invalid'}, ]
        yield self.add_user(r'> ', extraCommands, GID='AnyGroup', Username='AnyUsername')

    @defer.inlineCallbacks
    def test_add_with_invalid_uid(self):
        extraCommands = [{'command': 'uid With Space'},
                         {'command': 'ok', 'expect': r'Error: User uid syntax is invalid'}, ]
        yield self.add_user(r'> ', extraCommands, GID='AnyGroup', Username='AnyUsername')

    @defer.inlineCallbacks
    def test_add_with_invalid_username(self):
        extraCommands = [{'command': 'uid AnyUid'},
                         {'command': 'username With Space'},
                         {'command': 'password anything'},
                         {'command': 'ok', 'expect': r'Error: User username syntax is invalid'}, ]
        yield self.add_user(r'> ', extraCommands, GID='AnyGroup')

    @defer.inlineCallbacks
    def test_add_without_minimum_args(self):
        extraCommands = [{'command': 'ok',
                          'expect': r'You must set User id \(uid\), group \(gid\), username and password before saving !'}]
        yield self.add_user(r'> ', extraCommands)

    @defer.inlineCallbacks
    def test_add_invalid_userkey(self):
        extraCommands = [{'command': 'uid user_2'},
                         {'command': 'anykey anyvalue', 'expect': r'Unknown User key: anykey'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

    @defer.inlineCallbacks
    def test_cancel_add(self):
        extraCommands = [{'command': 'uid user_3'},
                         {'command': 'ko'}, ]
        yield self.add_user(r'jcli : ', extraCommands)

    @defer.inlineCallbacks
    def test_add_and_list(self):
        extraCommands = [{'command': 'uid user_4'}]
        yield self.add_user('jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        expectedList = ['#User id          Group id         Username         Balance MT SMS Throughput',
                        '#user_4           AnyGroup         AnyUsername      ND \(\!\)  ND \(\!\) ND/ND',
                        'Total Users: 1']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_add_and_list_group_users(self):
        # Add 2 users
        gid1 = 'gid1'
        uid1 = 'user_4-1'
        username1 = 'username1'
        extraCommands = [{'command': 'uid %s' % uid1}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid1, Username=username1)

        gid2 = 'gid2'
        uid2 = 'user_4-2'
        username2 = 'username2'
        extraCommands = [{'command': 'uid %s' % uid2}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid2, Username=username2)

        # List all users
        expectedList = ['#User id          Group id         Username         Balance MT SMS Throughput',
                        '#%s %s %s %s %s %s' % (
                        uid1.ljust(16), gid1.ljust(16), username1.ljust(16), 'ND \(\!\) '.ljust(7),
                        'ND \(\!\)'.ljust(6), 'ND/ND'.ljust(8)),
                        '#%s %s %s %s %s %s' % (
                        uid2.ljust(16), gid2.ljust(16), username2.ljust(16), 'ND \(\!\) '.ljust(7),
                        'ND \(\!\)'.ljust(6), 'ND/ND'.ljust(8)),
                        'Total Users: 2']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # List gid1 only users
        expectedList = ['#User id          Group id         Username         Balance MT SMS Throughput',
                        '#%s %s %s %s %s %s' % (
                        uid1.ljust(16), gid1.ljust(16), username1.ljust(16), 'ND \(\!\) '.ljust(7),
                        'ND \(\!\)'.ljust(6), 'ND/ND'.ljust(8)),
                        'Total Users in group \[%s\]\: 1' % gid1]
        commands = [{'command': 'user -l %s' % gid1, 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_add_cancel_and_list(self):
        extraCommands = [{'command': 'uid user_5'},
                         {'command': 'ko'}, ]
        yield self.add_user(r'jcli : ', extraCommands)

        commands = [{'command': 'user -l', 'expect': r'Total Users: 0'}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_add_and_show(self):
        uid = 'user_6'
        gid = 'group_bla'
        username = 'foobar'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user('jcli : ', extraCommands, GID=gid, Username=username)

        expectedList = [
            'uid %s' % uid,
            'gid %s' % gid,
            'username %s' % username,
            'mt_messaging_cred authorization http_send True',
            'mt_messaging_cred authorization http_balance True',
            'mt_messaging_cred authorization http_rate True',
            'mt_messaging_cred authorization http_bulk False',
            'mt_messaging_cred authorization smpps_send True',
            'mt_messaging_cred authorization http_long_content True',
            'mt_messaging_cred authorization dlr_level True',
            'mt_messaging_cred authorization http_dlr_method True',
            'mt_messaging_cred authorization src_addr True',
            'mt_messaging_cred authorization priority True',
            'mt_messaging_cred authorization validity_period True',
            'mt_messaging_cred authorization schedule_delivery_time True',
            'mt_messaging_cred authorization hex_content True',
            'mt_messaging_cred valuefilter dst_addr .*',
            'mt_messaging_cred valuefilter src_addr .*',
            'mt_messaging_cred valuefilter priority \^\[0-3\]\$',
            'mt_messaging_cred valuefilter validity_period %s' % re.escape('^\d+$'),
            'mt_messaging_cred valuefilter content .*',
            'mt_messaging_cred defaultvalue src_addr None',
            'mt_messaging_cred quota balance ND',
            'mt_messaging_cred quota early_percent ND',
            'mt_messaging_cred quota sms_count ND',
            'mt_messaging_cred quota http_throughput ND',
            'mt_messaging_cred quota smpps_throughput ND',
            'smpps_cred authorization bind True',
            'smpps_cred quota max_bindings ND',
        ]
        commands = [{'command': 'user -s %s' % uid, 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_show_invalid_uid(self):
        commands = [{'command': 'user -s invalid_uid', 'expect': r'Unknown User\: invalid_uid'}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_update_uid(self):
        uid = 'user_7-1'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        commands = [
            {'command': 'user -u user_7-1', 'expect': r'Updating User id \[%s\]\: \(ok\: save, ko\: exit\)' % uid},
            {'command': 'uid 2222', 'expect': r'User id can not be modified !'}]
        yield self._test(r'> ', commands)

    @defer.inlineCallbacks
    def test_update_username(self):
        uid = 'user_7-2'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        commands = [
            {'command': 'user -u user_7-2', 'expect': r'Updating User id \[%s\]\: \(ok\: save, ko\: exit\)' % uid},
            {'command': 'username AnotherUsername', 'expect': r'User username can not be modified !'}]
        yield self._test(r'> ', commands)

    @defer.inlineCallbacks
    def test_update_gid(self):
        uid = 'user_8'
        gid = 'CurrentGID'
        newGID = 'NewGID'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid, Username='AnyUsername')

        # List
        expectedList = ['#User id          Group id         Username         Balance MT SMS',
                        '#%s %s AnyUsername      %s %s' % (
                        uid.ljust(16), gid.ljust(16), 'ND \(\!\) '.ljust(7), 'ND \(\!\)'.ljust(6)),
                        'Total Users: 1']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # Add a new group
        commands = [{'command': 'group -a'},
                    {'command': 'gid %s' % newGID},
                    {'command': 'ok', 'expect': r'Successfully added Group \['}]
        yield self._test(r'jcli : ', commands)

        # Place the user into this new group
        commands = [
            {'command': 'user -u %s' % uid, 'expect': r'Updating User id \[%s\]\: \(ok\: save, ko\: exit\)' % uid},
            {'command': 'gid %s' % newGID},
            {'command': 'ok', 'expect': r'Successfully updated User \[%s\]' % uid}]
        yield self._test(r'jcli : ', commands)

        # List again
        expectedList = ['#User id          Group id         Username         Balance MT SMS',
                        '#%s %s AnyUsername      %s %s' % (
                        uid.ljust(16), newGID.ljust(16), 'ND \(\!\) '.ljust(7), 'ND \(\!\)'.ljust(6)),
                        'Total Users: 1']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_update_and_show(self):
        uid = 'user_9'
        gid = 'CurrentGID'
        username = 'AnyUsername'
        newGID = 'NewGID'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid, Username=username)

        # Add a new group
        commands = [{'command': 'group -a'},
                    {'command': 'gid %s' % newGID},
                    {'command': 'ok', 'expect': r'Successfully added Group \['}]
        yield self._test(r'jcli : ', commands)

        # Place the user into this new group
        commands = [
            {'command': 'user -u %s' % uid, 'expect': r'Updating User id \[%s\]\: \(ok\: save, ko\: exit\)' % uid},
            {'command': 'gid %s' % newGID},
            {'command': 'ok', 'expect': r'Successfully updated User \[%s\]' % uid}]
        yield self._test(r'jcli : ', commands)

        # Show and assert
        expectedList = [
            'uid %s' % uid,
            'gid %s' % newGID,
            'username %s' % username,
            'mt_messaging_cred authorization http_send True',
            'mt_messaging_cred authorization http_balance True',
            'mt_messaging_cred authorization http_rate True',
            'mt_messaging_cred authorization http_bulk False',
            'mt_messaging_cred authorization smpps_send True',
            'mt_messaging_cred authorization http_long_content True',
            'mt_messaging_cred authorization dlr_level True',
            'mt_messaging_cred authorization http_dlr_method True',
            'mt_messaging_cred authorization src_addr True',
            'mt_messaging_cred authorization priority True',
            'mt_messaging_cred authorization validity_period True',
            'mt_messaging_cred authorization schedule_delivery_time True',
            'mt_messaging_cred authorization hex_content True',
            'mt_messaging_cred valuefilter dst_addr .*',
            'mt_messaging_cred valuefilter src_addr .*',
            'mt_messaging_cred valuefilter priority \^\[0-3\]\$',
            'mt_messaging_cred valuefilter validity_period %s' % re.escape('^\d+$'),
            'mt_messaging_cred valuefilter content .*',
            'mt_messaging_cred defaultvalue src_addr None',
            'mt_messaging_cred quota balance ND',
            'mt_messaging_cred quota early_percent ND',
            'mt_messaging_cred quota sms_count ND',
            'mt_messaging_cred quota http_throughput ND',
            'mt_messaging_cred quota smpps_throughput ND',
            'smpps_cred authorization bind True',
            'smpps_cred quota max_bindings ND',
        ]
        commands = [{'command': 'user -s %s' % uid, 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_remove_invalid_uid(self):
        commands = [{'command': 'user -r invalid_uid', 'expect': r'Unknown User\: invalid_uid'}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_remove(self):
        uid = 'user_309'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        commands = [{'command': 'user -r %s' % uid, 'expect': r'Successfully removed User id\:%s' % uid}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_remove_and_list(self):
        # Add
        uid = 'user_318'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        # List
        expectedList = ['#User id          Group id         Username         Balance MT SMS Throughput',
                        '#%s AnyGroup         AnyUsername      %s %s %s' % (
                        uid.ljust(16), 'ND \(\!\) '.ljust(7), 'ND \(\!\)'.ljust(6), 'ND/ND'.ljust(8)),
                        'Total Users: 1']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # Remove
        commands = [{'command': 'user -r %s' % uid, 'expect': r'Successfully removed User id\:%s' % uid}]
        yield self._test(r'jcli : ', commands)

        # List again
        commands = [{'command': 'user -l', 'expect': r'Total Users: 0'}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_remove_group_will_remove_its_users(self):
        gid = 'a_group'
        # Add 2 users to gid
        uid1 = 'user_341-1'
        username1 = 'username1'
        extraCommands = [{'command': 'uid %s' % uid1}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid, Username=username1)

        uid2 = 'user_341-2'
        username2 = 'username2'
        extraCommands = [{'command': 'uid %s' % uid2}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid, Username=username2)

        # List
        expectedList = ['#User id          Group id         Username         Balance MT SMS',
                        '#%s %s %s %s %s' % (uid1.ljust(16), gid.ljust(16), username1.ljust(16), 'ND \(\!\) '.ljust(7),
                                             'ND \(\!\)'.ljust(6)),
                        '#%s %s %s %s %s' % (uid2.ljust(16), gid.ljust(16), username2.ljust(16), 'ND \(\!\) '.ljust(7),
                                             'ND \(\!\)'.ljust(6)),
                        'Total Users: 2']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # Remove group
        commands = [{'command': 'group -r %s' % gid, 'expect': r'Successfully removed Group id\:%s' % gid}]
        yield self._test(r'jcli : ', commands)

        # List again
        commands = [{'command': 'user -l', 'expect': r'Total Users: 0'}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_crypted_password(self):
        """Related to #103"""
        uid = 'user_371'
        add_password = 'oldpwd'
        update_password = 'newpwd'
        extraCommands = [{'command': 'uid %s' % uid},
                         {'command': 'password %s' % add_password}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        # assert password is store in crypted format
        self.assertEqual(1, len(self.RouterPB_f.users))
        self.assertEqual(md5(add_password.encode('ascii')).digest(), self.RouterPB_f.users[0].password)

        commands = [{'command': 'user -u %s' % uid},
                    {'command': 'password %s' % update_password},
                    {'command': 'ok'}]
        yield self._test(r'jcli : ', commands)

        # assert password is store in crypted format
        self.assertEqual(1, len(self.RouterPB_f.users))
        self.assertEqual(md5(update_password.encode('ascii')).digest(), self.RouterPB_f.users[0].password)

    @defer.inlineCallbacks
    def test_enabled_disable(self):
        "Related to #306"
        uid = 'user_393'
        gid = 'AnyGroup'
        username = 'AnyUsername'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid, Username=username)

        # Disable user
        commands = [{'command': 'user -d %s' % uid,
                     'expect': r'Successfully disabled User id\:%s' % uid}]
        yield self._test(r'jcli : ', commands)

        # List
        expectedList = ['#User id          Group id         Username         Balance MT SMS',
                        '#!%s%s' % (uid.ljust(16), gid.ljust(16)),
                        'Total Users: 1']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # Enable user
        commands = [{'command': 'user -e %s' % uid,
                     'expect': r'Successfully enabled User id\:%s' % uid}]
        yield self._test(r'jcli : ', commands)

        # List
        expectedList = ['#User id          Group id         Username         Balance MT SMS',
                        '#%s %s' % (uid.ljust(16), gid.ljust(16)),
                        'Total Users: 1']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # Disable group
        commands = [{'command': 'group -d %s' % gid,
                     'expect': r'Successfully disabled Group id\:%s' % gid}]
        yield self._test(r'jcli : ', commands)

        # List
        expectedList = ['#User id          Group id         Username         Balance MT SMS',
                        '#%s !%s' % (uid.ljust(16), gid.ljust(16)),
                        'Total Users: 1']
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_smpp_unbind(self):
        """Related to #294"""
        uid = 'user_437'
        gid = 'AnyGroup'
        username = 'AnyUsername'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid, Username=username)

        # Unbind user
        commands = [{'command': 'user --smpp-unbind %s' % uid,
                     'expect': r'Successfully unbound User id\:%s' % uid}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_smpp_ban(self):
        """Related to #305"""
        uid = 'user_450'
        gid = 'AnyGroup'
        username = 'AnyUsername'
        extraCommands = [{'command': 'uid %s' % uid}]
        yield self.add_user(r'jcli : ', extraCommands, GID=gid, Username=username)

        # Unbind user
        commands = [{'command': 'user --smpp-ban %s' % uid,
                     'expect': r'Successfully unbound and banned User id\:%s' % uid}]
        yield self._test(r'jcli : ', commands)


class MtMessagingCredentialTestCases(UserTestCases):
    def _get_str_repattern(self, pattern):
        if isinstance(pattern, bytes):
            return pattern.decode()
        else:
            return pattern

    @defer.inlineCallbacks
    def _test_user_with_MtMessagingCredential(self, uid, gid, username, mtcred):
        if mtcred.getQuota('balance') is None:
            assertBalance = 'ND'
        else:
            assertBalance = str(float(mtcred.getQuota('balance')))

        if mtcred.getQuota('submit_sm_count') is None:
            assertSmsCount = 'ND'
        else:
            assertSmsCount = str(mtcred.getQuota('submit_sm_count'))

        if mtcred.getQuota('early_decrement_balance_percent') is None:
            assertEarlyPercent = 'ND'
        else:
            assertEarlyPercent = str(float(mtcred.getQuota('early_decrement_balance_percent')))

        if mtcred.getQuota('http_throughput') is None:
            assertHttpThroughput = 'ND'
        else:
            assertHttpThroughput = str(int(mtcred.getQuota('http_throughput')))

        if mtcred.getQuota('smpps_throughput') is None:
            assertSmppsThroughput = 'ND'
        else:
            assertSmppsThroughput = str(int(mtcred.getQuota('smpps_throughput')))

        # Show and assert
        expectedList = [
            'uid %s' % uid,
            'gid %s' % gid,
            'username %s' % username,
            'mt_messaging_cred authorization http_send %s' % mtcred.getAuthorization('http_send'),
            'mt_messaging_cred authorization http_balance %s' % mtcred.getAuthorization('http_balance'),
            'mt_messaging_cred authorization http_rate %s' % mtcred.getAuthorization('http_rate'),
            'mt_messaging_cred authorization http_bulk %s' % mtcred.getAuthorization('http_bulk'),
            'mt_messaging_cred authorization smpps_send %s' % mtcred.getAuthorization('smpps_send'),
            'mt_messaging_cred authorization http_long_content %s' % mtcred.getAuthorization(
                'http_long_content'),
            'mt_messaging_cred authorization dlr_level %s' % mtcred.getAuthorization('set_dlr_level'),
            'mt_messaging_cred authorization http_dlr_method %s' % mtcred.getAuthorization(
                'http_set_dlr_method'),
            'mt_messaging_cred authorization src_addr %s' % mtcred.getAuthorization('set_source_address'),
            'mt_messaging_cred authorization priority %s' % mtcred.getAuthorization('set_priority'),
            'mt_messaging_cred authorization validity_period %s' % mtcred.getAuthorization(
                'set_validity_period'),
            'mt_messaging_cred authorization schedule_delivery_time %s' % mtcred.getAuthorization(
                'set_schedule_delivery_time'),
            'mt_messaging_cred authorization hex_content %s' % mtcred.getAuthorization('set_hex_content'),
            'mt_messaging_cred valuefilter dst_addr %s' % re.escape(
                self._get_str_repattern(mtcred.getValueFilter('destination_address').pattern)),
            'mt_messaging_cred valuefilter src_addr %s' % re.escape(
                self._get_str_repattern(mtcred.getValueFilter('source_address').pattern)),
            'mt_messaging_cred valuefilter priority %s' % re.escape(
                self._get_str_repattern(mtcred.getValueFilter('priority').pattern)),
            'mt_messaging_cred valuefilter validity_period %s' % re.escape(
                self._get_str_repattern(mtcred.getValueFilter('validity_period').pattern)),
            'mt_messaging_cred valuefilter content %s' % re.escape(
                self._get_str_repattern(mtcred.getValueFilter('content').pattern)),
            'mt_messaging_cred defaultvalue src_addr %s' % mtcred.getDefaultValue('source_address'),
            'mt_messaging_cred quota balance %s' % assertBalance,
            'mt_messaging_cred quota early_percent %s' % assertEarlyPercent,
            'mt_messaging_cred quota sms_count %s' % assertSmsCount,
            'mt_messaging_cred quota http_throughput %s' % assertHttpThroughput,
            'mt_messaging_cred quota smpps_throughput %s' % assertSmppsThroughput,
            'smpps_cred authorization bind True',
            'smpps_cred quota max_bindings ND',
        ]
        commands = [{'command': 'user -s %s' % uid, 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # List and assert
        if assertBalance == 'ND' and assertSmsCount == 'ND':
            assertBalance = 'ND \(\!\) '
            assertSmsCount = 'ND \(\!\)'
        expectedList = ['#.*',
                        '#%s %s %s %s %s' % (uid.ljust(16), gid.ljust(16), username.ljust(16), assertBalance.ljust(7),
                                             assertSmsCount.ljust(6)),
                        ]
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_default(self):
        """Default user is created with a default MtMessagingCredential() instance"""

        # Assert User adding
        extraCommands = [{'command': 'uid user_548'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_MtMessagingCredential('user_548', 'AnyGroup', 'AnyUsername', MtMessagingCredential())

        # Assert User updating
        extraCommands = [{'command': 'password anypassword'}]
        yield self.update_user(r'jcli : ', 'user_548', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_548', 'AnyGroup', 'AnyUsername', MtMessagingCredential())

    @defer.inlineCallbacks
    def test_authorization(self):
        _cred = MtMessagingCredential()
        _cred.setAuthorization('http_send', False)
        _cred.setAuthorization('http_balance', False)
        _cred.setAuthorization('http_bulk', True)

        # Assert User adding
        extraCommands = [{'command': 'uid user_564'},
                         {'command': 'mt_messaging_cred authorization http_send no'},
                         {'command': 'mt_messaging_cred authorization http_balance no'},
                         {'command': 'mt_messaging_cred authorization http_bulk yes'},
                         ]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_MtMessagingCredential('user_564', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setAuthorization('http_send', True)
        _cred.setAuthorization('http_balance', True)
        _cred.setAuthorization('http_bulk', False)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred authorization http_send 1'},
                         {'command': 'mt_messaging_cred authorization http_balance yes'},
                         {'command': 'mt_messaging_cred authorization http_bulk 0'},
                         ]
        yield self.update_user(r'jcli : ', 'user_564', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_564', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_valuefilter(self):
        _cred = MtMessagingCredential()
        _cred.setValueFilter('content', '^HELLO$')

        # Assert User adding
        extraCommands = [{'command': 'uid user_589'},
                         {'command': 'mt_messaging_cred valuefilter content ^HELLO$'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_MtMessagingCredential('user_589', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setValueFilter('content', '^WORLD$')
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred valuefilter content ^WORLD$'}]
        yield self.update_user(r'jcli : ', 'user_589', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_589', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_defaultvalue(self):
        _cred = MtMessagingCredential()
        _cred.setDefaultValue('source_address', 'World')

        # Assert User adding
        extraCommands = [{'command': 'uid user_606'},
                         {'command': 'mt_messaging_cred defaultvalue src_addr World'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_MtMessagingCredential('user_606', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setDefaultValue('source_address', 'HELLO')
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred defaultvalue src_addr HELLO'}]
        yield self.update_user(r'jcli : ', 'user_606', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_606', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_quota(self):
        _cred = MtMessagingCredential()
        _cred.setQuota('balance', 40.3)

        # Assert User adding
        extraCommands = [{'command': 'uid user_623'},
                         {'command': 'mt_messaging_cred quota balance %s' % _cred.getQuota('balance')}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_MtMessagingCredential('user_623', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setQuota('balance', 42)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota balance %s' % _cred.getQuota('balance')}]
        yield self.update_user(r'jcli : ', 'user_623', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_623', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_increase_decrease_quota_float(self):
        # Add with initial quota
        extraCommands = [{'command': 'uid user_637'},
                         {'command': 'mt_messaging_cred quota balance 100'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        _cred = MtMessagingCredential()
        _cred.setQuota('balance', 19.999999999999996)

        # Assert User increasing/decreasing quota
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota balance -90.2'}]
        yield self.update_user(r'jcli : ', 'user_637', extraCommands)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota balance +10.2'}]
        yield self.update_user(r'jcli : ', 'user_637', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_637', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_increase_decrease_quota_int(self):
        # Add with initial quota
        extraCommands = [{'command': 'uid user_655'},
                         {'command': 'mt_messaging_cred quota sms_count 100'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        _cred = MtMessagingCredential()
        _cred.setQuota('submit_sm_count', 20)

        # Assert User increasing/decreasing quota
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota sms_count -90'}]
        yield self.update_user(r'jcli : ', 'user_655', extraCommands)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota sms_count +10'}]
        yield self.update_user(r'jcli : ', 'user_655', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_655', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_increase_decrease_quota_invalid_type(self):
        # Add with initial quota
        extraCommands = [{'command': 'uid user_673'},
                         {'command': 'mt_messaging_cred quota sms_count 100'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        # Quota will remain the same since the following updates are using incorrect type
        _cred = MtMessagingCredential()
        _cred.setQuota('submit_sm_count', 100)

        # Assert User increasing/decreasing quota
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota sms_count -90.2'}]
        yield self.update_user(r'jcli : ', 'user_673', extraCommands)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota sms_count +10.2'}]
        yield self.update_user(r'jcli : ', 'user_673', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_673', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_increase_unlimited_quota(self):
        """Related to #403"""
        # Add user without initial quota
        extraCommands = [{'command': 'uid user_693'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        _cred = MtMessagingCredential()
        _cred.setQuota('submit_sm_count', 20)
        _cred.setQuota('balance', 11.2)

        # Assert User increasing/decreasing quota
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota sms_count +20'}]
        yield self.update_user(r'jcli : ', 'user_693', extraCommands)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'mt_messaging_cred quota balance +11.2'}]
        yield self.update_user(r'jcli : ', 'user_693', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_693', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_all(self):
        _cred = MtMessagingCredential()
        _cred.setAuthorization('http_send', False)
        _cred.setAuthorization('http_long_content', False)
        _cred.setAuthorization('set_dlr_level', False)
        _cred.setAuthorization('http_set_dlr_method', False)
        _cred.setAuthorization('set_source_address', False)
        _cred.setAuthorization('set_priority', False)
        _cred.setAuthorization('set_validity_period', False)
        _cred.setAuthorization('set_schedule_delivery_time', False)
        _cred.setAuthorization('set_hex_content', False)
        _cred.setValueFilter('destination_address', '^HELLO$')
        _cred.setValueFilter('source_address', '^World$')
        _cred.setValueFilter('priority', '^1$')
        _cred.setValueFilter('validity_period', '^1$')
        _cred.setValueFilter('content', '[0-9].*')
        _cred.setDefaultValue('source_address', 'BRAND NAME')
        _cred.setQuota('balance', 40.3)
        _cred.setQuota('http_throughput', 2.2)
        _cred.setQuota('smpps_throughput', 0.5)

        # Assert User adding
        extraCommands = [{'command': 'uid user_731'},
                         {'command': 'mt_messaging_cred Authorization http_send no'},
                         {'command': 'mt_messaging_cred authorization http_long_content n'},
                         {'command': 'mt_messaging_cred authorization dlr_level 0'},
                         {'command': 'mt_messaging_cred authorization http_dlr_method NO'},
                         {'command': 'mt_messaging_cred authorization src_addr false'},
                         {'command': 'mt_messaging_cred authorization priority f'},
                         {'command': 'mt_messaging_cred authorization validity_period f'},
                         {'command': 'mt_messaging_cred authorization schedule_delivery_time f'},
                         {'command': 'mt_messaging_cred authorization hex_content f'},
                         {'command': 'mt_messaging_cred Valuefilter dst_addr ^HELLO$'},
                         {'command': 'mt_messaging_cred valuefilter src_addr ^World$'},
                         {'command': 'mt_messaging_cred valuefilter priority ^1$'},
                         {'command': 'mt_messaging_cred valuefilter validity_period ^1$'},
                         {'command': 'mt_messaging_cred valuefilter content [0-9].*'},
                         {'command': 'mt_messaging_cred Defaultvalue src_addr BRAND NAME'},
                         {'command': 'mt_messaging_cred Quota balance 40.3'},
                         {'command': 'mt_messaging_cred quota http_throughput 2.2'},
                         {'command': 'mt_messaging_cred quota smpps_throughput 0.5'},
                         ]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_MtMessagingCredential('user_731', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setAuthorization('http_send', True)
        _cred.setAuthorization('http_long_content', True)
        _cred.setAuthorization('set_dlr_level', True)
        _cred.setAuthorization('http_set_dlr_method', True)
        _cred.setAuthorization('set_source_address', True)
        _cred.setAuthorization('set_priority', True)
        _cred.setAuthorization('set_validity_period', True)
        _cred.setAuthorization('set_schedule_delivery_time', True)
        _cred.setAuthorization('set_hex_content', True)
        _cred.setValueFilter('destination_address', '^WORLD$')
        _cred.setValueFilter('source_address', '^HELLO$')
        _cred.setValueFilter('priority', '^2$')
        _cred.setValueFilter('validity_period', '^2$')
        _cred.setValueFilter('content', '[2-6].*')
        _cred.setDefaultValue('source_address', 'SEXY NAME')
        _cred.setQuota('balance', 66)
        extraCommands = [{'command': 'mt_messaging_cred authorization http_send yes'},
                         {'command': 'mt_messaging_cred authorization http_long_content y'},
                         {'command': 'mt_messaging_cred authorization dlr_level 1'},
                         {'command': 'mt_messaging_cred authorization http_dlr_method YES'},
                         {'command': 'mt_messaging_cred authorization src_addr true'},
                         {'command': 'mt_messaging_cred authorization priority t'},
                         {'command': 'mt_messaging_cred authorization validity_period t'},
                         {'command': 'mt_messaging_cred authorization schedule_delivery_time t'},
                         {'command': 'mt_messaging_cred authorization hex_content t'},
                         {'command': 'mt_messaging_cred valuefilter dst_addr ^WORLD$'},
                         {'command': 'mt_messaging_cred valuefilter src_addr ^HELLO$'},
                         {'command': 'mt_messaging_cred valuefilter priority ^2$'},
                         {'command': 'mt_messaging_cred valuefilter validity_period ^2$'},
                         {'command': 'mt_messaging_cred valuefilter content [2-6].*'},
                         {'command': 'mt_messaging_cred defaultvalue src_addr SEXY NAME'},
                         {'command': 'mt_messaging_cred quota balance 66'}]
        yield self.update_user(r'jcli : ', 'user_731', extraCommands)
        yield self._test_user_with_MtMessagingCredential('user_731', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_invalid_syntax(self):
        # Assert User adding
        extraCommands = [{'command': 'uid user_792'},
                         {'command': 'mt_messaging_red authorization http_send no',
                          'expect': 'Unknown User key: mt_messaging_red'},
                         {'command': 'mt_messaging_cred quta balance 40.3',
                          'expect': 'Error: invalid section name: quta, possible values: Authorization, ValueFilter, DefaultValue, Quota'},
                         {'command': 'mt_messaging_cred DeefaultValue Anything AnyValue',
                          'expect': 'Error: invalid section name: deefaultvalue, possible values: Authorization, ValueFilter, DefaultValue, Quota'},
                         {'command': 'mt_messaging_cred defaultvalue Anything AnyValue',
                          'expect': 'Error: invalid key: anything, possible keys: src_addr'},
                         {'command': 'mt_messaging_cred quota balance ',
                          'expect': 'Error: expected syntax: mt_messaging_cred section key value'},
                         {'command': 'mt_messaging_cred authorization http_send ',
                          'expect': 'Error: expected syntax: mt_messaging_cred section key value'},
                         ]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        # Assert User updating
        extraCommands = [{'command': 'password any_password'},
                         {'command': 'mt_messaging_red authorization http_send no',
                          'expect': 'Unknown User key: mt_messaging_red'},
                         {'command': 'mt_messaging_cred quta balance 40.3',
                          'expect': 'Error: invalid section name: quta, possible values: Authorization, ValueFilter, DefaultValue, Quota'},
                         {'command': 'mt_messaging_cred DeefaultValue Anything AnyValue',
                          'expect': 'Error: invalid section name: deefaultvalue, possible values: Authorization, ValueFilter, DefaultValue, Quota'},
                         {'command': 'mt_messaging_cred defaultvalue Anything AnyValue',
                          'expect': 'Error: invalid key: anything, possible keys: src_addr'},
                         {'command': 'mt_messaging_cred quota balance ',
                          'expect': 'Error: expected syntax: mt_messaging_cred section key value'},
                         {'command': 'mt_messaging_cred authorization http_send ',
                          'expect': 'Error: expected syntax: mt_messaging_cred section key value'},
                         ]
        yield self.update_user(r'jcli : ', 'user_792', extraCommands)


class SmppsCredentialTestCases(UserTestCases):
    @defer.inlineCallbacks
    def _test_user_with_SmppsCredential(self, uid, gid, username, smppscred):
        if smppscred.getQuota('max_bindings') is None:
            assertMaxBindings = 'ND'
        else:
            assertMaxBindings = str(int(smppscred.getQuota('max_bindings')))

        # Show and assert
        expectedList = ['uid %s' % uid,
                        'gid %s' % gid,
                        'username %s' % username,
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'mt_messaging_cred ',
                        'smpps_cred authorization bind %s' % smppscred.getAuthorization('bind'),
                        'smpps_cred quota max_bindings %s' % assertMaxBindings,
                        ]
        commands = [{'command': 'user -s %s' % uid, 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

        # List and assert
        expectedList = ['#.*',
                        '#%s %s %s' % (uid.ljust(16), gid.ljust(16), username.ljust(16))
                        ]
        commands = [{'command': 'user -l', 'expect': expectedList}]
        yield self._test(r'jcli : ', commands)

    @defer.inlineCallbacks
    def test_default(self):
        """Default user is created with a default SmppsCredential() instance"""

        # Assert User adding
        extraCommands = [{'command': 'uid user_878'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_SmppsCredential('user_878', 'AnyGroup', 'AnyUsername', SmppsCredential())

        # Assert User updating
        extraCommands = [{'command': 'password anypassword'}]
        yield self.update_user(r'jcli : ', 'user_878', extraCommands)
        yield self._test_user_with_SmppsCredential('user_878', 'AnyGroup', 'AnyUsername', SmppsCredential())

    @defer.inlineCallbacks
    def test_authorization(self):
        _cred = SmppsCredential()
        _cred.setAuthorization('bind', False)

        # Assert User adding
        extraCommands = [{'command': 'uid user_892'},
                         {'command': 'smpps_cred authorization bind no'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_SmppsCredential('user_892', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setAuthorization('bind', True)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'smpps_cred authorization bind 1'}]
        yield self.update_user(r'jcli : ', 'user_892', extraCommands)
        yield self._test_user_with_SmppsCredential('user_892', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_quota(self):
        _cred = SmppsCredential()
        _cred.setQuota('max_bindings', 10)

        # Assert User adding
        extraCommands = [{'command': 'uid user_909'},
                         {'command': 'smpps_cred quota max_bindings 10'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_SmppsCredential('user_909', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setQuota('max_bindings', 20)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'smpps_cred quota max_bindings 20'}]
        yield self.update_user(r'jcli : ', 'user_909', extraCommands)
        yield self._test_user_with_SmppsCredential('user_909', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_increase_decrease_quota_int(self):
        # Add with initial quota
        extraCommands = [{'command': 'uid user_923'},
                         {'command': 'smpps_cred quota max_bindings 100'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        _cred = SmppsCredential()
        _cred.setQuota('max_bindings', 20)

        # Assert User increasing/decreasing quota
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'smpps_cred quota max_bindings -90'}]
        yield self.update_user(r'jcli : ', 'user_923', extraCommands)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'smpps_cred quota max_bindings +10'}]
        yield self.update_user(r'jcli : ', 'user_923', extraCommands)
        yield self._test_user_with_SmppsCredential('user_923', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_increase_decrease_quota_invalid_type(self):
        # Add with initial quota
        extraCommands = [{'command': 'uid user_941'},
                         {'command': 'smpps_cred quota max_bindings 100'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        # Quota will remain the same since the following updates are using incorrect type
        _cred = SmppsCredential()
        _cred.setQuota('max_bindings', 100)

        # Assert User increasing/decreasing quota
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'smpps_cred quota max_bindings -90.2'}]
        yield self.update_user(r'jcli : ', 'user_941', extraCommands)
        extraCommands = [{'command': 'password anypassword'},
                         {'command': 'smpps_cred quota max_bindings +10.2'}]
        yield self.update_user(r'jcli : ', 'user_941', extraCommands)
        yield self._test_user_with_SmppsCredential('user_941', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_all(self):
        _cred = SmppsCredential()
        _cred.setAuthorization('bind', False)
        _cred.setQuota('max_bindings', 11)

        # Assert User adding
        extraCommands = [{'command': 'uid user_964'},
                         {'command': 'smpps_cred authorization bind no'},
                         {'command': 'smpps_cred quota max_bindings 11'}]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')
        yield self._test_user_with_SmppsCredential('user_964', 'AnyGroup', 'AnyUsername', _cred)

        # Assert User updating
        _cred.setAuthorization('bind', True)
        _cred.setQuota('max_bindings', 66)
        extraCommands = [{'command': 'smpps_cred authorization bind y'},
                         {'command': 'smpps_cred quota max_bindings 66'}]
        yield self.update_user(r'jcli : ', 'user_964', extraCommands)
        yield self._test_user_with_SmppsCredential('user_964', 'AnyGroup', 'AnyUsername', _cred)

    @defer.inlineCallbacks
    def test_invalid_syntax(self):
        # Assert User adding
        extraCommands = [{'command': 'uid user_980'},
                         {'command': 'smpps_red authorization bind no',
                          'expect': 'Unknown User key: smpps_red'},
                         {'command': 'smpps_cred quta max_bindings 22',
                          'expect': 'Error: invalid section name: quta, possible values: Authorization, Quota'},
                         {'command': 'smpps_cred DeefaultValue Anything AnyValue',
                          'expect': 'Error: invalid section name: deefaultvalue, possible values: Authorization, Quota'},
                         {'command': 'smpps_cred quota max_bindings incorrectvalue',
                          'expect': "Error: invalid literal for int\(\) with base 10: 'incorrectvalue'"},
                         {'command': 'smpps_cred authorization bind incorrectvalue',
                          'expect': "Error: bind is not a boolean value: incorrectvalue"},
                         ]
        yield self.add_user(r'jcli : ', extraCommands, GID='AnyGroup', Username='AnyUsername')

        # Assert User updating
        extraCommands = [{'command': 'password any_password'},
                         {'command': 'smpps_red authorization bind no',
                          'expect': 'Unknown User key: smpps_red'},
                         {'command': 'smpps_cred quta max_bindings 22',
                          'expect': 'Error: invalid section name: quta, possible values: Authorization, Quota'},
                         {'command': 'smpps_cred DeefaultValue Anything AnyValue',
                          'expect': 'Error: invalid section name: deefaultvalue, possible values: Authorization, Quota'},
                         {'command': 'smpps_cred quota max_bindings incorrectvalue',
                          'expect': "Error: invalid literal for int\(\) with base 10: 'incorrectvalue'"},
                         {'command': 'smpps_cred authorization bind incorrectvalue',
                          'expect': "Error: bind is not a boolean value: incorrectvalue"},
                         ]
        yield self.update_user(r'jcli : ', 'user_980', extraCommands)
