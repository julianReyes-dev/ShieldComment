import asyncio
import json
from aio_pika import Message, connect
from aio_pika.abc import AbstractIncomingMessage
from ..database import AsyncSessionLocal
from ..models import Comment, CommentAnalysis, User
from ..utils.config import settings
from ..rabbitmq import get_connection

async def analyze_toxicity(comment_text: str) -> dict:
    # TODO: Integrate with HuggingFace Transformers
    # For now, mock analysis
    toxic_words = ["idiota", "estúpido", "imbécil"]
    toxic_count = sum(1 for word in toxic_words if word in comment_text.lower())
    
    toxicity_score = min(100, toxic_count * 30)
    classification = "non-toxic"
    if toxicity_score > 70:
        classification = "toxic"
    elif toxicity_score > 30:
        classification = "potentially-toxic"
    
    return {
        "toxicity_score": toxicity_score,
        "classification": classification,
        "details": {
            "toxic_words_found": toxic_count,
            "model_version": "mock-v1"
        }
    }

async def process_comment_analysis(message: AbstractIncomingMessage):
    async with message.process():
        try:
            data = json.loads(message.body.decode())
            comment_id = data["comment_id"]
            user_id = data["user_id"]
            text = data["text"]
            
            # Perform toxicity analysis
            analysis_result = await analyze_toxicity(text)
            
            async with AsyncSessionLocal() as db:
                # Update comment analysis
                analysis = CommentAnalysis(
                    comment_id=comment_id,
                    toxicity_score=analysis_result["toxicity_score"],
                    classification=analysis_result["classification"],
                    analysis_result=analysis_result
                )
                db.add(analysis)
                
                # If toxic, increment user offense count
                if analysis_result["classification"] in ["potentially-toxic", "toxic"]:
                    user = await db.get(User, user_id)
                    if user:
                        user.offense_count += 1
                        db.add(user)
                
                await db.commit()
                
                # If user reached threshold, send to block queue
                user = await db.get(User, user_id)
                if user and user.offense_count >= 2:  # Threshold configurable
                    block_message = {
                        "user_id": user_id,
                        "offense_count": user.offense_count,
                        "block_duration": 600  # 10 minutes in seconds
                    }
                    await publish_message("userBlockQueue", json.dumps(block_message))
                    
        except Exception as e:
            print(f"Error processing message: {e}")

async def publish_message(queue_name: str, message: str):
    connection = await get_connection()
    channel = await connection.channel()
    await channel.declare_queue(queue_name, durable=True)
    await channel.default_exchange.publish(
        Message(body=message.encode()),
        routing_key=queue_name,
    )
    await channel.close()

async def main():
    connection = await connect(
        f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
    )
    
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        
        queue = await channel.declare_queue("commentAnalysisQueue", durable=True)
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await process_comment_analysis(message)

if __name__ == "__main__":
    asyncio.run(main())
