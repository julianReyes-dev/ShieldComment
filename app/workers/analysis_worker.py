from app.utils.queues import COMMENT_ANALYSIS_QUEUE, USER_BLOCK_QUEUE
import asyncio
import json
import logging
from aio_pika import Message, connect
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import CommentAnalysis, User
from app.utils.config import settings
from app.utils.toxicity_analyzer import analyze_toxicity
from app.rabbitmq import publish_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_comment_analysis(message: AbstractIncomingMessage):
    async with message.process():
        try:
            data = json.loads(message.body.decode())
            comment_id = data["comment_id"]
            user_id = data["user_id"]
            text = data["text"]

            logger.info(f"Processing comment analysis for comment ID: {comment_id}")

            # Perform toxicity analysis
            analysis_result = await analyze_toxicity(text)

            async with AsyncSessionLocal() as db:
                # Save analysis
                analysis = CommentAnalysis(
                    comment_id=comment_id,
                    toxicity_score=analysis_result["toxicity_score"],
                    classification=analysis_result["classification"],
                    analysis_result=analysis_result
                )
                db.add(analysis)

                # Update user offense count if comment is toxic
                user = await db.get(User, user_id)
                if user and analysis_result["classification"] in ["potentially-toxic", "toxic"]:
                    user.offense_count += 1
                    db.add(user)

                await db.commit()

                # Check if user should be blocked
                if user and user.offense_count >= 2 and not user.is_blocked:
                    block_message = {
                        "user_id": user.id,
                        "offense_count": user.offense_count,
                        "block_duration": 600  # 10 minutes
                    }
                    await publish_message("user_block_queue", json.dumps(block_message))

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Optionally: implement retry logic or dead letter queue

async def main():
    while True:
        try:
            connection = await connect(
                f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/",
                timeout=10
            )
            
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=1)
                
                queue = await channel.declare_queue(
                    COMMENT_ANALYSIS_QUEUE,
                    durable=True,
                    arguments={
                        'x-message-ttl': 86400000,  # 24h en ms
                        'x-max-length': 10000,
                        'x-dead-letter-exchange': 'dlx'  # Opcional para manejo de errores
                    }
)
                
                logger.info("Waiting for messages. To exit press CTRL+C")
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        await process_comment_analysis(message)
                        
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())