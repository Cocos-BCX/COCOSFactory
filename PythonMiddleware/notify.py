import logging
from events import Events
from PythonMiddlewareapi.websocket import GrapheneWebsocket
from PythonMiddleware.instance import shared_graphene_instance
from PythonMiddleware.market import Market
from PythonMiddleware.price import Order, FilledOrder, UpdateCallOrder
from PythonMiddleware.account import Account, AccountUpdate
from threading import Thread
log = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)


class Notify(Events):
    """ Notifications on Blockchain events.

        :param list accounts: Account names/ids to be notified about when changing
        :param list markets: Instances of :class:`graphene.market.Market` that identify markets to be monitored
        :param list objects: Object ids to be notified about when changed
        :param fnt on_tx: Callback that will be called for each transaction received
        :param fnt on_block: Callback that will be called for each block received
        :param fnt on_account: Callback that will be called for changes of the listed accounts
        :param fnt on_market: Callback that will be called for changes of the listed markets
        :param graphene.graphene.graphene graphene_instance: graphene instance

        **Example**

        .. code-block:: python

            from pprint import pprint
            from graphene.notify import Notify
            from graphene.market import Market

            notify = Notify(
                markets=["TEST:GOLD"],
                accounts=["xeroc"],
                on_market=print,
                on_account=print,
                on_block=print,
                on_tx=print
            )
            notify.listen()


    """

    __events__ = [
        'on_tx',
        'on_object',
        'on_block',
        'on_account',
        'on_market',
    ]

    def __init__(
        self,
        accounts=[],
        markets=[],
        objects=[],
        on_tx=None,
        on_object=None,
        on_block=None,
        on_account=None,
        on_market=None,
        graphene_instance=None,
    ):
        # Events
        super(Notify, self).__init__()
        self.events = Events()

        # graphene instance
        self.graphene = graphene_instance or shared_graphene_instance()

        # Markets
        market_ids = []
        for market_name in markets:
            market = Market(
                market_name,
                graphene_instance=self.graphene
            )
            market_ids.append([
                market["base"]["id"],
                market["quote"]["id"],
            ])

        # Callbacks
        if on_tx:
            self.on_tx += on_tx
        if on_object:
            self.on_object += on_object
        if on_block:
            self.on_block += on_block
        if on_account:
            self.on_account += on_account
        if on_market:
            self.on_market += on_market

        # Open the websocket
        self.websocket = GrapheneWebsocket(
            urls=self.graphene.rpc.urls,
            user=self.graphene.rpc.user,
            password=self.graphene.rpc.password,
            accounts=accounts,
            markets=market_ids,
            objects=objects,
            on_tx=on_tx,
            on_object=on_object,
            on_block=on_block,
            on_account=self.process_account,
            on_market=self.process_market,
        )

    def process_market(self, data):
        """ This method is used for post processing of market
            notifications. It will return instances of either

            * :class:`graphene.price.Order` or
            * :class:`graphene.price.FilledOrder` or
            * :class:`graphene.price.UpdateCallOrder`

            Also possible are limit order updates (margin calls)

        """
        for d in data:
            if not d:
                continue
            if isinstance(d, str):
                # Single order has been placed
                log.debug("Calling on_market with Order()")
                self.on_market(Order(d))
                continue
            elif isinstance(d, dict):
                d = [d]

            # Orders have been matched
            for p in d:
                if not isinstance(p, list):
                    p = [p]
                for i in p:
                    if isinstance(i, dict):
                        if "pays" in i and "receives" in i:
                            self.on_market(FilledOrder(i))
                        elif "for_sale" in i and "sell_price" in i:
                            self.on_market(Order(i))
                        elif "collateral" in i and "call_price" in i:
                            self.on_market(UpdateCallOrder(i))
                        else:
                            if i:
                                log.error(
                                    "Unknown market update type: %s" % i
                                )

    def process_account(self, message):
        """ This is used for processing of account Updates. It will
            return instances of :class:graphene.account.AccountUpdate`
        """
        self.on_account(AccountUpdate(message))

    def listen(self):
        """ This call initiates the listening/notification process. It
            behaves similar to ``run_forever()``.
        """
        Thread(
            target=self.websocket.run_forever,
            args=()
            ).start()
