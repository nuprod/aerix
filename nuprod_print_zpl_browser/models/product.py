# -*- coding: utf-8 -*-

import base64

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class nuprod_product_template_zpl(models.Model):
    _inherit = "product.template"

    def action_nuprod_print_product_zpl(self):
        layout = self.env["product.label.layout"].create({
            "print_format": "zpl",
            "custom_quantity": 1,
            "product_tmpl_ids": self.ids,
        })
        layout_data = layout.process()

        printers = self.env["nuprod.config.printer"].search([("is_active", "=", True), ("label_type", "=", "zpl")], limit=1)
        if not printers:
            raise UserError("Veuillez configurer une imprimante ZPL active.")

        printer = printers[0]

        if layout_data:
            layout_data["report_name"] = "nuprod_print_zpl_browser.report_nuprod_product_label_zpl"

            render = self.env["ir.actions.report"]._render(
                layout_data["report_name"],
                self.product_variant_ids.ids,
                layout_data["data"],
            )

            try:
                render_str = render[0].decode('utf-8').strip().replace('\n', '').replace('\r', '')
            except UnicodeDecodeError:
                render_str = render[0].decode('latin-1').strip().replace('\n', '').replace('\r', '')

            client_id = self.env.context.get("client_id", "BROADCAST")

            datas = {
                "render": render_str,
                "ip_address": printer.ip_address if printer.network_type == "ip" else None,
                "client_id": client_id,
                "is_pdf": False,
                "connection_type": printer.network_type,
            }

            self.env["bus.bus"]._sendone(
                "nuprod_print_browser",
                "nuprod_print_browser",
                datas,
            )



class nuprod_product_product_zpl(models.Model):
    _inherit = "product.product"

    def action_nuprod_print_product_zpl(self):
        layout = self.env["product.label.layout"].create({
            "print_format": "zpl",
            "custom_quantity": 1,
            "product_tmpl_ids": self.mapped('product_tmpl_id').ids,
        })
        layout_data = layout.process()

        if layout_data:
            layout_data["report_name"] = "nuprod_print_zpl_browser.report_nuprod_product_label_zpl"

            render = self.env["ir.actions.report"]._render(
                layout_data["report_name"],
                self.ids,
                layout_data["data"],
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

            self.env["bus.bus"]._sendone(
                "nuprod_print_browser",
                "nuprod_print_browser",
                datas,
            )