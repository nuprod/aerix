from odoo import models, fields, api
import logging
import base64
import json

_logger = logging.getLogger(__name__)


class NuprodStockPicking(models.Model):
    _inherit = "stock.picking"

    def action_nuprod_print_picking_zpl(self, zpl_file, printer_id=None, client_id="BROADCAST"):
        if not zpl_file:
            _logger.error("No ZPL file found.")
            return False

        try:
            render = base64.b64decode(zpl_file.datas).decode('utf-8')
        except UnicodeDecodeError:
            render = base64.b64decode(zpl_file.datas).decode('latin-1')

        if client_id == "BROADCAST":
            client_id = self.env.context.get("client_id", "BROADCAST")

        message = {
            "client_id": client_id,
            "ip_address": printer_id.ip_address if printer_id else "192.168.1.70",
            "render": render,
        }

        self.env['bus.bus']._sendone(
            'nuprod_print_browser',
            'nuprod_print_browser',
            message,
        )

        return True
