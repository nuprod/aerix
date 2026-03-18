# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class nuprod_stock_package_zpl(models.Model):
    _inherit = "mrp.workcenter"

    mrp_report_id = fields.Many2one(
        "ir.actions.report",
        string="Étiquette à imprimer",
        domain=[("model", "=", "mrp.production")],
        help="The report action to print from production or workcenter",
        ondelete="cascade",
    )
