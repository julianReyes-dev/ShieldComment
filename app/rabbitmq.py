import aio_pika
from aio_pika.abc import AbstractRobustConnection
from aio_pika.pool import Pool
from app.utils.config import settings

RABBITMQ_URL = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"

async def get_connection() -> AbstractRobustConnection:
    return await aio_pika.connect_robust(RABBITMQ_URL)

connection_pool = Pool(get_connection, max_size=2)

async def get_channel() -> aio_pika.abc.AbstractChannel:
    async with connection_pool.acquire() as connection:
        return await connection.channel()

channel_pool = Pool(get_channel, max_size=10)

async def publish_message(queue_name: str, message: str):
    async with channel_pool.acquire() as channel:
        await channel.declare_queue(queue_name, durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(body=message.encode()),
            routing_key=queue_name,
        )
