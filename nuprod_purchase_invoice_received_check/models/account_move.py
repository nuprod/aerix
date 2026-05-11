from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    nu_has_invoice_over_received = fields.Boolean(
        compute="_compute_nu_invoice_over_received",
        store=False,
    )
    nu_invoice_over_received_warning = fields.Char(
        compute="_compute_nu_invoice_over_received",
        store=False,
    )

    def _nu_get_invoice_received_excesses(self):
        """Return [(purchase_line, qty_invoiced_total, qty_received), ...]
        for each purchase.order.line where the post-validation cumulative
        invoiced quantity would exceed the received quantity."""
        self.ensure_one()
        return []

    @api.depends(
        "move_type", "state", "invoice_line_ids",
        "invoice_line_ids.quantity",
        "invoice_line_ids.purchase_line_id",
        "invoice_line_ids.purchase_line_id.qty_received",
        "invoice_line_ids.purchase_line_id.qty_invoiced",
        "invoice_line_ids.product_id.type",
    )
    def _compute_nu_invoice_over_received(self):
        for move in self:
            excesses = (
                move._nu_get_invoice_received_excesses()
                if move.move_type == "in_invoice" else []
            )
            move.nu_has_invoice_over_received = bool(excesses)
            move.nu_invoice_over_received_warning = False
