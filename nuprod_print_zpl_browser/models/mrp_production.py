# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class nuprod_stock_package_zpl(models.Model):
    _inherit = "mrp.production"

    def action_nuprod_print_mrp_zpl(self):
        action = self.env.ref(
            "nuprod_print_zpl_browser.nuprod_production_zpl_report"
        ).report_action(self.ids, config=False)
        if action:
            client_id = self.env.context.get("client_id") or False
            self.send_print_render(action["report_name"], client_id)

    def send_print_render(self, template, client_id):
        render = self.env["ir.actions.report"]._render(
            template,
            self.ids,
        )
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
