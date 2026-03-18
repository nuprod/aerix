# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class nuprod_stock_package_zpl(models.Model):
    _inherit = "mrp.workorder"

    mrp_report_name = fields.Char(
        related="workcenter_id.mrp_report_id.report_name",
        store=True,
        depends=["workcenter_id.mrp_report_id"],
    )
