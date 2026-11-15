# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import grpc
import logging
from concurrent import futures

from exclave.task.full_model_update_exclave import FullModelUpdateExclave
from exclave.utils.constants import MAX_SEND_MSG_LENGTH, MAX_RECEIVE_MSG_LENGTH
from exclave.service.model_update_exclave import model_update_pb2
from exclave.service.model_update_exclave import model_update_pb2_grpc


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options = [
        ('grpc.max_send_message_length', MAX_SEND_MSG_LENGTH),
        ('grpc.max_receive_message_length', MAX_RECEIVE_MSG_LENGTH)
    ])
    logging.info("Initializing Full Model Update Exclave")
    # exclave object
    model_update_exclave = FullModelUpdateExclave()
    model_update_pb2_grpc.add_ModelUpdateServicer_to_server(
        model_update_exclave, server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    serve()
