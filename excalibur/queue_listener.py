import tempfile

import pika
import json
import time
import requests
import traceback
from excalibur import configuration as conf
from excalibur.www.views import create_files
from werkzeug.datastructures import FileStorage
from io import BytesIO
import asyncio

RECONNECT_DELAY = 10  # reconnect delay in seconds


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
        content = FileStorage(
            stream=file, name=name, filename=name, content_type="application/pdf"
        )
        create_files(content, agency_name=agency_name, url=url)


def items_queue_callback(ch, method, properties, body):
    json_body = json.loads(body)
    print(f"here - {json_body}")
    file_urls, agency_name = get_file_urls(json_body)
    print(f"here - {file_urls}")
    if file_urls:
        asyncio.run(download_files(file_urls, agency_name))


def consume():
    print("consume")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host="localhost")
        )
        channel = connection.channel()

        channel.queue_declare(queue="pdfs_queue", durable=True)

        channel.basic_consume(
            queue="pdfs_queue", on_message_callback=items_queue_callback, auto_ack=True
        )
        channel.start_consuming()
    except KeyboardInterrupt:
        traceback.print_exc()
    except Exception as e:
        traceback.print_exc()
        time.sleep(RECONNECT_DELAY)
        print("Attempting to reconnect")
        consume()
