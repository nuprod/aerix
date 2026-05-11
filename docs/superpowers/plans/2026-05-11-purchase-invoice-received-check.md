# `nuprod_purchase_invoice_received_check` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Odoo 19 module `nuprod_purchase_invoice_received_check` that blocks posting of vendor bills (`account.move` with `move_type='in_invoice'`) whose lines invoice more quantity than has actually been received on the linked purchase order line, with a proactive warning in draft and a bypass group.

**Architecture:** Pure inheritance of `account.move`. A single helper method `_nu_get_invoice_received_excesses` is the source of truth — used by both the computed warning field and the `_post` override. No new model, no stored fields, no migration.

**Tech Stack:** Odoo 19.0, Python 3.x, `purchase_stock` dependency (transitively pulls `account`, `purchase`, `stock`).

**Reference spec:** [docs/superpowers/specs/2026-05-11-purchase-invoice-received-check-design.md](../specs/2026-05-11-purchase-invoice-received-check-design.md)

---

## Pre-flight: test execution

All TDD steps assume a working Odoo 19 dev environment with a test database. The standard command used throughout is:

```bash
odoo-bin -d <DB_NAME> \
  --addons-path=<path/to/addons>,<path/to/Aerix/aerix> \
  -u nuprod_purchase_invoice_received_check \
  --test-enable \
  --test-tags /nuprod_purchase_invoice_received_check \
  --stop-after-init \
  --log-level=test
```

Adapt `<DB_NAME>` and the addons path to your local setup. For installing for the first time, replace `-u` with `-i`. To run a single test method, use `--test-tags /nuprod_purchase_invoice_received_check:TestInvoiceReceivedCheck.test_method_name`.

---

## File structure

```
nuprod_purchase_invoice_received_check/
├── __init__.py                              # imports models
├── __manifest__.py                          # manifest dict
├── models/
│   ├── __init__.py                          # imports account_move
│   └── account_move.py                      # AccountMove inherit, ~90 lines
├── security/
│   └── security.xml                         # group_force_invoice_without_reception
├── views/
│   └── account_move_views.xml               # banner on form view
├── tests/
│   ├── __init__.py                          # imports test module
│   └── test_invoice_received_check.py       # 12 test methods, ~280 lines
└── static/description/
    └── icon.png                             # copied from nuprod_project_aerix
```

All files live under `/Volumes/T7/Nuprod_Cloud/Clients/Aerix/aerix/nuprod_purchase_invoice_received_check/`.

---

## Task 1: Module skeleton (installable, empty)

**Files:**
- Create: `nuprod_purchase_invoice_received_check/__init__.py`
- Create: `nuprod_purchase_invoice_received_check/__manifest__.py`
- Create: `nuprod_purchase_invoice_received_check/models/__init__.py`
- Create: `nuprod_purchase_invoice_received_check/models/account_move.py`
- Create: `nuprod_purchase_invoice_received_check/tests/__init__.py`
- Copy: `nuprod_purchase_invoice_received_check/static/description/icon.png`

- [ ] **Step 1: Create the directory tree**

```bash
cd /Volumes/T7/Nuprod_Cloud/Clients/Aerix/aerix
mkdir -p nuprod_purchase_invoice_received_check/{models,security,views,tests,static/description}
```

- [ ] **Step 2: Create `nuprod_purchase_invoice_received_check/__init__.py`**

```python
from . import models
```

- [ ] **Step 3: Create `nuprod_purchase_invoice_received_check/__manifest__.py`**

```python
# -*- coding: utf-8 -*-
{
    "name": "nuprod_purchase_invoice_received_check",
    "summary": "Bloque la validation d'une facture fournisseur si la réception "
               "liée n'est pas réalisée.",
    "description": """
      Bloque la validation d'une facture fournisseur dont les quantités
      facturées dépassent les quantités reçues sur les lignes d'achat liées.
      Les factures sans achat lié, les lignes de service et les avoirs
      fournisseurs sont exclus du contrôle. Un groupe dédié permet de forcer
      la validation.
    """,
    "author": "NUprod",
    "website": "https://www.nuprod.fr",
    "category": "Accounting/Purchase",
    "version": "19.0.0.0.0",
    "depends": ["purchase_stock"],
    "data": [
        "security/security.xml",
        "views/account_move_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
}
```

- [ ] **Step 4: Create `nuprod_purchase_invoice_received_check/models/__init__.py`**

```python
from . import account_move
```

- [ ] **Step 5: Create `nuprod_purchase_invoice_received_check/models/account_move.py` (empty inherit)**

```python
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"
```

- [ ] **Step 6: Create `nuprod_purchase_invoice_received_check/tests/__init__.py`**

```python
from . import test_invoice_received_check
```

- [ ] **Step 7: Create placeholder test file `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`**

```python
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInvoiceReceivedCheck(TransactionCase):
    """Placeholder, populated in subsequent tasks."""
```

- [ ] **Step 8: Copy the icon from the existing module**

```bash
cp nuprod_project_aerix/static/description/icon.png \
   nuprod_purchase_invoice_received_check/static/description/icon.png
```

- [ ] **Step 9: Stub the still-referenced data files so install does not fail**

Create `nuprod_purchase_invoice_received_check/security/security.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
</odoo>
```

Create `nuprod_purchase_invoice_received_check/views/account_move_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
</odoo>
```

- [ ] **Step 10: Install and verify**

Run:

```bash
odoo-bin -d <DB_NAME> --addons-path=... -i nuprod_purchase_invoice_received_check --stop-after-init --log-level=info
```

Expected: log shows "Module nuprod_purchase_invoice_received_check loaded", "Modules loaded.", no traceback.

- [ ] **Step 11: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "feat(nuprod_purchase_invoice_received_check): module skeleton"
```

---

## Task 2: Test helpers + first behavioral test (fully received passes)

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`
- Modify: `nuprod_purchase_invoice_received_check/models/account_move.py`

- [ ] **Step 1: Write `setUpClass` and helpers in the test file**

Replace the placeholder test file with:

```python
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
```

Notes:
- `is_storable=True` flags the product as stock-tracked in Odoo 19. If your environment uses the older `type='product'`, replace accordingly.
- `purchase_method='receive'` makes Odoo prefill the bill with the received quantity (not the ordered quantity). Helps the partial-reception test setup.

- [ ] **Step 2: Write the failing test `test_invoice_fully_received`**

Append to `TestInvoiceReceivedCheck`:

```python
    def test_invoice_fully_received(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=10)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertFalse(invoice.nu_has_invoice_over_received)
```

- [ ] **Step 3: Run the test, see it fail**

```bash
odoo-bin -d <DB_NAME> --addons-path=... -u nuprod_purchase_invoice_received_check \
  --test-enable --test-tags /nuprod_purchase_invoice_received_check:TestInvoiceReceivedCheck.test_invoice_fully_received \
  --stop-after-init
```

Expected: FAIL — `AttributeError: 'account.move' object has no attribute 'nu_has_invoice_over_received'`.

- [ ] **Step 4: Add the boolean computed field (stub returning False)**

Replace the body of `AccountMove` in `models/account_move.py`:

```python
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
```

- [ ] **Step 5: Re-run the test, see it pass**

Same command as Step 3. Expected: 1 test passed.

- [ ] **Step 6: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "feat(nuprod_purchase_invoice_received_check): add computed fields, fully-received passes"
```

---

## Task 3: Detect partial reception (single PO line) + block in `_post`

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`
- Modify: `nuprod_purchase_invoice_received_check/models/account_move.py`

- [ ] **Step 1: Write the failing tests**

Append to `TestInvoiceReceivedCheck`:

```python
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
```

- [ ] **Step 2: Run, see both fail**

```bash
odoo-bin -d <DB_NAME> --addons-path=... -u nuprod_purchase_invoice_received_check \
  --test-enable --test-tags /nuprod_purchase_invoice_received_check:TestInvoiceReceivedCheck \
  --stop-after-init
```

Expected: `test_invoice_partially_received_blocks` FAIL (no UserError raised), `test_invoice_partially_received_at_received_qty` PASS by accident.

- [ ] **Step 3: Implement the helper + override `_post`**

Replace `_nu_get_invoice_received_excesses` and add the `_post` override:

```python
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
            qty_current = sum(current_lines.mapped("quantity"))
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
```

Also update the compute to populate the warning string:

```python
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
```

- [ ] **Step 4: Re-run all tests, all green**

Same command as Step 2. Expected: 3 tests passed.

- [ ] **Step 5: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "feat(nuprod_purchase_invoice_received_check): block on partial reception"
```

---

## Task 4: Exclusion — lines without PO link

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run, expect pass (filter already in place)**

Same `--test-tags` as before. Expected: PASS. The `purchase_line_id` filter from Task 3 already handles this case. If it fails, debug; otherwise the test locks the behavior in.

- [ ] **Step 3: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "test(nuprod_purchase_invoice_received_check): assert invoices without PO pass"
```

---

## Task 5: Exclusion — service lines

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
    def test_service_line_always_allowed(self):
        po = self._make_po(self.service, qty=10)
        # No receipt for service products (no picking generated).
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        self.assertFalse(invoice.nu_has_invoice_over_received)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
```

- [ ] **Step 2: Run, expect pass (service filter already in place)**

Filter `l.product_id.type != "service"` from Task 3 should handle this. Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "test(nuprod_purchase_invoice_received_check): assert service lines bypass control"
```

---

## Task 6: Exclusion — refunds (in_refund)

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run, expect pass (move_type filter in helper and `_post`)**

Both the helper and `_post` early-return when `move_type != "in_invoice"`. Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "test(nuprod_purchase_invoice_received_check): assert refunds bypass control"
```

---

## Task 7: Cumulative invoicing across multiple bills

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`

- [ ] **Step 1: Write the tests**

Append:

```python
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
```

- [ ] **Step 2: Run, expect pass (cumul handled by `qty_invoiced - qty_current`)**

The helper uses `po_line.qty_invoiced` (Odoo's stored cumulative) minus the current move's lines, so cumul across bills is naturally covered. Expected: PASS for both.

If one fails, inspect `qty_invoiced` on the PO line — Odoo recomputes it on `account.move` state changes; ensure the first bill is fully posted before computing the second.

- [ ] **Step 3: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "test(nuprod_purchase_invoice_received_check): cover cumulative invoicing"
```

---

## Task 8: Mixed lines + multiple invoice lines on same PO line

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`

- [ ] **Step 1: Write the tests**

Append:

```python
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
```

- [ ] **Step 2: Run, expect pass**

The helper aggregates by `purchase_line_id` and ignores lines without one. Expected: PASS for both.

- [ ] **Step 3: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "test(nuprod_purchase_invoice_received_check): cover mixed and multi-line cases"
```

---

## Task 9: Bypass group + security file

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/security/security.xml`
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run, see it fail**

Expected: `ValueError: External ID not found in the system: nuprod_purchase_invoice_received_check.group_force_invoice_without_reception`.

- [ ] **Step 3: Define the group**

Replace `security/security.xml` with:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="group_force_invoice_without_reception" model="res.groups">
        <field name="name">Forcer la validation de facture sans réception</field>
        <field name="category_id" ref="base.module_category_accounting_accounting"/>
        <field name="comment">Permet de valider une facture fournisseur même si les quantités facturées dépassent les quantités reçues.</field>
    </record>
</odoo>
```

- [ ] **Step 4: Re-run, expect pass**

Same `--test-tags` command, with `-u` to update the module so the new XML data is loaded. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "feat(nuprod_purchase_invoice_received_check): bypass group"
```

---

## Task 10: Warning recomputed on quantity change (regression guard)

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/tests/test_invoice_received_check.py`

- [ ] **Step 1: Write the test**

Append:

```python
    def test_warning_recomputed_on_quantity_change(self):
        po = self._make_po(self.product, qty=10)
        self._receive(po, qty=4)
        invoice = self._make_invoice_from_po(po)
        invoice.invoice_line_ids.write({"quantity": 10})
        self.assertTrue(invoice.nu_has_invoice_over_received)
        invoice.invoice_line_ids.write({"quantity": 4})
        self.assertFalse(invoice.nu_has_invoice_over_received)
        self.assertFalse(invoice.nu_invoice_over_received_warning)
```

- [ ] **Step 2: Run, expect pass**

The `@api.depends` declared in Task 3 includes `invoice_line_ids.quantity`. Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "test(nuprod_purchase_invoice_received_check): recompute warning on quantity change"
```

---

## Task 11: View — proactive warning banner

**Files:**
- Modify: `nuprod_purchase_invoice_received_check/views/account_move_views.xml`

This task is verified manually via the UI — no automated test for the banner rendering.

- [ ] **Step 1: Replace `views/account_move_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="nu_account_move_form_inherit" model="ir.ui.view">
        <field name="name">account.move.form.nu.invoice.received.check</field>
        <field name="model">account.move</field>
        <field name="inherit_id" ref="account.view_move_form"/>
        <field name="arch" type="xml">
            <xpath expr="//sheet" position="before">
                <div class="alert alert-warning" role="alert"
                     invisible="not nu_has_invoice_over_received or state != 'draft' or move_type != 'in_invoice'">
                    <field name="nu_invoice_over_received_warning" readonly="1" nolabel="1"/>
                </div>
                <field name="nu_has_invoice_over_received" invisible="1"/>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Update the module and verify the banner manually**

```bash
odoo-bin -d <DB_NAME> --addons-path=... -u nuprod_purchase_invoice_received_check --stop-after-init
```

Then in the UI:
1. Create a PO for the storable product, qty 10, confirm.
2. Receive 4 on the picking.
3. Create the bill from the PO. The bill prefills with quantity 4.
4. Manually set the bill line quantity to 10. The yellow banner appears in the form, listing the product and qty 10/4.
5. Reset the quantity to 4. The banner disappears.
6. Set back to 10, click "Confirm" — see the blocking `UserError` popup.

If anything misbehaves, fix the XML / xpath. Otherwise proceed.

- [ ] **Step 3: Commit**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "feat(nuprod_purchase_invoice_received_check): warning banner on bill form"
```

---

## Task 12: Final run + conventions audit

**Files:**
- None (verification only).

- [ ] **Step 1: Run the full test suite**

```bash
odoo-bin -d <DB_NAME> --addons-path=... -u nuprod_purchase_invoice_received_check \
  --test-enable --test-tags /nuprod_purchase_invoice_received_check \
  --stop-after-init --log-level=test
```

Expected: 12 tests pass, no failures, no errors.

Test inventory (matches spec section 9):
1. `test_invoice_no_purchase`
2. `test_invoice_fully_received`
3. `test_invoice_partially_received_blocks`
4. `test_invoice_partially_received_at_received_qty`
5. `test_service_line_always_allowed`
6. `test_refund_always_allowed`
7. `test_cumulative_invoicing_blocks`
8. `test_cumulative_invoicing_within_received`
9. `test_mixed_line_only_po_lines_checked`
10. `test_bypass_group_allows_validation`
11. `test_warning_recomputed_on_quantity_change`
12. `test_multiple_invoice_lines_same_po_line`

- [ ] **Step 2: Run the Nuprod structure audit**

Invoke the `check-odoo-structure` skill on the new module:

```
/check-odoo-structure nuprod_purchase_invoice_received_check
```

Expected: no `[STRUCTURE]`, `[MODÈLE]`, `[CHAMP]`, or `[VUE]` non-conformities. Fix any reported issue inline.

- [ ] **Step 3: Final commit (if anything was fixed in Step 2)**

```bash
git add nuprod_purchase_invoice_received_check
git commit -m "chore(nuprod_purchase_invoice_received_check): conventions Nuprod"
```

If nothing changed, skip the commit.

---

## Notes for the implementer

- **Odoo 19 product type API:** This plan assumes `type='consu'` + `is_storable=True` for stockable products and `type='service'` for services. If your Odoo 19 build still uses the older `type='product'` enumeration, swap accordingly in `setUpClass` and in the helper's filter (`l.product_id.type != "service"` is correct in both cases).
- **`purchase_method='receive':`** forces Odoo to prefill bills with received quantities rather than ordered quantities. Keeps test setup deterministic.
- **`_post(soft=True)` signature:** stable across Odoo 16–19. If a future Odoo version changes it, propagate `*args, **kwargs`.
- **No new ACL rows:** the module adds zero models, so `ir.model.access.csv` is intentionally absent.
- **Banner field declaration in view:** Odoo 17+ requires every field referenced in an `invisible=` expression to be present in the view, hence the explicit `<field name="nu_has_invoice_over_received" invisible="1"/>`.
