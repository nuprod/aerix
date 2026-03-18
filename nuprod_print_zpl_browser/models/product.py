# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class nuprod_product_template_zpl(models.Model):
    _inherit = "product.template"

    def action_nuprod_print_product_zpl(self):
        layout = self.env["product.label.layout"].create(
            {
                "print_format": "zpl",
                "custom_quantity": 1,
                "product_tmpl_ids": self.ids,
            }
        )
        layout_data = layout.process()

        if layout_data:
            render = self.env["ir.actions.report"]._render(
                layout_data["report_name"],
                self.ids,
                layout_data["data"],
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


class nuprod_product_product_zpl(models.Model):
    _inherit = "product.product"

    def action_nuprod_print_product_zpl(self):
        layout = self.env["product.label.layout"].create(
            {
                "print_format": "zpl",
                "custom_quantity": 1,
                "product_ids": self.ids,
            }
        )
        layout_data = layout.process()

        if layout_data:
            render = self.env["ir.actions.report"]._render(
                layout_data["report_name"],
                self.ids,
                layout_data["data"],
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
