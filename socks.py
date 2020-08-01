import systemd.daemon
import redis
import asyncio
import websockets
import concurrent
import threading


class Client:

    def __init__(self, r, ws, path):
        self.r = r
        self.p = self.r.pubsub(ignore_subscribe_messages=True)
        self.ws = ws
        self.q = asyncio.Queue()

    def populate_queue(self, loop):
        '''Runs in a thread and updates the queue with messages from Redis subscriptions'''
        # Sadly we have to subscribe to a queue for it to listen to anything to start off with
        self.p.subscribe('__socks.placeholder-subscription')
        for message in self.p.listen():
            print('Recieved message')
            asyncio.run_coroutine_threadsafe(self.q.put(message), loop)
            print('dispatched')
        print('Exited')

    async def consumer(self, message):
        '''Handle messages from the ws client'''
        message = message.split(' ')
        cmd = message[0]
        arg = message[1]

        if cmd == 'subscribe':
            self.p.subscribe(arg)
        elif cmd == 'unsubscribe':
            self.p.unsubscribe(arg)
        elif cmd == 'psubscribe':
            self.p.psubscribe(arg)
        elif cmd == 'punsubscribe':
            self.p.punsubscribe(arg)
        elif cmd == 'publish':
            self.r.publish(arg, message[2])

    async def producer(self):
        '''Create messages for the ws client'''
        msg = await self.q.get()
        return msg['channel'] + ' ' + msg['data']

    async def consumer_handler(self):
        '''Receives messages from the ws client'''
        async for message in self.ws:
            await self.consumer(message)

    async def producer_handler(self):
        '''Sends messages to the ws client'''
        while True:
            message = await self.producer()
            await self.ws.send(message)

    async def run(self, loop):
        '''Run the client'''

        # Start thread to populate queue first
        self.t = threading.Thread(target=self.populate_queue, args=(loop,))
        self.t.start()

        consumer_task = asyncio.ensure_future(self.consumer_handler())
        producer_task = asyncio.ensure_future(self.producer_handler())
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        self.p.close()


def execute():
    print('Startup')

    r = redis.Redis(host='192.168.0.1', port=6379,
                    db=0, decode_responses=True)

    loop = asyncio.get_event_loop()

    async def connection(ws, path):
        '''Handles a new websocket connection'''
        client = Client(r, ws, path)
        await client.run(loop)

    start_server = websockets.serve(connection, '192.168.0.1', 7963)
    loop.run_until_complete(start_server)

    r.publish('services', 'socks.on')
    systemd.daemon.notify('READY=1')
    print('Startup complete')

    try:
        loop.run_forever()
    finally:
        r.publish('services', 'socks.off')
        print('Goodbye')


if __name__ == '__main__':
    execute()
