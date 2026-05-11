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
        self.ensure_one()
        if self.move_type != "in_invoice":
            return []
        eligible_lines = self.invoice_line_ids.filtered(
            lambda l: l.purchase_line_id and l.product_id.type != "service"
        )
        if not eligible_lines:
            return []
        excesses = []
        po_lines = eligible_lines.purchase_line_id
        for po_line in po_lines:
            current_lines = eligible_lines.filtered(lambda l: l.purchase_line_id == po_line)
            # Convert each bill line's quantity to the PO line's UoM so the
            # comparison stays consistent with qty_invoiced and qty_received
            # (both expressed in po_line.product_uom_id).
            qty_current = sum(
                inv_line.product_uom_id._compute_quantity(
                    inv_line.quantity, po_line.product_uom_id
                )
                for inv_line in current_lines
            )
            qty_already_other = po_line.qty_invoiced - qty_current
            qty_total = qty_already_other + qty_current
            if qty_total - po_line.qty_received > 1e-6:
                excesses.append((po_line, qty_total, po_line.qty_received))
        return excesses

    def _post(self, soft=True):
        bypass_group = (
            "nuprod_purchase_invoice_received_check.group_force_invoice_without_reception"
        )
        for move in self:
            if move.move_type != "in_invoice":
                continue
            if self.env.user.has_group(bypass_group):
                continue
            excesses = move._nu_get_invoice_received_excesses()
            if excesses:
                details = "\n".join(
                    "  - %s : facturé %s / reçu %s" % (
                        po_line.product_id.display_name, total, recv,
                    )
                    for po_line, total, recv in excesses
                )
                raise UserError(_(
                    "Impossible de valider cette facture : les quantités "
                    "facturées dépassent les quantités reçues pour :\n%s",
                    details,
                ))
        return super()._post(soft=soft)

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
            if excesses:
                move.nu_invoice_over_received_warning = _(
                    "Quantités facturées supérieures aux quantités reçues :\n%s",
                    "\n".join(
                        "• %s : %s facturé / %s reçu" % (
                            po_line.product_id.display_name, total, recv,
                        )
                        for po_line, total, recv in excesses
                    ),
                )
            else:
                move.nu_invoice_over_received_warning = False
