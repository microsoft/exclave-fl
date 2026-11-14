# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import grpc
import logging
from concurrent import futures

from exclave.task.ncbi_train_exclave import NCBITrainExclave
from exclave.utils.constants import MAX_SEND_MSG_LENGTH, MAX_RECEIVE_MSG_LENGTH
from exclave.service.training_exclave import training_pb2
from exclave.service.training_exclave import training_pb2_grpc

# Model Name
MODEL_NAME = "google/mobilebert-uncased"

# Batch size
BATCH_SIZE = 32

# Epoch Number
EPOCH_NUMBER = 4

# Learning Rate
LEARNING_RATE = 2e-5

# Number of Labels
NUM_LABELS = 3

# Ignore token
IGNORE_TOKEN = -100

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options = [
        ('grpc.max_send_message_length', MAX_SEND_MSG_LENGTH),
        ('grpc.max_receive_message_length', MAX_RECEIVE_MSG_LENGTH)
    ])
    logging.info("Initializing NLP Training Exclave")
    # exclave object
    ncbi_train_exclave = NCBITrainExclave(epochs=EPOCH_NUMBER, batch_size=BATCH_SIZE, lr=LEARNING_RATE, num_labels=NUM_LABELS, ignore_token=IGNORE_TOKEN, model_name=MODEL_NAME)
    training_pb2_grpc.add_TrainServicer_to_server(
        ncbi_train_exclave, server)
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
