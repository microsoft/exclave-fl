# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import grpc
import logging
from concurrent import futures

from exclave.task.svt_dp_exclave import SvtDpExclave
from exclave.utils.constants import MAX_SEND_MSG_LENGTH, MAX_RECEIVE_MSG_LENGTH
from exclave.service.dp_exclave import dp_pb2
from exclave.service.dp_exclave import dp_pb2_grpc

# DP parameters
FRACTION = 1
EPSILON = 0.1
NOISE_VAR = 1e+3
GAMMA = 1e-4
TAU = 1e-8

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options = [
        ('grpc.max_send_message_length', MAX_SEND_MSG_LENGTH),
        ('grpc.max_receive_message_length', MAX_RECEIVE_MSG_LENGTH)
    ])
    logging.info("Initializing SVT DP Exclave")
    # exclave object
    svt_dp_exclave = SvtDpExclave(fraction=FRACTION, epsilon=EPSILON, noise_var=NOISE_VAR, gamma=GAMMA, tau=TAU)
    dp_pb2_grpc.add_DifferentialPrivacyServicer_to_server(
        svt_dp_exclave, server)
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
