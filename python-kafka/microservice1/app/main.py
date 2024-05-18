from fastapi import FastAPI, HTTPException
from sqlmodel import SQLModel, Field
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app import settings
import logging
import asyncio
# Logging configuration
logging.basicConfig(level=logging.INFO)


class BookOrder(SQLModel):
    id: int = Field(default=None, primary_key=True)
    title: str
    user_id: int
    price: float


app = FastAPI()

@app.post("/order-book")
async def order_book(book_order: BookOrder):
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVER,
        acks="all",
    )
    logging.info(f"KAFKA_BOOTSTRAP_SERVER: {settings.KAFKA_BOOTSTRAP_SERVER}")
    logging.info(f"Book order received: {book_order.model_dump_json().encode('utf-8')}")

    await producer.start()

    try:
        await producer.send_and_wait(
            topic=settings.KAFKA_BOOK_ORDER_TOPIC,
            value=book_order.model_dump_json().encode('utf-8'),
            key=book_order.title.encode('utf-8'),
            headers=[("user_id", str(book_order.user_id).encode('utf-8'))]
        )
    finally:
        await producer.stop()

    return book_order

@app.get("/consumer")
async def consume_messages():
    consumer = AIOKafkaConsumer(
        settings.KAFKA_BOOK_ORDER_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVER,
        group_id=settings.KAFKA_CONSUMER_BOOK_GROUD_ID
    )
    await consumer.start()

    try:
        # msg = await consumer.getone()
        msg = await asyncio.wait_for(consumer.getone(), timeout=10.0)
        print(
            "{}:{:d}:{:d}: key={} value={} timestamp_ms={}".format(
                msg.topic, msg.partition, msg.offset, msg.key, msg.value,
                msg.timestamp)
        )
        return {"raw_message": msg, "value": msg.value.decode('utf-8')}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="No messages received within the timeout period")
    finally:
        logging.info("Stopping consumer")
        await consumer.stop()