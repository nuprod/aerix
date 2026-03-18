# -*- coding: utf-8 -*-

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class nuprod_product_template_zpl(models.Model):
    _inherit = "product.template"

    def action_nuprod_print_product_zpl(self):
        action = self.env.ref(
            "product.report_productlabel_dymo"
        ).report_action(self.ids, config=False)
        if action:
            render = self.env["ir.actions.report"]._render(
                action["report_name"],
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


class nuprod_product_product_zpl(models.Model):
    _inherit = "product.product"

    def action_nuprod_print_product_zpl(self):
        action = self.env.ref(
            "product.report_productlabel_dymo"
        ).report_action(self.ids, config=False)
        if action:
            render = self.env["ir.actions.report"]._render(
                action["report_name"],
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
