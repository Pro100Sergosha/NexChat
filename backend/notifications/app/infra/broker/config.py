"""RabbitMQ topology constants, shared by producer and consumer.

The broker itself opens connections lazily (see broker.py) from
``settings.RABBITMQ_URL``; there is no module-level client to hold open.
"""

EXCHANGE = "nexchat.notifications"
QUEUE = "notifications.emit"
ROUTING_KEY = "notification.emit"
BINDING_KEY = "notification.*"
