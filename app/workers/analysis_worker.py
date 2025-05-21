import asyncio
import json
import logging
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from aio_pika import connect
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select
import torch
from transformers import pipeline

from app.database import AsyncSessionLocal
from app.models import CommentAnalysis, User, Comment
from app.utils.config import settings
from app.utils.queues import COMMENT_ANALYSIS_QUEUE, USER_BLOCK_QUEUE
from app.rabbitmq import publish_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar el modelo una vez
toxicity_analyzer = pipeline(
    "text-classification",
    model="unitary/toxic-bert",
    return_all_scores=True,
    device="cuda" if torch.cuda.is_available() else "cpu"
)

async def analyze_toxicity(text: str) -> dict:
    try:
        results = toxicity_analyzer(text)
        toxic_score = next((s['score'] for s in results[0] if s['label'] == 'toxic'), 0.0)
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
                # timestamp se sobreescribirá luego
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

            # Obtener una sola hora base para todo el análisis
            analysis_time = datetime.utcnow()
            analysis_result = await analyze_toxicity(text)
            analysis_result["analysis_result"]["timestamp"] = analysis_time.isoformat()

            async with AsyncSessionLocal() as db:
                user = await db.get(User, user_id)

                # ⚠️ Verificar ofensas recientes en los últimos 5 minutos
                five_minutes_ago = analysis_time - timedelta(minutes=5)
                recent_result = await db.execute(
                    select(CommentAnalysis)
                    .join(Comment, Comment.id == CommentAnalysis.comment_id)
                    .where(
                        Comment.user_id == user.id,
                        Comment.created_at >= five_minutes_ago,
                        CommentAnalysis.classification.in_(
                            ["toxic", "potentially-toxic"]
                        )
                    )
                )
                recent_offenses = recent_result.scalars().all()

                if (
                    len(recent_offenses) >= 2 and
                    analysis_result["classification"] in ["toxic", "potentially-toxic"]
                ):
                    logger.warning(f"Usuario {user.id} ya tiene 2 comentarios groseros en 5 minutos. Comentario {comment_id} rechazado.")
                    return

                # Guardar análisis
                analysis = CommentAnalysis(
                    comment_id=comment_id,
                    toxicity_score=analysis_result["toxicity_score"],
                    classification=analysis_result["classification"],
                    analysis_result=analysis_result["analysis_result"]
                )
                db.add(analysis)
                await db.commit() 

                # ⚠️ Aumentar conteo de ofensas
                if user and analysis_result["classification"] in ["toxic", "potentially-toxic"]:
                    last_offense_result = await db.execute(
                        select(CommentAnalysis)
                        .join(Comment, Comment.id == CommentAnalysis.comment_id)
                        .where(
                            Comment.user_id == user.id,
                            CommentAnalysis.classification.in_(
                                ["toxic", "potentially-toxic"]
                            )
                        )
                        .order_by(Comment.created_at.desc())
                        .limit(1)
                    )
                    last_offense = last_offense_result.scalar_one_or_none()

                    if last_offense:
                        last_time = isoparse(last_offense.analysis_result.get("timestamp"))
                        if (analysis_time - last_time).total_seconds() > 3600:
                            user.offense_count = 0

                    user.offense_count += 1
                    db.add(user)
                    await db.commit()

                    # 🚫 Bloqueo automático por ofensas recientes
                    if len(recent_offenses) >= 1:  # Ya había una, esta sería la 2da
                        block_duration = 3600  # 1 hora en segundos
                        unblock_time = analysis_time + timedelta(seconds=block_duration)
                        
                        user.is_blocked = True
                        user.blocked_until = unblock_time
                        db.add(user)
                        await db.commit()
                        
                        block_message = {
                            "user_id": user.id,
                            "block_duration": block_duration,
                            "unblock_at": unblock_time.isoformat()
                        }
                        
                        await publish_message(USER_BLOCK_QUEUE, json.dumps(block_message))
                        logger.info(f"Usuario {user.id} bloqueado por 1 hora")
                        return
                    # 🚫 Bloqueo escalonado por acumulación total
                    if user.offense_count >= 3 and not user.is_blocked:
                        block_duration = 3600 * (user.offense_count - 1)
                        unblock_time = analysis_time + timedelta(seconds=block_duration)

                        user.is_blocked = True
                        user.blocked_until = unblock_time
                        db.add(user)
                        await db.commit()

                        block_message = {
                            "user_id": user.id,
                            "offense_count": user.offense_count,
                            "block_duration": block_duration,
                            "unblock_at": unblock_time.isoformat()
                        }

                        await publish_message(USER_BLOCK_QUEUE, json.dumps(block_message))
                        logger.info(f"Usuario {user.id} será bloqueado desde {analysis_time.isoformat()} hasta {unblock_time.isoformat()} (duración: {block_duration // 3600}h)")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid message format: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

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
