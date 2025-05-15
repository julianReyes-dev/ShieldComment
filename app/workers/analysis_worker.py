import asyncio
import json
import logging
from datetime import datetime, timedelta
from aio_pika import Message, connect
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select
import torch
from transformers import pipeline

from app.database import AsyncSessionLocal
from app.models import CommentAnalysis, User
from app.utils.config import settings
from app.utils.queues import COMMENT_ANALYSIS_QUEUE, USER_BLOCK_QUEUE
from app.rabbitmq import publish_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar el modelo una vez al iniciar
toxicity_analyzer = pipeline(
    "text-classification",
    model="unitary/toxic-bert",
    return_all_scores=True,
    device="cuda" if torch.cuda.is_available() else "cpu"
)

async def analyze_toxicity(text: str) -> dict:
    """Analiza la toxicidad del texto usando toxic-bert"""
    try:
        results = toxicity_analyzer(text)
        toxic_score = next(
            (score['score'] for score in results[0] if score['label'] == 'toxic'),
            0.0
        )
        
        # Convertir a porcentaje (0-100)
        toxicity_score = int(toxic_score * 100)
        
        if toxicity_score > 70:
            classification = "toxic"
        elif toxicity_score > 30:
            classification = "potentially-toxic"
        else:
            classification = "non-toxic"
            
        return {
            "toxicity_score": toxicity_score,
            "classification": classification,
            "analysis_result": {
                "model": "unitary/toxic-bert",
                "scores": {item['label']: item['score'] for item in results[0]},
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error in toxicity analysis: {e}")
        return {
            "toxicity_score": 0,
            "classification": "error",
            "analysis_result": {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        }

async def process_comment_analysis(message: AbstractIncomingMessage):
    async with message.process():
        try:
            data = json.loads(message.body.decode())
            comment_id = data["comment_id"]
            user_id = data["user_id"]
            text = data["text"]

            logger.info(f"Processing comment {comment_id} from user {user_id}")

            # Realizar análisis de toxicidad
            analysis_result = await analyze_toxicity(text)

            async with AsyncSessionLocal() as db:
                # Guardar análisis
                analysis = CommentAnalysis(
                    comment_id=comment_id,
                    toxicity_score=analysis_result["toxicity_score"],
                    classification=analysis_result["classification"],
                    analysis_result=analysis_result["analysis_result"]
                )
                db.add(analysis)

                # Actualizar conteo de ofensas si es tóxico
                user = await db.get(User, user_id)
                if user and analysis_result["classification"] in ["toxic", "potentially-toxic"]:
                    user.offense_count += 1
                    db.add(user)

                await db.commit()

                # Verificar si se debe bloquear al usuario
                if user and user.offense_count >= 3 and not user.is_blocked:
                    block_duration = 3600 * (user.offense_count - 1)  # 1h por ofensa
                    block_message = {
                        "user_id": user.id,
                        "offense_count": user.offense_count,
                        "block_duration": block_duration
                    }
                    await publish_message(USER_BLOCK_QUEUE, json.dumps(block_message))

        except json.JSONDecodeError as e:
            logger.error(f"Invalid message format: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Podríamos implementar reintentos aquí

async def main():
    while True:
        try:
            connection = await connect(
                f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/",
                timeout=30
            )
            
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=2)
                
                queue = await channel.declare_queue(
                    COMMENT_ANALYSIS_QUEUE,
                    durable=True,
                    arguments={
                        'x-message-ttl': 86400000,
                        'x-max-length': 10000,
                        'x-dead-letter-exchange': 'dlx'
                    }
                )
                
                logger.info("Worker ready. Waiting for messages...")
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        await process_comment_analysis(message)
                        
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 10 seconds...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())