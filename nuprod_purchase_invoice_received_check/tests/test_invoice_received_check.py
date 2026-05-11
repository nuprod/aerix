from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInvoiceReceivedCheck(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.product = cls.env["product.product"].create({
            "name": "Test Storable",
            "type": "consu",
            "is_storable": True,
            "purchase_method": "receive",
        })
        cls.service = cls.env["product.product"].create({
            "name": "Test Service",
            "type": "service",
            "purchase_method": "receive",
        })

    def _make_po(self, product, qty, price=100.0):
        po = self.env["purchase.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_qty": qty,
                "price_unit": price,
            })],
        })
        po.button_confirm()
        return po

    def _receive(self, po, qty):
        """Validate the first picking with the given received quantity."""
        picking = po.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))[:1]
        if not picking:
            return
        move = picking.move_ids[:1]
        move.write({"quantity": qty, "picked": True})
        picking._action_done()

    def _make_invoice_from_po(self, po):
        """Create a draft bill from the PO (Odoo prefills lines from PO)."""
        po.action_create_invoice()
        return po.invoice_ids[-1]

    def test_invoice_fully_received(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=10)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertFalse(invoice.nu_has_invoice_over_received)

    def test_invoice_partially_received_blocks(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=4)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        self.assertTrue(invoice.nu_has_invoice_over_received)
        self.assertIn("10", invoice.nu_invoice_over_received_warning or "")
        self.assertIn("4", invoice.nu_invoice_over_received_warning or "")
        with self.assertRaises(UserError):
            invoice.action_post()

    def test_invoice_partially_received_at_received_qty(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=4)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 4})
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertFalse(invoice.nu_has_invoice_over_received)

    def test_invoice_no_purchase(self):
        invoice = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 5,
                "price_unit": 50,
            })],
        })
        self.assertFalse(invoice.nu_has_invoice_over_received)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_service_line_always_allowed(self):
        po = self._make_po(self.service, qty=10)
        # No receipt for service products (no picking generated).
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        self.assertFalse(invoice.nu_has_invoice_over_received)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_refund_always_allowed(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=2)
        refund = self.env["account.move"].create({
            "move_type": "in_refund",
            "partner_id": self.partner.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 10,
                "price_unit": 100,
                "purchase_line_id": po.order_line.id,
            })],
        })
        self.assertFalse(refund.nu_has_invoice_over_received)
        refund.action_post()
        self.assertEqual(refund.state, "posted")

    def test_cumulative_invoicing_blocks(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=6)
        first = self._make_invoice_from_po(po)
        first.invoice_line_ids.write({"quantity": 6})
        first.action_post()
        self.assertEqual(first.state, "posted")
        second = self._make_invoice_from_po(po)
        second.invoice_line_ids.write({"quantity": 4})
        # Cumul: 6 (already invoiced) + 4 (current) = 10, received = 6 → block
        with self.assertRaises(UserError):
            second.action_post()

    def test_cumulative_invoicing_within_received(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=8)
        first = self._make_invoice_from_po(po)
        first.invoice_line_ids.write({"quantity": 5})
        first.action_post()
        second = self._make_invoice_from_po(po)
        second.invoice_line_ids.write({"quantity": 3})
        # Cumul: 5 + 3 = 8, received = 8 → allowed
        second.action_post()
        self.assertEqual(second.state, "posted")

    def test_mixed_line_only_po_lines_checked(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=2)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        # Add a free line (no PO link) — should NOT block on its own.
        free_product = self.env["product.product"].create({
            "name": "Free", "type": "service",
        })
        self.env["account.move.line"].with_context(check_move_validity=False).create({
            "move_id": invoice.id,
            "product_id": free_product.id,
            "quantity": 99,
            "price_unit": 1,
        })
        excesses = invoice._nu_get_invoice_received_excesses()
        self.assertEqual(len(excesses), 1)
        self.assertEqual(excesses[0][0], po.order_line)
        with self.assertRaises(UserError):
            invoice.action_post()

    def test_multiple_invoice_lines_same_po_line(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=4)
        invoice = self._make_invoice_from_po(po)
        # Set the existing line to 2, add another line on the same PO line for 3.
        # Cumul: 2 + 3 = 5, received = 4 → block.
        invoice.invoice_line_ids.write({"quantity": 2})
        self.env["account.move.line"].with_context(check_move_validity=False).create({
            "move_id": invoice.id,
            "product_id": self.product.id,
            "quantity": 3,
            "price_unit": 100,
            "purchase_line_id": po.order_line.id,
        })
        with self.assertRaises(UserError):
            invoice.action_post()

    def test_bypass_group_allows_validation(self):
        bypass_group = self.env.ref(
            "nuprod_purchase_invoice_received_check.group_force_invoice_without_reception"
        )
        bypass_user = self.env["res.users"].create({
            "name": "Bypass User",
            "login": "bypass_user_test",
            "groups_id": [(6, 0, [
                self.env.ref("account.group_account_invoice").id,
                self.env.ref("purchase.group_purchase_user").id,
                bypass_group.id,
            ])],
        })
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=4)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        invoice.with_user(bypass_user).action_post()
        self.assertEqual(invoice.state, "posted")

    def test_warning_recomputed_on_quantity_change(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=4)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        self.assertTrue(invoice.nu_has_invoice_over_received)
        invoice.invoice_line_ids.write({"quantity": 4})
        self.assertFalse(invoice.nu_has_invoice_over_received)
        self.assertFalse(invoice.nu_invoice_over_received_warning)
