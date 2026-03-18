# -*- coding: utf-8 -*-

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class nuprod_stock_location_zpl(models.Model):
    _inherit = "stock.location"

    def action_nuprod_print_location_zpl(self):
        render = self.env["ir.actions.report"]._render(
            "stock.report_generic_barcode",
            self.ids,
        )
        client_id = self.env.context.get("client_id")
        datas = {
            "render": render[0],
            "ip_adress": "192.168.1.32",
            "client_id": client_id or False,
        }
        self.env["bus.bus"]._sendone(
            "nuprod_print_browser",
            "client_id_print_zpl",
            datas,
        )
