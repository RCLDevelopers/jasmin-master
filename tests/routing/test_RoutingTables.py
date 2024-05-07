# pylint: disable=W0401,W0611

from twisted.trial.unittest import TestCase
from jasmin.routing.RoutingTables import *
from jasmin.routing.Routes import *
from jasmin.routing.Filters import *
from smpp.pdu.operations import SubmitSM, DeliverSM
from jasmin.routing.Routables import RoutableSubmitSm, RoutableDeliverSm


class RoutingTableTests:
    def test_standard(self):
        routing_t = self._routingTable()
        routing_t.add(self.route2, 2)
        routing_t.add(self.route1, 1)
        routing_t.add(self.route4, 0)

        c = routing_t.getRouteFor(self.routable_matching_route1)
        self.assertEqual(c.getConnector(), self.connector1)
        c = routing_t.getRouteFor(self.routable_matching_route2)
        self.assertEqual(c.getConnector(), self.connector2)
        c = routing_t.getRouteFor(self.routable_notmatching_any)
        self.assertEqual(c.getConnector(), self.connector4)

    def test_routing_table_order(self):
        routing_t = self._routingTable()
        routing_t.add(self.route4, 0)
        routing_t.add(self.route2, 2)
        routing_t.add(self.route1, 1)
        routing_t.add(self.route3, 3)

        self.assertEqual(list(routing_t.getAll()[0])[0], 3)
        self.assertEqual(list(routing_t.getAll()[1])[0], 2)
        self.assertEqual(list(routing_t.getAll()[2])[0], 1)
        self.assertEqual(list(routing_t.getAll()[3])[0], 0)

    def test_routing_table_replace_route(self):
        routing_t = self._routingTable()
        routing_t.add(self.route4, 0)
        routing_t.add(self.route2, 2)
        routing_t.add(self.route3, 2)

        self.assertEqual(list(routing_t.getAll()[0].values())[0], self.route3)

    def test_remove_route(self):
        routing_t = self._routingTable()
        routing_t.add(self.route2, 2)
        routing_t.add(self.route1, 1)
        routing_t.add(self.route4, 0)
        self.assertEqual(len(routing_t.getAll()), 3)

        # Remove non existent route
        r = routing_t.remove(3)
        self.assertFalse(r)

        # List after removing one route
        routing_t.remove(1)
        self.assertEqual(len(routing_t.getAll()), 2)

    def test_default_route(self):
        routing_t = self._routingTable()
        self.assertRaises(InvalidRoutingTableParameterError, routing_t.add, self.route3, 0)

    def test_flush(self):
        routing_t = self._routingTable()
        routing_t.add(self.route4, 0)
        routing_t.add(self.route3, 2)

        allRoutes = routing_t.getAll()
        self.assertEqual(len(allRoutes), 2)

        routing_t.flush()
        allRoutes = routing_t.getAll()
        self.assertEqual(len(allRoutes), 0)

        routing_t.add(self.route4, 0)
        allRoutes = routing_t.getAll()
        self.assertEqual(len(allRoutes), 1)


class MTRoutingTableTestCase(RoutingTableTests, TestCase):
    _routingTable = MTRoutingTable

    def setUp(self):
        self.connector1 = SmppClientConnector('abc')
        self.connector2 = SmppClientConnector('def')
        self.connector3 = SmppClientConnector('ghi')
        self.connector4 = SmppClientConnector('jkl')
        self.group100 = Group(100)
        self.user1 = User(1, self.group100, 'username', 'password')
        self.user2 = User(2, self.group100, 'username', 'password')

        self.mt_filter1 = [UserFilter(self.user1)]
        self.mt_filter2 = [DestinationAddrFilter('^10\d+')]
        self.transparent_filter = [TransparentFilter()]
        self.route1 = StaticMTRoute(self.mt_filter1, self.connector1, 0.0)
        self.route2 = StaticMTRoute(self.mt_filter2, self.connector2, 0.0)
        self.route3 = StaticMTRoute(self.transparent_filter, self.connector3, 0.0)
        self.route4 = DefaultRoute(self.connector4)

        self.PDU_dst_1 = SubmitSM(
            source_addr=b'x',
            destination_addr=b'200',
            short_message=b'hello world',
        )
        self.PDU_dst_2 = SubmitSM(
            source_addr=b'x',
            destination_addr=b'100',
            short_message=b'hello world',
        )

        self.routable_matching_route1 = RoutableSubmitSm(self.PDU_dst_1, self.user1)
        self.routable_matching_route2 = RoutableSubmitSm(self.PDU_dst_2, self.user2)
        self.routable_notmatching_any = RoutableSubmitSm(self.PDU_dst_1, self.user2)


class MORoutingTableTestCase(RoutingTableTests, TestCase):
    _routingTable = MORoutingTable

    def setUp(self):
        self.connector1 = HttpConnector('abc', 'http://127.0.0.1')
        self.connector2 = HttpConnector('def', 'http://127.0.0.1')
        self.connector3 = HttpConnector('ghi', 'http://127.0.0.1')
        self.connector4 = SmppServerSystemIdConnector('jkl')

        self.mt_filter1 = [SourceAddrFilter('^10\d+')]
        self.mt_filter2 = [DestinationAddrFilter('^90\d+')]
        self.transparent_filter = [TransparentFilter()]
        self.route1 = StaticMORoute(self.mt_filter1, self.connector1)
        self.route2 = StaticMORoute(self.mt_filter2, self.connector2)
        self.route3 = StaticMORoute(self.transparent_filter, self.connector3)
        self.route4 = DefaultRoute(self.connector4)

        self.PDU_dst_1 = DeliverSM(
            source_addr=b'100',
            destination_addr=b'200',
            short_message=b'hello world',
        )
        self.PDU_dst_2 = DeliverSM(
            source_addr=b'x',
            destination_addr=b'900',
            short_message=b'hello world',
        )
        self.PDU_dst_3 = DeliverSM(
            source_addr=b'x',
            destination_addr=b'y',
            short_message=b'hello world',
        )

        self.routable_matching_route1 = RoutableDeliverSm(self.PDU_dst_1, self.connector1)
        self.routable_matching_route2 = RoutableDeliverSm(self.PDU_dst_2, self.connector1)
        self.routable_notmatching_any = RoutableDeliverSm(self.PDU_dst_3, self.connector1)
