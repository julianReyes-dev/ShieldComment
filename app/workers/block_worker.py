import asyncio
import json
from datetime import datetime, timedelta
from aio_pika import connect
from aio_pika.abc import AbstractIncomingMessage
from ..database import AsyncSessionLocal
from ..models import User
from ..utils.config import settings

async def process_user_block(message: AbstractIncomingMessage):
    async with message.process():
        try:
            data = json.loads(message.body.decode())
            user_id = data["user_id"]
            block_duration = data["block_duration"]
            
            async with AsyncSessionLocal() as db:
                user = await db.get(User, user_id)
                if user:
                    user.is_blocked = True
                    user.blocked_until = datetime.now() + timedelta(seconds=block_duration)
                    db.add(user)
                    await db.commit()
                    print(f"User {user_id} blocked until {user.blocked_until}")
                    
        except Exception as e:
            print(f"Error processing block message: {e}")

async def main():
    connection = await connect(
        f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
    )
    
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        
        queue = await channel.declare_queue("userBlockQueue", durable=True)
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await process_user_block(message)

if __name__ == "__main__":
    asyncio.run(main())
