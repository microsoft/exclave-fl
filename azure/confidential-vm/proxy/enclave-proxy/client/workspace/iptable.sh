#!/bin/sh

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# Initialization script responsible for setting up port forwarding to the Envoy proxy.

OUTBOUND_CAPTURE_PORT=15001
PROXY_UID=1337
PROXY_GID=${PROXY_UID}

# Clear the iptables setup.
iptables -t nat -F
iptables -t nat -X
iptables -t filter -F
iptables -t filter -X

# Dump variables for debugging purposes.
echo "Variables:"
echo "----------"
echo "INBOUND_CAPTURE_PORT=${INBOUND_CAPTURE_PORT}"
echo "OUTBOUND_CAPTURE_PORT=${OUTBOUND_CAPTURE_PORT}"
echo "PROXY_UID=${PROXY_UID}"
echo "PROXY_GID=${PROXY_GID}"
echo "PROXY_HEALTH_PORT=${PROXY_HEALTH_PORT}"
echo "INBOUND_PORTS_EXCLUDE=${INBOUND_PORTS_EXCLUDE}"
echo

# New chain to redirect TCP connections to the Envoy proxy listening on OUTBOUND_CAPTURE_PORT.
iptables -t nat -N HTTP_PROXY
iptables -t nat -A OUTPUT -p tcp -j HTTP_PROXY
iptables -t nat -A HTTP_PROXY -d 127.0.0.1/32 -j RETURN
iptables -t nat -A HTTP_PROXY -m owner --uid-owner ${PROXY_UID} -m owner --gid-owner ${PROXY_GID} -j RETURN
iptables -t nat -A HTTP_PROXY -p tcp --dport 50051 -j REDIRECT --to-ports 15001
iptables -t nat -A HTTP_PROXY -p tcp --dport 8102 -j REDIRECT --to-ports 15001
iptables -t nat -A HTTP_PROXY -p tcp --dport 8103 -j REDIRECT --to-ports 15001
