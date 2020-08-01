import systemd.daemon
import redis
import asyncio
import websockets
import concurrent


def execute():
    print('Startup')

    r = redis.Redis(host='192.168.0.1', port=6379,
                    db=0, decode_responses=True)

    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

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
