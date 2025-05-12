from app.utils.queues import COMMENT_ANALYSIS_QUEUE, USER_BLOCK_QUEUE
import aio_pika
from aio_pika.abc import AbstractRobustConnection
from aio_pika.pool import Pool
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

RABBITMQ_URL = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"

async def get_connection() -> AbstractRobustConnection:
    try:
        connection = await aio_pika.connect_robust(
            RABBITMQ_URL,
            timeout=10,
            client_properties={
                "connection_name": "shieldcomment-api"
            }
        )
        logger.info(f"Connected to RabbitMQ at {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
        raise

connection_pool = Pool(get_connection, max_size=2)

async def get_channel() -> aio_pika.abc.AbstractChannel:
    async with connection_pool.acquire() as connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        return channel

channel_pool = Pool(get_channel, max_size=10)

async def publish_message(queue_name: str, message: str):
    try:
        if queue_name not in [COMMENT_ANALYSIS_QUEUE, USER_BLOCK_QUEUE]:
            raise ValueError(f"Invalid queue name: {queue_name}")
            
        async with channel_pool.acquire() as channel:
            await channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    'x-message-ttl': 86400000,
                    'x-max-length': 10000,
                    'x-dead-letter-exchange': 'dlx'  # Exchange para mensajes fallidos
                }
            )
            await channel.declare_exchange('dlx', type='direct')
            
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=message.encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=queue_name,
            )
            logger.info(f"Message published to {queue_name}")
    except Exception as e:
        logger.error(f"Failed to publish message to {queue_name}: {str(e)}")
        raise