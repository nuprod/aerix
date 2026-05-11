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
