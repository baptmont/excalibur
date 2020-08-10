import tempfile

import pika
import json
import requests
from excalibur import configuration as conf
from excalibur.www.views import create_files
from werkzeug.datastructures import FileStorage
from io import BytesIO


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
    print(f"here - {request.content}")
    file = BytesIO(request.content)
    return file, name


def items_queue_callback(ch, method, properties, body):
    json_body = json.loads(body)
    print(f"here - {json_body}")
    file_urls, agency_name = get_file_urls(json_body)
    print(f"here - {file_urls}")
    if file_urls:
        for url in file_urls:
            file, name = download_file(url)
            print(f"content = {file}")
            content = FileStorage(stream=file, name=name, filename=name, content_type='application/pdf')
            create_files(content, agency_name=agency_name, url=url)


def consume():
    print("consume")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.basic_consume(queue='item_pdf', on_message_callback=items_queue_callback, auto_ack=True)
    channel.start_consuming()


def publish(message):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.exchange_declare(exchange="excalibur",
                             exchange_type="direct",
                             durable=True)
    channel.queue_declare(queue="item_scrape",
                          durable=True)
    channel.queue_bind(exchange="excalibur",
                       routing_key="item_scrape",
                       queue="item_scrape")

    channel.basic_publish(
        exchange="excalibur",
        routing_key="item_scrape",
        body=message,
    )

    connection.close()
