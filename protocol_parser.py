"""Deprecated shim kept so stale imports fail loudly.

The real implementations now live in controllers.parse_controller.ParseController
and model.protocols.* classes. Import that code directly instead of this module.
"""


class ProtocolParser:
    def __init__(self, *_, **__):
        raise RuntimeError("protocol_parser module was removed; use ParseController")

    @staticmethod
    def parse_inv_data(*_, **__):
        raise RuntimeError("ProtocolParser.parse_inv_data was removed; use InvLikeProtocol")

    @staticmethod
    def get_device_type_from_port(*_, **__):
        raise RuntimeError("ProtocolParser.get_device_type_from_port was removed")

    @staticmethod
    def get_device_category(*_, **__):
        raise RuntimeError("ProtocolParser.get_device_category was removed")
