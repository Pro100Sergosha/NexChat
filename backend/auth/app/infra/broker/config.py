"""RabbitMQ topology for publishing to the notifications service.

Mirrors the contract owned by ``notifications`` (its ``infra/broker/config.py``):
auth is only a producer, so it declares the exchange and publishes with the
``notification.emit`` routing key — the notifications consumer owns the queue.
"""

EXCHANGE = "nexchat.notifications"
ROUTING_KEY = "notification.emit"
