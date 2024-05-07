import copy
import string

from unittest.mock import Mock
from twisted.internet import defer, reactor
from twisted.web import server

from jasmin.protocols.smpp.configs import SMPPClientConfig
from tests.protocols.smpp.smsc_simulator import *
from jasmin.routing.Filters import TransparentFilter
from jasmin.routing.Routes import DefaultRoute, FailoverMORoute
from jasmin.routing.configs import deliverSmThrowerConfig
from jasmin.routing.jasminApi import *
from jasmin.routing.proxies import RouterPBProxy
from tests.routing.http_server import AckServer
from tests.routing.test_router import (SMPPClientManagerPBTestCase, LastClientFactory,
                                             SubmitSmTestCaseTools, id_generator)
from tests.routing.test_router_smpps import SMPPClientTestCases
from jasmin.routing.throwers import deliverSmThrower
from smpp.pdu.pdu_types import (EsmClass, EsmClassMode, EsmClassType, EsmClassGsmFeatures,
                                              MoreMessagesToSend, MessageState, AddrTon, AddrNpi, CommandId)
from smpp.pdu.operations import DeliverSM


@defer.inlineCallbacks
def waitFor(seconds):
    # Wait seconds
    waitDeferred = defer.Deferred()
    reactor.callLater(seconds, waitDeferred.callback, None)
    yield waitDeferred


class DeliverSmSMSCTestCase(SMPPClientManagerPBTestCase):
    protocol = DeliverSmSMSC

    @defer.inlineCallbacks
    def setUp(self):
        yield SMPPClientManagerPBTestCase.setUp(self)

        self.smsc_f = LastClientFactory()
        self.smsc_f.protocol = self.protocol
        self.SMSCPort = reactor.listenTCP(0, self.smsc_f)

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.SMSCPort.stopListening()
        yield SMPPClientManagerPBTestCase.tearDown(self)


class DeliverSmHttpThrowingTestCases(RouterPBProxy, DeliverSmSMSCTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield DeliverSmSMSCTestCase.setUp(self)

        # Start http servers
        self.AckServerResource = AckServer()
        self.AckServer = reactor.listenTCP(0, server.Site(self.AckServerResource))

        # Initiating config objects without any filename
        # will lead to setting defaults and that's what we
        # need to run the tests
        deliverSmThrowerConfigInstance = deliverSmThrowerConfig()
        # Lower the timeout config to pass the timeout tests quickly
        deliverSmThrowerConfigInstance.timeout = 2
        deliverSmThrowerConfigInstance.retry_delay = 1
        deliverSmThrowerConfigInstance.max_retries = 2

        # Launch the deliverSmThrower
        self.deliverSmThrower = deliverSmThrower(deliverSmThrowerConfigInstance)

        # Add the broker to the deliverSmThrower
        yield self.deliverSmThrower.addAmqpBroker(self.amqpBroker)

        # Initiate last seqNum
        self.last_seqNum = 1

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.AckServer.stopListening()
        yield self.deliverSmThrower.stopService()
        yield DeliverSmSMSCTestCase.tearDown(self)

    @defer.inlineCallbacks
    def prepareRoutingsAndStartConnector(self, connector, route=None, route_order=1):
        self.AckServerResource.render_POST = Mock(wraps=self.AckServerResource.render_POST)

        # Prepare for routing
        connector.port = self.SMSCPort.getHost().port

        # Set the route
        if route is None:
            c2_destination = HttpConnector(id_generator(), 'http://127.0.0.1:%s/send' % self.AckServer.getHost().port, 'POST')
            yield self.moroute_add(DefaultRoute(c2_destination), 0)
        else:
            yield self.moroute_add(route, route_order)

        # Now we'll create the connector 1 from which we'll receive DeliverSm PDUs before
        # throwing to http
        yield self.SMPPClientManagerPBProxy.connect('127.0.0.1', self.CManagerPort)
        c1Config = SMPPClientConfig(id=connector.cid, port=connector.port)
        yield self.SMPPClientManagerPBProxy.add(c1Config)

        # Start the connector
        yield self.SMPPClientManagerPBProxy.start(connector.cid)
        # Wait for 'BOUND_TRX' state
        while True:
            ssRet = yield self.SMPPClientManagerPBProxy.session_state(connector.cid)
            if ssRet == 'BOUND_TRX':
                break
            else:
                yield waitFor(0.2)

    @defer.inlineCallbacks
    def stopConnector(self, connector):
        # Disconnect the connector
        yield self.SMPPClientManagerPBProxy.stop(connector.cid)
        # Wait for 'BOUND_TRX' state
        while True:
            ssRet = yield self.SMPPClientManagerPBProxy.session_state(connector.cid)
            if ssRet == 'NONE':
                break
            else:
                yield waitFor(0.2)

    @defer.inlineCallbacks
    def triggerDeliverSmFromSMSC(self, pdus):
        for pdu in pdus:
            pdu.seqNum = self.last_seqNum
            yield self.SMSCPort.factory.lastClient.trigger_deliver_sm(pdu)
            self.last_seqNum += 1

            # Wait 0.5 seconds
            yield waitFor(0.5)

    @defer.inlineCallbacks
    def test_delivery_HttpConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        # Connect to SMSC
        source_connector = Connector(id_generator())
        yield self.prepareRoutingsAndStartConnector(source_connector)

        # Send a deliver_sm from the SMSC
        pdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='any content',
        )
        yield self.triggerDeliverSmFromSMSC([pdu])

        # Run tests
        # Test callback in router
        self.assertEqual(self.pbRoot_f.deliver_sm_callback.call_count, 1)
        # Destination connector must receive the message one time (no retries)
        self.assertEqual(self.AckServerResource.render_POST.call_count, 1)
        # Assert received args
        receivedHttpReq = self.AckServerResource.last_request.args
        self.assertEqual(len(receivedHttpReq), 8)
        self.assertEqual(receivedHttpReq[b'from'], [pdu.params['source_addr']])
        self.assertEqual(receivedHttpReq[b'to'], [pdu.params['destination_addr']])
        self.assertEqual(receivedHttpReq[b'content'], [pdu.params['short_message']])
        self.assertEqual(receivedHttpReq[b'binary'], [binascii.hexlify(pdu.params['short_message'])])
        self.assertEqual(receivedHttpReq[b'origin-connector'], [source_connector.cid.encode()])

        # Disconnector from SMSC
        yield self.stopConnector(source_connector)

    @defer.inlineCallbacks
    def test_delivery_HttpConnector_message_payload_when_short_message_empty(self):
        """Related to #470
        Consider 'message_payload' when 'short_message' is empty"""
        yield self.connect('127.0.0.1', self.pbPort)
        # Connect to SMSC
        source_connector = Connector(id_generator())
        yield self.prepareRoutingsAndStartConnector(source_connector)

        # Send a deliver_sm from the SMSC
        assert_content = b'Some content'
        pdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='',
            message_payload=assert_content
        )
        yield self.triggerDeliverSmFromSMSC([pdu])

        # Run tests
        # Test callback in router
        self.assertEqual(self.pbRoot_f.deliver_sm_callback.call_count, 1)
        # Destination connector must receive the message one time (no retries)
        self.assertEqual(self.AckServerResource.render_POST.call_count, 1)
        # Assert received args
        receivedHttpReq = self.AckServerResource.last_request.args
        self.assertEqual(len(receivedHttpReq), 8)
        self.assertEqual(receivedHttpReq[b'content'], [assert_content])
        self.assertEqual(receivedHttpReq[b'binary'], [binascii.hexlify(assert_content)])

        # Disconnector from SMSC
        yield self.stopConnector(source_connector)

    @defer.inlineCallbacks
    def test_delivery_failover_route(self):
        """#467: Will ensure a failover route will deliver the message"""

        yield self.connect('127.0.0.1', self.pbPort)
        # Connect to SMSC
        source_connector = Connector(id_generator())
        wrong_port = self.AckServer.getHost().port + 1000
        route = FailoverMORoute([TransparentFilter()], [
            HttpConnector(id_generator(), 'http://127.0.0.1:%s/send' % wrong_port, 'POST'),
            HttpConnector(id_generator(), 'http://127.0.0.1:%s/send' % self.AckServer.getHost().port, 'POST')])
        yield self.prepareRoutingsAndStartConnector(source_connector, route)

        # Send a deliver_sm from the SMSC
        pdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='any content',
        )
        yield self.triggerDeliverSmFromSMSC([pdu])

        # Run tests
        # Test callback in router
        self.assertEqual(self.pbRoot_f.deliver_sm_callback.call_count, 1)
        # Destination connector must receive the message one time (no retries)
        self.assertEqual(self.AckServerResource.render_POST.call_count, 1)

        # Disconnector from SMSC
        yield self.stopConnector(source_connector)

    @defer.inlineCallbacks
    def test_long_content_delivery_SAR_HttpConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        # Connect to SMSC
        source_connector = Connector(id_generator())
        yield self.prepareRoutingsAndStartConnector(source_connector)

        # Send a deliver_sm from the SMSC
        basePdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='',
            sar_total_segments=3,
            sar_msg_ref_num=int(id_generator(size=2, chars=string.digits)),
        )
        pdu_part1 = copy.deepcopy(basePdu)
        pdu_part2 = copy.deepcopy(basePdu)
        pdu_part3 = copy.deepcopy(basePdu)
        pdu_part1.params[
            'short_message'] = b'__1st_part_with_153_char________________________________________________________________________________________________________________________________.'
        pdu_part1.params['sar_segment_seqnum'] = 1
        pdu_part2.params[
            'short_message'] = b'__2nd_part_with_153_char________________________________________________________________________________________________________________________________.'
        pdu_part2.params['sar_segment_seqnum'] = 2
        pdu_part3.params['short_message'] = b'__3rd_part_end.'
        pdu_part3.params['sar_segment_seqnum'] = 3
        yield self.triggerDeliverSmFromSMSC([pdu_part1, pdu_part2, pdu_part3])

        # Run tests
        # Destination connector must receive the message one time (no retries)
        self.assertEqual(self.AckServerResource.render_POST.call_count, 1)
        # Assert received args
        receivedHttpReq = self.AckServerResource.last_request.args
        self.assertEqual(len(receivedHttpReq), 8)
        self.assertEqual(receivedHttpReq[b'from'], [basePdu.params['source_addr']])
        self.assertEqual(receivedHttpReq[b'to'], [basePdu.params['destination_addr']])
        self.assertEqual(receivedHttpReq[b'content'], [
            pdu_part1.params['short_message'] + pdu_part2.params['short_message'] + pdu_part3.params['short_message']])
        self.assertEqual(receivedHttpReq[b'binary'], [binascii.hexlify(
            pdu_part1.params['short_message'] + pdu_part2.params['short_message'] + pdu_part3.params['short_message'])])
        self.assertEqual(receivedHttpReq[b'origin-connector'], [source_connector.cid.encode()])

        # Disconnector from SMSC
        yield self.stopConnector(source_connector)

    @defer.inlineCallbacks
    def test_long_content_delivery_UDH_HttpConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        # Connect to SMSC
        source_connector = Connector(id_generator())
        yield self.prepareRoutingsAndStartConnector(source_connector)

        # Build a UDH
        baseUdh = []
        baseUdh.append(struct.pack('!B', 5))  # Length of User Data Header
        baseUdh.append(struct.pack('!B',
                                   0))  # Information Element Identifier, equal to 00 (Concatenated short messages, 8-bit reference number)
        baseUdh.append(struct.pack('!B', 3))  # Length of the header, excluding the first two fields; equal to 03
        baseUdh.append(struct.pack('!B', int(id_generator(size=2, chars=string.digits))))  # msg_ref_num
        baseUdh.append(struct.pack('!B', 3))  # total_segments

        # Send a deliver_sm from the SMSC
        basePdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='',
            esm_class=EsmClass(EsmClassMode.DEFAULT, EsmClassType.DEFAULT, [EsmClassGsmFeatures.UDHI_INDICATOR_SET]),
        )
        pdu_part1 = copy.deepcopy(basePdu)
        udh_part1 = copy.deepcopy(baseUdh)
        pdu_part2 = copy.deepcopy(basePdu)
        udh_part2 = copy.deepcopy(baseUdh)
        pdu_part3 = copy.deepcopy(basePdu)
        udh_part3 = copy.deepcopy(baseUdh)
        udh_part1.append(struct.pack('!B', 1))  # segment_seqnum
        pdu_part1.params['more_messages_to_send'] = MoreMessagesToSend.MORE_MESSAGES
        pdu_part1.params['short_message'] = b''.join(
            udh_part1) + b'__1st_part_with_153_char________________________________________________________________________________________________________________________________.'
        udh_part2.append(struct.pack('!B', 2))  # segment_seqnum
        pdu_part2.params['more_messages_to_send'] = MoreMessagesToSend.MORE_MESSAGES
        pdu_part2.params['short_message'] = b''.join(
            udh_part2) + b'__2nd_part_with_153_char________________________________________________________________________________________________________________________________.'
        udh_part3.append(struct.pack('!B', 3))  # segment_seqnum
        pdu_part3.params['more_messages_to_send'] = MoreMessagesToSend.NO_MORE_MESSAGES
        pdu_part3.params['short_message'] = b''.join(udh_part3) + b'__3rd_part_end.'
        yield self.triggerDeliverSmFromSMSC([pdu_part1, pdu_part2, pdu_part3])

        # Run tests
        # Destination connector must receive the message one time (no retries)
        self.assertEqual(self.AckServerResource.render_POST.call_count, 1)
        # Assert received args
        receivedHttpReq = self.AckServerResource.last_request.args
        self.assertEqual(len(receivedHttpReq), 8)
        self.assertEqual(receivedHttpReq[b'from'], [basePdu.params['source_addr']])
        self.assertEqual(receivedHttpReq[b'to'], [basePdu.params['destination_addr']])
        self.assertEqual(receivedHttpReq[b'content'], [
            pdu_part1.params['short_message'][6:] + pdu_part2.params['short_message'][6:] + pdu_part3.params[
                                                                                                'short_message'][6:]])
        self.assertEqual(receivedHttpReq[b'binary'], [binascii.hexlify(
            pdu_part1.params['short_message'][6:] + pdu_part2.params['short_message'][6:] + pdu_part3.params[
                                                                                                'short_message'][6:])])
        self.assertEqual(receivedHttpReq[b'origin-connector'], [source_connector.cid.encode()])

        # Disconnector from SMSC
        yield self.stopConnector(source_connector)

    @defer.inlineCallbacks
    def test_unordered_long_content_delivery_HttpConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        # Connect to SMSC
        source_connector = Connector(id_generator())
        yield self.prepareRoutingsAndStartConnector(source_connector)

        # Send a deliver_sm from the SMSC
        basePdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='',
            sar_total_segments=3,
            sar_msg_ref_num=int(id_generator(size=2, chars=string.digits)),
        )
        pdu_part1 = copy.deepcopy(basePdu)
        pdu_part2 = copy.deepcopy(basePdu)
        pdu_part3 = copy.deepcopy(basePdu)
        pdu_part1.params[
            'short_message'] = b'__1st_part_with_153_char________________________________________________________________________________________________________________________________.'
        pdu_part1.params['sar_segment_seqnum'] = 1
        pdu_part2.params[
            'short_message'] = b'__2nd_part_with_153_char________________________________________________________________________________________________________________________________.'
        pdu_part2.params['sar_segment_seqnum'] = 2
        pdu_part3.params['short_message'] = b'__3rd_part_end.'
        pdu_part3.params['sar_segment_seqnum'] = 3
        yield self.triggerDeliverSmFromSMSC([pdu_part2, pdu_part1, pdu_part3])

        # Run tests
        # Destination connector must receive the message one time (no retries)
        self.assertEqual(self.AckServerResource.render_POST.call_count, 1)
        # Assert received args
        receivedHttpReq = self.AckServerResource.last_request.args
        self.assertEqual(len(receivedHttpReq), 8)
        self.assertEqual(receivedHttpReq[b'from'], [basePdu.params['source_addr']])
        self.assertEqual(receivedHttpReq[b'to'], [basePdu.params['destination_addr']])
        self.assertEqual(receivedHttpReq[b'content'], [
            pdu_part1.params['short_message'] + pdu_part2.params['short_message'] + pdu_part3.params['short_message']])
        self.assertEqual(receivedHttpReq[b'binary'], [binascii.hexlify(
            pdu_part1.params['short_message'] + pdu_part2.params['short_message'] + pdu_part3.params['short_message'])])
        self.assertEqual(receivedHttpReq[b'origin-connector'], [source_connector.cid.encode()])

        # Disconnector from SMSC
        yield self.stopConnector(source_connector)

    @defer.inlineCallbacks
    def test_last_first_long_content_delivery_HttpConnector(self):
        "Ensure that receiving the last data_sm part at first is handled"

    test_last_first_long_content_delivery_HttpConnector.skip = "TODO: handle this specific case, it was omitted for more performance"


class DeliverSmSmppThrowingTestCases(RouterPBProxy, SMPPClientTestCases, SubmitSmTestCaseTools):
    @defer.inlineCallbacks
    def setUp(self):
        yield SMPPClientTestCases.setUp(self)

        # Initiating config objects without any filename
        # will lead to setting defaults and that's what we
        # need to run the tests
        deliverSmThrowerConfigInstance = deliverSmThrowerConfig()

        # Launch the deliverSmThrower
        self.deliverSmThrower = deliverSmThrower(deliverSmThrowerConfigInstance)

        # Add the broker to the deliverSmThrower
        yield self.deliverSmThrower.addAmqpBroker(self.amqpBroker)

        # Add SMPPs factory to DLRThrower
        self.deliverSmThrower.addSmpps(self.smpps_factory)

        # Initiate last seqNum
        self.last_seqNum = 1

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.deliverSmThrower.stopService()
        yield SMPPClientTestCases.tearDown(self)

    @defer.inlineCallbacks
    def prepareRoutingsAndStartConnector(self, route=None, route_order=1):
        yield SubmitSmTestCaseTools.prepareRoutingsAndStartConnector(self)

        # Set the route
        if route is None:
            # Add a MO Route to a SmppServerSystemIdConnector
            c2_destination = SmppServerSystemIdConnector(system_id=self.smppc_factory.config.username)
            yield self.moroute_add(DefaultRoute(c2_destination), 0)
        else:
            yield self.moroute_add(route, route_order)

    @defer.inlineCallbacks
    def triggerDeliverSmFromSMSC(self, pdus):
        for pdu in pdus:
            pdu.seqNum = self.last_seqNum
            yield self.SMSCPort.factory.lastClient.trigger_deliver_sm(pdu)
            self.last_seqNum += 1

            # Wait 0.5 seconds
            yield waitFor(0.5)

    @defer.inlineCallbacks
    def test_delivery_failover_route(self):
        """#467: Will ensure a failover route will deliver the message"""

        yield self.connect('127.0.0.1', self.pbPort)

        route = FailoverMORoute([TransparentFilter()], [
            SmppServerSystemIdConnector(system_id='wrong_username1'),
            SmppServerSystemIdConnector(system_id=self.smppc_factory.config.username)])
        yield self.prepareRoutingsAndStartConnector(route)

        # Bind
        yield self.smppc_factory.connectAndBind()

        # Install mocks
        self.smppc_factory.lastProto.PDUDataRequestReceived = Mock(
            wraps=self.smppc_factory.lastProto.PDUDataRequestReceived)

        # Send a deliver_sm from the SMSC
        yield self.triggerDeliverSmFromSMSC([self.DeliverSmPDU])

        # Run tests
        self.assertEqual(self.smppc_factory.lastProto.PDUDataRequestReceived.call_count, 1)
        # the received pdu must be our self.DeliverSmPDU
        received_pdu_1 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[0][0][0]
        self.assertEqual(received_pdu_1.id, CommandId.deliver_sm)

        # Unbind and disconnect
        yield self.smppc_factory.smpp.unbindAndDisconnect()
        yield self.stopSmppClientConnectors()

    @defer.inlineCallbacks
    def test_delivery_SmppClientConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        yield self.prepareRoutingsAndStartConnector()

        # Bind
        yield self.smppc_factory.connectAndBind()

        # Install mocks
        self.smppc_factory.lastProto.PDUDataRequestReceived = Mock(
            wraps=self.smppc_factory.lastProto.PDUDataRequestReceived)

        # Send a deliver_sm from the SMSC
        yield self.triggerDeliverSmFromSMSC([self.DeliverSmPDU])

        # Run tests
        self.assertEqual(self.smppc_factory.lastProto.PDUDataRequestReceived.call_count, 1)
        # the received pdu must be our self.DeliverSmPDU
        received_pdu_1 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[0][0][0]
        self.assertEqual(received_pdu_1.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_1.params['source_addr'], self.DeliverSmPDU.params['source_addr'])
        self.assertEqual(received_pdu_1.params['destination_addr'], self.DeliverSmPDU.params['destination_addr'])
        self.assertEqual(received_pdu_1.params['short_message'], self.DeliverSmPDU.params['short_message'])

        # Unbind and disconnect
        yield self.smppc_factory.smpp.unbindAndDisconnect()
        yield self.stopSmppClientConnectors()

    @defer.inlineCallbacks
    def test_delivery_multipart_SmppClientConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        yield self.prepareRoutingsAndStartConnector()

        # Bind
        yield self.smppc_factory.connectAndBind()

        # Install mocks
        self.smppc_factory.lastProto.PDUDataRequestReceived = Mock(
            wraps=self.smppc_factory.lastProto.PDUDataRequestReceived)

        # Send 10 deliver_sm from the SMSC
        for i in range(10):
            pdu = copy.copy(self.DeliverSmPDU)
            yield self.triggerDeliverSmFromSMSC([pdu])

        # Run tests
        self.assertEqual(self.smppc_factory.lastProto.PDUDataRequestReceived.call_count, 10)
        # the received pdus are ordered the same way they were sent
        for i in range(10):
            received_pdu = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[i][0][0]
            self.assertEqual(received_pdu.id, CommandId.deliver_sm)
            self.assertEqual(received_pdu.seqNum, i + 1)

        # Unbind and disconnect
        yield self.smppc_factory.smpp.unbindAndDisconnect()
        yield self.stopSmppClientConnectors()

    @defer.inlineCallbacks
    def test_long_content_delivery_SAR_SmppsConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        yield self.prepareRoutingsAndStartConnector()

        # Bind
        yield self.smppc_factory.connectAndBind()

        # Install mocks
        self.smppc_factory.lastProto.PDUDataRequestReceived = Mock(
            wraps=self.smppc_factory.lastProto.PDUDataRequestReceived)

        # Send a deliver_sm from the SMSC
        basePdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='',
            sar_total_segments=3,
            sar_msg_ref_num=int(id_generator(size=2, chars=string.digits)),
        )
        pdu_part1 = copy.deepcopy(basePdu)
        pdu_part2 = copy.deepcopy(basePdu)
        pdu_part3 = copy.deepcopy(basePdu)
        pdu_part1.params[
            'short_message'] = b'__1st_part_with_153_char________________________________________________________________________________________________________________________________.'
        pdu_part1.params['sar_segment_seqnum'] = 1
        pdu_part2.params[
            'short_message'] = b'__2nd_part_with_153_char________________________________________________________________________________________________________________________________.'
        pdu_part2.params['sar_segment_seqnum'] = 2
        pdu_part3.params['short_message'] = b'__3rd_part_end.'
        pdu_part3.params['sar_segment_seqnum'] = 3
        yield self.triggerDeliverSmFromSMSC([pdu_part1, pdu_part2, pdu_part3])

        # Run tests
        self.assertEqual(self.smppc_factory.lastProto.PDUDataRequestReceived.call_count, 3)
        # First received pdu
        received_pdu_1 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[0][0][0]
        self.assertEqual(received_pdu_1.seqNum, 1)
        self.assertEqual(received_pdu_1.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_1.params['source_addr'], basePdu.params['source_addr'])
        self.assertEqual(received_pdu_1.params['destination_addr'], basePdu.params['destination_addr'])
        self.assertEqual(received_pdu_1.params['short_message'], pdu_part1.params['short_message'])
        self.assertEqual(received_pdu_1.params['sar_segment_seqnum'], pdu_part1.params['sar_segment_seqnum'])
        # Second received pdu
        received_pdu_2 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[1][0][0]
        self.assertEqual(received_pdu_2.seqNum, 2)
        self.assertEqual(received_pdu_2.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_2.params['source_addr'], basePdu.params['source_addr'])
        self.assertEqual(received_pdu_2.params['destination_addr'], basePdu.params['destination_addr'])
        self.assertEqual(received_pdu_2.params['short_message'], pdu_part2.params['short_message'])
        self.assertEqual(received_pdu_2.params['sar_segment_seqnum'], pdu_part2.params['sar_segment_seqnum'])
        self.assertNotEqual(received_pdu_2.params['short_message'], received_pdu_1.params['short_message'])
        self.assertNotEqual(received_pdu_2.params['sar_segment_seqnum'], received_pdu_1.params['sar_segment_seqnum'])
        # Third received pdu
        received_pdu_3 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[2][0][0]
        self.assertEqual(received_pdu_3.seqNum, 3)
        self.assertEqual(received_pdu_3.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_3.params['source_addr'], basePdu.params['source_addr'])
        self.assertEqual(received_pdu_3.params['destination_addr'], basePdu.params['destination_addr'])
        self.assertEqual(received_pdu_3.params['short_message'], pdu_part3.params['short_message'])
        self.assertEqual(received_pdu_3.params['sar_segment_seqnum'], pdu_part3.params['sar_segment_seqnum'])
        self.assertNotEqual(received_pdu_3.params['short_message'], received_pdu_2.params['short_message'])
        self.assertNotEqual(received_pdu_3.params['sar_segment_seqnum'], received_pdu_2.params['sar_segment_seqnum'])

        # Unbind and disconnect
        yield self.smppc_factory.smpp.unbindAndDisconnect()
        yield self.stopSmppClientConnectors()

    @defer.inlineCallbacks
    def test_long_content_delivery_UDH_SmppsConnector(self):
        yield self.connect('127.0.0.1', self.pbPort)
        yield self.prepareRoutingsAndStartConnector()

        # Bind
        yield self.smppc_factory.connectAndBind()

        # Install mocks
        self.smppc_factory.lastProto.PDUDataRequestReceived = Mock(
            wraps=self.smppc_factory.lastProto.PDUDataRequestReceived)

        # Build a UDH
        baseUdh = []
        baseUdh.append(struct.pack('!B', 5))  # Length of User Data Header
        baseUdh.append(struct.pack('!B',
                                   0))  # Information Element Identifier, equal to 00 (Concatenated short messages, 8-bit reference number)
        baseUdh.append(struct.pack('!B', 3))  # Length of the header, excluding the first two fields; equal to 03
        baseUdh.append(struct.pack('!B', int(id_generator(size=2, chars=string.digits))))  # msg_ref_num
        baseUdh.append(struct.pack('!B', 3))  # total_segments

        # Send a deliver_sm from the SMSC
        basePdu = DeliverSM(
            source_addr='1234',
            destination_addr='4567',
            short_message='',
            esm_class=EsmClass(EsmClassMode.DEFAULT, EsmClassType.DEFAULT, [EsmClassGsmFeatures.UDHI_INDICATOR_SET]),
        )
        pdu_part1 = copy.deepcopy(basePdu)
        udh_part1 = copy.deepcopy(baseUdh)
        pdu_part2 = copy.deepcopy(basePdu)
        udh_part2 = copy.deepcopy(baseUdh)
        pdu_part3 = copy.deepcopy(basePdu)
        udh_part3 = copy.deepcopy(baseUdh)
        udh_part1.append(struct.pack('!B', 1))  # segment_seqnum
        pdu_part1.params['more_messages_to_send'] = MoreMessagesToSend.MORE_MESSAGES
        pdu_part1.params['short_message'] = b''.join(
            udh_part1) + b'__1st_part_with_153_char________________________________________________________________________________________________________________________________.'
        udh_part2.append(struct.pack('!B', 2))  # segment_seqnum
        pdu_part2.params['more_messages_to_send'] = MoreMessagesToSend.MORE_MESSAGES
        pdu_part2.params['short_message'] = b''.join(
            udh_part2) + b'__2nd_part_with_153_char________________________________________________________________________________________________________________________________.'
        udh_part3.append(struct.pack('!B', 3))  # segment_seqnum
        pdu_part3.params['more_messages_to_send'] = MoreMessagesToSend.NO_MORE_MESSAGES
        pdu_part3.params['short_message'] = b''.join(udh_part3) + b'__3rd_part_end.'
        yield self.triggerDeliverSmFromSMSC([pdu_part1, pdu_part2, pdu_part3])

        # Run tests
        self.assertEqual(self.smppc_factory.lastProto.PDUDataRequestReceived.call_count, 3)
        # First received pdu
        received_pdu_1 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[0][0][0]
        self.assertEqual(received_pdu_1.seqNum, 1)
        self.assertEqual(received_pdu_1.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_1.params['source_addr'], basePdu.params['source_addr'])
        self.assertEqual(received_pdu_1.params['destination_addr'], basePdu.params['destination_addr'])
        self.assertEqual(received_pdu_1.params['esm_class'], basePdu.params['esm_class'])
        self.assertEqual(received_pdu_1.params['short_message'][6:], pdu_part1.params['short_message'][6:])
        # Second received pdu
        received_pdu_2 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[1][0][0]
        self.assertEqual(received_pdu_2.seqNum, 2)
        self.assertEqual(received_pdu_2.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_2.params['source_addr'], basePdu.params['source_addr'])
        self.assertEqual(received_pdu_2.params['destination_addr'], basePdu.params['destination_addr'])
        self.assertEqual(received_pdu_2.params['esm_class'], basePdu.params['esm_class'])
        self.assertEqual(received_pdu_2.params['short_message'][6:], pdu_part2.params['short_message'][6:])
        # Third received pdu
        received_pdu_3 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[2][0][0]
        self.assertEqual(received_pdu_3.seqNum, 3)
        self.assertEqual(received_pdu_3.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_3.params['source_addr'], basePdu.params['source_addr'])
        self.assertEqual(received_pdu_3.params['destination_addr'], basePdu.params['destination_addr'])
        self.assertEqual(received_pdu_3.params['esm_class'], basePdu.params['esm_class'])
        self.assertEqual(received_pdu_3.params['short_message'][6:], pdu_part3.params['short_message'][6:])

        # Unbind and disconnect
        yield self.smppc_factory.smpp.unbindAndDisconnect()
        yield self.stopSmppClientConnectors()

    @defer.inlineCallbacks
    def test_delivery_SmppClientConnector_with_network_error_code(self):
        "Related to #117"
        yield self.connect('127.0.0.1', self.pbPort)
        yield self.prepareRoutingsAndStartConnector()

        # Bind
        yield self.smppc_factory.connectAndBind()

        # Install mocks
        self.smppc_factory.lastProto.PDUDataRequestReceived = Mock(
            wraps=self.smppc_factory.lastProto.PDUDataRequestReceived)

        # Send a deliver_sm from the SMSC
        DeliverSmPDU = copy.deepcopy(self.DeliverSmPDU)
        DeliverSmPDU.params['network_error_code'] = b'\x03\x00\x00'
        yield self.triggerDeliverSmFromSMSC([DeliverSmPDU])

        # Run tests
        self.assertEqual(self.smppc_factory.lastProto.PDUDataRequestReceived.call_count, 1)
        # the received pdu must be our DeliverSmPDU
        received_pdu_1 = self.smppc_factory.lastProto.PDUDataRequestReceived.call_args_list[0][0][0]
        self.assertEqual(received_pdu_1.id, CommandId.deliver_sm)
        self.assertEqual(received_pdu_1.params['network_error_code'], DeliverSmPDU.params['network_error_code'])

        # Unbind and disconnect
        yield self.smppc_factory.smpp.unbindAndDisconnect()
        yield self.stopSmppClientConnectors()
