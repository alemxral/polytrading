import asyncio
import websockets
import logging

class WebSocketClient:
    def __init__(self, url):
        self.url = url
        self.connection = None

    async def connect(self):
        self.connection = await websockets.connect(self.url)
        logging.info(f"Connected to {self.url}")

    async def send(self, message):
        await self.connection.send(message)

    async def receive(self):
        return await self.connection.recv()

    async def close(self):
        await self.connection.close()
