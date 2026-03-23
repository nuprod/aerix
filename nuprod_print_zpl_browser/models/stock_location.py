# -*- coding: utf-8 -*-

import base64

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class nuprod_stock_location_zpl(models.Model):
    _inherit = "stock.location"

    def action_nuprod_print_location_zpl(self):
        report_name = "nuprod_print_zpl_browser.report_nuprod_location_label_zpl"

        render = self.env["ir.actions.report"]._render(
            report_name,
            self.ids,
            {},
        )

        try:
            render_str = render[0].decode('utf-8').strip().replace('\n', '').replace('\r', '')
        except UnicodeDecodeError:
            render_str = render[0].decode('latin-1').strip().replace('\n', '').replace('\r', '')

        client_id = self.env.context.get("client_id", "BROADCAST")
        datas = {
            "render": render_str,
            "ip_address": "192.168.1.70",
            "client_id": client_id,
            "is_pdf": False,
        }

        _logger.error(render_str)
        self.env["bus.bus"]._sendone(
            "nuprod_print_browser",
            "nuprod_print_browser",
            datas,
        )