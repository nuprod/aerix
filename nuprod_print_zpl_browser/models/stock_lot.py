# -*- coding: utf-8 -*-

from odoo import models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class nuprod_stock_lot_zpl(models.Model):
    _inherit = "stock.lot"

    def action_nuprod_print_lot_zpl(self):
        report_name = "nuprod_print_zpl_browser.nuprod_lot_template_zpl"
        printers = self.env["nuprod.config.printer"].search([("is_active", "=", True), ("label_type", "=", "zpl")], limit=1)
        if not printers:
            raise UserError("Veuillez configurer une imprimante ZPL active.")

        printer = printers[0]

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
            "client_id": client_id,
            "is_pdf": False,
            "connection_type": printer.network_type,
            "ip_address": printer.ip_address if printer.network_type == "ip" else None,
        }

        _logger.error(render_str)
        self.env["bus.bus"]._sendone(
            "nuprod_print_browser",
            "nuprod_print_browser",
            datas,
        )
