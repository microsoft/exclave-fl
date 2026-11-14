#!/bin/sh

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# two-way proxy iptables rules for the server that is deployed with exclaves

INBOUND_CAPTURE_PORT=15006
OUTBOUND_CAPTURE_PORT=15001
PROXY_UID=1337
PROXY_GID=${PROXY_UID}
PROXY_HEALTH_PORT=15021

INBOUND_PORTS_EXCLUDE="${PROXY_HEALTH_PORT}"


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

# INBOUND RULES
# New chain to redirect TCP connections to the Envoy proxy listening on INBOUND_CAPTURE_PORT.
iptables -t nat -N PROXY_IN_REDIRECT
iptables -t nat -A PROXY_IN_REDIRECT -p tcp -j REDIRECT --to-port ${INBOUND_CAPTURE_PORT}

# New chain to handle incoming TCP connections.
iptables -t nat -N PROXY_INBOUND
iptables -t nat -A PREROUTING -p tcp -j PROXY_INBOUND

# Connections to these ports need not be redirected to the Envoy proxy.
if [ -n "${INBOUND_PORTS_EXCLUDE}" ]; then
  for port in ${INBOUND_PORTS_EXCLUDE}; do
    iptables -t nat -A PROXY_INBOUND -p tcp --dport ${port} -j RETURN
  done
fi

# Redirect all other TCP traffic to the Envoy proxy.
iptables -t nat -A PROXY_INBOUND -p tcp -j PROXY_IN_REDIRECT

# OUTBOUND RULES
# Chain to redirect outbound flows
iptables -t nat -N PROXY_OUT_REDIRECT
iptables -t nat -A OUTPUT -p tcp -j PROXY_OUT_REDIRECT
iptables -t nat -A PROXY_OUT_REDIRECT -d 127.0.0.1/32 -j RETURN
# do not redirect messages from the proxy
iptables -t nat -A PROXY_OUT_REDIRECT -m owner --uid-owner ${PROXY_UID} -m owner --gid-owner ${PROXY_GID} -j RETURN
# redirect
iptables -t nat -A PROXY_OUT_REDIRECT -p tcp --dport 50051 -j REDIRECT --to-ports ${OUTBOUND_CAPTURE_PORT}
