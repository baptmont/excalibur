import tempfile

import pika
import json
import requests
from excalibur import configuration as conf
from excalibur.www.views import create_files
from werkzeug.datastructures import FileStorage
from io import BytesIO
import asyncio


def get_file_urls(json_body):
    result_set = set()
    agency_name = ""
    for item in json_body:
        print(f"item  - {item} and set {result_set}")
        result_set = result_set.union(set(item["file_urls"]))
        agency_name = item["agency_name"]
    return list(result_set), agency_name


def download_file(file_url):
    name = file_url.split("/")[-1]
    request = requests.get(file_url)
    file = BytesIO(request.content)
    return file, name


async def download_files(file_urls, agency_name):
    for url in file_urls:
        file, name = download_file(url)
        content = FileStorage(stream=file, name=name, filename=name, content_type='application/pdf')
        create_files(content, agency_name=agency_name, url=url)


def items_queue_callback(ch, method, properties, body):
    json_body = json.loads(body)
    print(f"here - {json_body}")
    file_urls, agency_name = get_file_urls(json_body)
    print(f"here - {file_urls}")
    if file_urls:
        asyncio.run(download_files(file_urls, agency_name))  # TODO check if consume thread is not blocked


def consume():
    print("consume")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.queue_declare(queue="pdfs_queue", durable=True)

    channel.basic_consume(queue='pdfs_queue', on_message_callback=items_queue_callback, auto_ack=True)
    channel.start_consuming()


def publish(message):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.exchange_declare(exchange="excalibur",
                             exchange_type="direct",
                             durable=True)
    channel.queue_declare(queue="item_queue",
                          durable=True)
    channel.queue_bind(exchange="excalibur",
                       routing_key="item",
                       queue="item_queue")

    channel.basic_publish(
        exchange="excalibur",
        routing_key="item",
        body=message,
    )
    connection.close()


def create_email_queue_dto(file):
    msg = dict()
    msg['filename'] = file.filename
    msg['uploaded_at'] = file.uploaded_at
    msg['agency_name'] = file.agency_name if hasattr(file, 'agency_name') else "-"
    msg['url'] = file.url if hasattr(file, 'url') else "-"
    msg['from'] = 'excalibur'
    return msg


def publish_new_file_message(file):
    message = json.dumps(create_email_queue_dto(file), default=str)

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.exchange_declare(exchange="excalibur",
                             exchange_type="direct",
                             durable=True)
    channel.queue_declare(queue="email_queue",
                          durable=True)
    channel.queue_bind(exchange="excalibur",
                       routing_key="email",
                       queue="email_queue")

    channel.basic_publish(
        exchange="excalibur",
        routing_key="email",
        body=message,
    )
    connection.close()
