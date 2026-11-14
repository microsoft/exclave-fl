# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import grpc
import logging
from concurrent import futures

from exclave.task.cifar10_train_exclave import Cifar10TrainExclave
from exclave.utils.constants import MAX_SEND_MSG_LENGTH, MAX_RECEIVE_MSG_LENGTH
from exclave.service.training_exclave import training_pb2
from exclave.service.training_exclave import training_pb2_grpc

# Model Name
MODEL_NAME = "vgg9"

# Batch size
BATCH_SIZE = 64

# Epoch Number
EPOCH_NUMBER = 6

# Learning Rate
LEARNING_RATE = 1e-2

# Momentum
MOMENTUM = 0.9

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options = [
        ('grpc.max_send_message_length', MAX_SEND_MSG_LENGTH),
        ('grpc.max_receive_message_length', MAX_RECEIVE_MSG_LENGTH)
    ])
    logging.info("Initializing Cifar10 Training Exclave")
    # exclave object
    cifar10_train_exclave = Cifar10TrainExclave(epochs=EPOCH_NUMBER, batch_size=BATCH_SIZE, lr=LEARNING_RATE, momentum=MOMENTUM, model_name=MODEL_NAME)
    training_pb2_grpc.add_TrainServicer_to_server(
        cifar10_train_exclave, server)
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
