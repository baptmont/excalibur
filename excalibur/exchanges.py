import json
import pika


def publish(message):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.exchange_declare(exchange="excalibur", exchange_type="direct", durable=True)
    channel.queue_declare(queue="item_queue", durable=True)
    channel.queue_bind(exchange="excalibur", routing_key="item", queue="item_queue")

    channel.basic_publish(
        exchange="excalibur",
        routing_key="item",
        body=message,
    )
    connection.close()


def create_email_queue_dto(file):
    msg = {}
    msg["filename"] = file.filename
    msg["uploaded_at"] = file.uploaded_at
    msg["agency_name"] = file.agency_name if hasattr(file, "agency_name") else "-"
    msg["url"] = file.url if hasattr(file, "url") else "-"
    msg["from"] = "excalibur"
    return msg


def publish_new_file_message(file):
    message = json.dumps(create_email_queue_dto(file), default=str)

    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.exchange_declare(exchange="excalibur", exchange_type="direct", durable=True)
    channel.queue_declare(queue="email_queue", durable=True)
    channel.queue_bind(exchange="excalibur", routing_key="email", queue="email_queue")

    channel.basic_publish(
        exchange="excalibur",
        routing_key="email",
        body=message,
    )
    connection.close()
