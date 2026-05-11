# `nuprod_account_invoice_extract_partner` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Odoo 19 module `nuprod_account_invoice_extract_partner` that ensures the `partner_id` of a vendor bill received by mail forward is the OCR-identified supplier, not the internal forwarder. Adds a SIREN-from-VAT-FR matching pass to the native VAT→IBAN→name pipeline, drops `partner_id` from inbound mail when the sender is an internal employee, and offers a recovery path on `_save_form` for bills already polluted by a forwarder.

**Architecture:** Pure inheritance of `account.move`. No new model, no field, no view, no group. Two helper methods (`_nu_is_internal_sender`, `_nu_find_partner_by_siren_from_vat`) and three overrides (`message_new`, `_get_partner`, `_save_form`). The native Odoo Enterprise matching is reused as-is — we just unlock it and prepend a SIREN step.

**Tech Stack:** Odoo 19.0 Enterprise, Python 3.x, `account_invoice_extract` + `l10n_fr_siret` dependencies.

**Reference spec:** [docs/superpowers/specs/2026-05-11-account-invoice-extract-partner-design.md](../specs/2026-05-11-account-invoice-extract-partner-design.md)

---

## Pre-flight: test execution

All TDD steps assume a working Odoo 19 dev environment with `account_invoice_extract` (Enterprise) and `l10n_fr_siret` available in the addons path. The standard command used throughout is:

```bash
odoo-bin -d <DB_NAME> \
  --addons-path=<path/to/addons>,/Volumes/T7/Odoo/nupo/19.0/enterprise,/Volumes/T7/Odoo/nupo/19.0/custom/aerix \
  -u nuprod_account_invoice_extract_partner \
  --test-enable \
  --test-tags /nuprod_account_invoice_extract_partner \
  --stop-after-init \
  --log-level=test
```

Adapt `<DB_NAME>` and the addons path to your local setup. First install: replace `-u` with `-i`. To run a single test method: `--test-tags /nuprod_account_invoice_extract_partner:TestExtractPartner.test_method_name`.

---

## File structure

```
nuprod_account_invoice_extract_partner/
├── __init__.py                              # imports models
├── __manifest__.py                          # manifest dict
├── models/
│   ├── __init__.py                          # imports account_move
│   └── account_move.py                      # AccountMove inherit, ~90 lines
├── tests/
│   ├── __init__.py                          # imports test module
│   └── test_extract_partner.py              # 14 test methods, ~350 lines
└── static/description/
    └── icon.png                             # copied from a sibling nuprod_ module
```

All files live under `/Volumes/T7/Odoo/nupo/19.0/custom/aerix/nuprod_account_invoice_extract_partner/`.

---

## Task 1: Module skeleton (installable, empty)

**Files:**
- Create: `nuprod_account_invoice_extract_partner/__init__.py`
- Create: `nuprod_account_invoice_extract_partner/__manifest__.py`
- Create: `nuprod_account_invoice_extract_partner/models/__init__.py`
- Create: `nuprod_account_invoice_extract_partner/models/account_move.py`
- Create: `nuprod_account_invoice_extract_partner/tests/__init__.py`
- Copy: `nuprod_account_invoice_extract_partner/static/description/icon.png`

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p /Volumes/T7/Odoo/nupo/19.0/custom/aerix/nuprod_account_invoice_extract_partner/{models,tests,static/description}
```

- [ ] **Step 2: Create `__init__.py`**

```python
from . import models
```

- [ ] **Step 3: Create `__manifest__.py`**

```python
# -*- coding: utf-8 -*-
{
    "name": "nuprod_account_invoice_extract_partner",
    "summary": "Force le matching OCR du fournisseur sur les factures "
               "transférées par mail, et ajoute un matching par SIREN FR.",
    "description": """
      Sur les factures fournisseurs créées via mail.alias, ne pas écrire le
      partner_id du transféreur interne pour laisser l'OCR Odoo identifier le
      vrai fournisseur. Enrichit le pipeline de matching natif avec un
      fallback par SIREN dérivé de la VAT française. Fournit un mécanisme de
      rattrapage pour les factures dont le partner_id pointe encore vers un
      utilisateur interne au moment du traitement OCR.
    """,
    "author": "NUprod",
    "website": "https://www.nuprod.fr",
    "category": "Accounting/Accounting",
    "version": "19.0.0.0.0",
    "depends": ["account_invoice_extract", "l10n_fr_siret"],
    "data": [],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
}
```

- [ ] **Step 4: Create `models/__init__.py`**

```python
from . import account_move
```

- [ ] **Step 5: Create `models/account_move.py` (empty stub for now)**

```python
from odoo import api, models, tools


class AccountMove(models.Model):
    _inherit = "account.move"
```

- [ ] **Step 6: Create `tests/__init__.py`**

```python
from . import test_extract_partner
```

- [ ] **Step 7: Create `tests/test_extract_partner.py` (empty stub)**

```python
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestExtractPartner(TransactionCase):
    pass
```

- [ ] **Step 8: Copy the icon from a sibling Nuprod module**

```bash
cp /Volumes/T7/Odoo/nupo/19.0/custom/aerix/nuprod_purchase_invoice_received_check/static/description/icon.png \
   /Volumes/T7/Odoo/nupo/19.0/custom/aerix/nuprod_account_invoice_extract_partner/static/description/icon.png
```

- [ ] **Step 9: Install and verify the empty module loads**

Run with `-i nuprod_account_invoice_extract_partner` and confirm logs show the module installed without error and no tests fail (none exist yet).

- [ ] **Step 10: Commit**

```bash
git add nuprod_account_invoice_extract_partner
git commit -m "feat: scaffold nuprod_account_invoice_extract_partner module"
```

---

## Task 2: `_nu_is_internal_sender` helper

**Files:**
- Modify: `nuprod_account_invoice_extract_partner/models/account_move.py`
- Modify: `nuprod_account_invoice_extract_partner/tests/test_extract_partner.py`

This helper is used by both `message_new` (Task 3) and `_save_form` (Task 6). We build it standalone first.

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_extract_partner.py` with:

```python
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestExtractPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountMove = cls.env["account.move"]
        cls.internal_user = cls.env["res.users"].create({
            "name": "Internal User",
            "login": "internal@aerix.fr",
            "email": "internal@aerix.fr",
        })
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal User",
            "login": "portal@vendor.com",
            "email": "portal@vendor.com",
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })
        cls.external_partner = cls.env["res.partner"].create({
            "name": "External Vendor",
            "email": "billing@vendor.com",
        })

    def test_internal_sender_returns_true(self):
        move = self.AccountMove.new({})
        self.assertTrue(move._nu_is_internal_sender("internal@aerix.fr"))

    def test_internal_sender_with_name_wrapper(self):
        move = self.AccountMove.new({})
        self.assertTrue(
            move._nu_is_internal_sender('"Internal" <internal@aerix.fr>')
        )

    def test_portal_user_returns_false(self):
        # share=True users (portal) must not be treated as internal
        self.assertTrue(self.portal_user.share)
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("portal@vendor.com"))

    def test_inactive_user_returns_false(self):
        self.internal_user.active = False
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("internal@aerix.fr"))

    def test_external_partner_only_returns_false(self):
        # A partner with an email but no res.users must not be internal
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("billing@vendor.com"))

    def test_empty_email_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender(""))
        self.assertFalse(move._nu_is_internal_sender(None))

    def test_garbage_email_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("not an email"))
```

- [ ] **Step 2: Run tests, confirm they fail**

Run the standard test command. Expected: failures on every test with `AttributeError: 'account.move' object has no attribute '_nu_is_internal_sender'`.

- [ ] **Step 3: Implement `_nu_is_internal_sender`**

Edit `models/account_move.py`:

```python
from odoo import api, models, tools


class AccountMove(models.Model):
    _inherit = "account.move"

    def _nu_is_internal_sender(self, email_from):
        """True if email_from resolves to an active, non-portal employee.

        Used both at message_new (drop the forwarder partner_id) and at
        _save_form (force OCR re-match when the current partner_id is an
        internal user).
        """
        if not email_from:
            return False
        parsed = tools.email_normalize(email_from)
        if not parsed:
            return False
        user = self.env["res.users"].sudo().search(
            [
                ("active", "=", True),
                ("share", "=", False),
                ("partner_id.email_normalized", "=", parsed),
            ],
            limit=1,
        )
        return bool(user)
```

- [ ] **Step 4: Run tests, confirm they pass**

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add nuprod_account_invoice_extract_partner
git commit -m "feat: add _nu_is_internal_sender helper"
```

---

## Task 3: Override `message_new` to drop forwarder partner_id on purchase journals

**Files:**
- Modify: `nuprod_account_invoice_extract_partner/models/account_move.py`
- Modify: `nuprod_account_invoice_extract_partner/tests/test_extract_partner.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_extract_partner.py`:

```python
    # --- message_new tests ---

    def _purchase_journal(self):
        return self.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1,
        )

    def _sale_journal(self):
        return self.env["account.journal"].search(
            [("type", "=", "sale")], limit=1,
        )

    def _make_msg(self, email_from):
        return {
            "email_from": email_from,
            "to": "achats@aerix.odoo.com",
            "subject": "Fwd: facture",
            "body": "",
            "message_id": "<test@example.com>",
        }

    def test_message_new_drops_internal_sender_on_purchase_journal(self):
        journal = self._purchase_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "in_invoice",
            "partner_id": self.internal_user.partner_id.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("internal@aerix.fr"), custom_values=custom_values,
        )
        self.assertFalse(
            move.partner_id,
            "partner_id should be dropped when an internal user forwards a "
            "bill to the purchase alias",
        )

    def test_message_new_keeps_external_sender_on_purchase_journal(self):
        journal = self._purchase_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "in_invoice",
            "partner_id": self.external_partner.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("billing@vendor.com"), custom_values=custom_values,
        )
        self.assertEqual(move.partner_id, self.external_partner)

    def test_message_new_keeps_portal_user_partner_on_purchase_journal(self):
        journal = self._purchase_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "in_invoice",
            "partner_id": self.portal_user.partner_id.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("portal@vendor.com"), custom_values=custom_values,
        )
        self.assertEqual(move.partner_id, self.portal_user.partner_id)

    def test_message_new_keeps_internal_sender_on_sale_journal(self):
        journal = self._sale_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "out_invoice",
            "partner_id": self.internal_user.partner_id.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("internal@aerix.fr"), custom_values=custom_values,
        )
        self.assertEqual(
            move.partner_id, self.internal_user.partner_id,
            "Sale journal must not strip the partner_id of an internal user "
            "(out of scope for this module)",
        )

    def test_message_new_drops_internal_sender_with_journal_in_context(self):
        # Some mail.alias setups pass the journal via default_journal_id
        # context instead of custom_values
        journal = self._purchase_journal()
        custom_values = {
            "move_type": "in_invoice",
            "partner_id": self.internal_user.partner_id.id,
        }
        move = self.AccountMove.with_context(
            default_journal_id=journal.id,
        ).message_new(
            self._make_msg("internal@aerix.fr"), custom_values=custom_values,
        )
        self.assertFalse(move.partner_id)
```

- [ ] **Step 2: Run tests, confirm new tests fail**

Expected: 5 failures (tests assume an override that doesn't exist yet — native `message_new` keeps `partner_id`).

- [ ] **Step 3: Add the `message_new` override**

Edit `models/account_move.py`, add after `_nu_is_internal_sender`:

```python
    @api.model
    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        journal_id = (
            custom_values.get("journal_id")
            or self.env.context.get("default_journal_id")
        )
        journal = (
            self.env["account.journal"].browse(journal_id)
            if journal_id else self.env["account.journal"]
        )
        if (
            journal.type == "purchase"
            and self._nu_is_internal_sender(msg_dict.get("email_from"))
        ):
            custom_values.pop("partner_id", None)
        return super().message_new(msg_dict, custom_values=custom_values)
```

- [ ] **Step 4: Run tests, confirm they pass**

Expected: all 12 tests so far pass.

- [ ] **Step 5: Commit**

```bash
git add nuprod_account_invoice_extract_partner
git commit -m "feat: drop forwarder partner_id on purchase journal mails"
```

---

## Task 4: `_nu_find_partner_by_siren_from_vat` helper

**Files:**
- Modify: `nuprod_account_invoice_extract_partner/models/account_move.py`
- Modify: `nuprod_account_invoice_extract_partner/tests/test_extract_partner.py`

This helper is the new matching step. We test it in isolation before wiring it into `_get_partner` (Task 5).

- [ ] **Step 1: Append failing tests**

Append to `tests/test_extract_partner.py`:

```python
    # --- _nu_find_partner_by_siren_from_vat tests ---

    @classmethod
    def _siren_setup(cls):
        # Create a French vendor with a valid SIRET (siège: NIC = 00012)
        # SIREN 732829320 (Schneider Electric, publicly known) used here as
        # a syntactically valid SIREN. Any 9-digit string works for the test.
        cls.fr_vendor_siret = cls.env["res.partner"].create({
            "name": "FR Vendor Siège",
            "siret": "73282932000012",
            "supplier_rank": 1,
        })
        cls.fr_vendor_other_etab = cls.env["res.partner"].create({
            "name": "FR Vendor Établissement",
            "siret": "73282932000045",
            "supplier_rank": 0,
        })

    @classmethod
    def setUpClass(cls):
        # NOTE for the engineer: this is the SAME setUpClass as Task 2 with
        # _siren_setup() appended. Replace the existing setUpClass entirely.
        super().setUpClass()
        cls.AccountMove = cls.env["account.move"]
        cls.internal_user = cls.env["res.users"].create({
            "name": "Internal User",
            "login": "internal@aerix.fr",
            "email": "internal@aerix.fr",
        })
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal User",
            "login": "portal@vendor.com",
            "email": "portal@vendor.com",
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })
        cls.external_partner = cls.env["res.partner"].create({
            "name": "External Vendor",
            "email": "billing@vendor.com",
        })
        cls._siren_setup()

    def test_siren_match_returns_partner(self):
        move = self.AccountMove.new({})
        partner = move._nu_find_partner_by_siren_from_vat("FR12732829320")
        self.assertEqual(partner, self.fr_vendor_siret)

    def test_siren_match_picks_highest_supplier_rank(self):
        # Both partners share SIREN 732829320 — the one with the higher
        # supplier_rank (siège) wins.
        move = self.AccountMove.new({})
        partner = move._nu_find_partner_by_siren_from_vat("FR12732829320")
        self.assertEqual(partner, self.fr_vendor_siret)
        self.assertGreater(
            self.fr_vendor_siret.supplier_rank,
            self.fr_vendor_other_etab.supplier_rank,
        )

    def test_siren_match_handles_whitespace_in_vat(self):
        move = self.AccountMove.new({})
        partner = move._nu_find_partner_by_siren_from_vat("FR 12 732829320")
        self.assertEqual(partner, self.fr_vendor_siret)

    def test_siren_match_handles_lowercase_vat(self):
        move = self.AccountMove.new({})
        partner = move._nu_find_partner_by_siren_from_vat("fr12732829320")
        self.assertEqual(partner, self.fr_vendor_siret)

    def test_non_french_vat_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(
            move._nu_find_partner_by_siren_from_vat("BE0477472701"),
        )

    def test_french_vat_with_no_siret_in_db_returns_false(self):
        # VAT FR but with a SIREN that doesn't match any partner
        move = self.AccountMove.new({})
        self.assertFalse(
            move._nu_find_partner_by_siren_from_vat("FR99999999999"),
        )

    def test_empty_vat_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_find_partner_by_siren_from_vat(""))
        self.assertFalse(move._nu_find_partner_by_siren_from_vat(None))

    def test_malformed_vat_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(
            move._nu_find_partner_by_siren_from_vat("FR-not-a-vat"),
        )
```

- [ ] **Step 2: Run tests, confirm new tests fail**

Expected: 8 new failures with `AttributeError: '_nu_find_partner_by_siren_from_vat'`.

- [ ] **Step 3: Implement the helper**

Add to `models/account_move.py` (and add `import re` at the top):

```python
import re

from odoo import api, models, tools


SIREN_FROM_VAT_FR_RE = re.compile(r"^FR[0-9A-Z]{2}([0-9]{9})$")


class AccountMove(models.Model):
    _inherit = "account.move"

    # ... existing _nu_is_internal_sender ...
    # ... existing message_new ...

    def _nu_find_partner_by_siren_from_vat(self, vat_number_ocr):
        """If the OCR VAT looks like a French VAT, derive the SIREN
        (the trailing 9 digits) and return the partner whose SIRET starts
        with it. In multi-établissement situations, prefer the highest
        supplier_rank. Returns res.partner() empty recordset if no match."""
        if not vat_number_ocr:
            return self.env["res.partner"]
        cleaned = re.sub(r"\s", "", vat_number_ocr.upper())
        match = SIREN_FROM_VAT_FR_RE.match(cleaned)
        if not match:
            return self.env["res.partner"]
        siren = match.group(1)
        return self.env["res.partner"].search(
            [
                *self.env["res.partner"]._check_company_domain(self.company_id),
                ("siret", "=like", f"{siren}%"),
            ],
            order="supplier_rank desc",
            limit=1,
        )
```

Note on return type: returning an empty recordset (not `False`) is more idiomatic in Odoo and makes the `if partner_siren:` check in Task 5 work cleanly either way.

- [ ] **Step 4: Run tests, confirm they pass**

Expected: all tests so far pass.

- [ ] **Step 5: Commit**

```bash
git add nuprod_account_invoice_extract_partner
git commit -m "feat: add SIREN-from-VAT-FR matching helper"
```

---

## Task 5: Override `_get_partner` to insert SIREN matching

**Files:**
- Modify: `nuprod_account_invoice_extract_partner/models/account_move.py`
- Modify: `nuprod_account_invoice_extract_partner/tests/test_extract_partner.py`

The native `_get_partner` (from `account_invoice_extract/models/account_invoice.py:434`) is the orchestrator. We wrap it to insert SIREN matching after the VAT exact match and before the previous-extracts / IBAN / name fallbacks.

- [ ] **Step 1: Append failing tests**

Append to `tests/test_extract_partner.py`:

```python
    # --- _get_partner tests ---

    def _ocr_results(self, vat="", iban="", supplier_name=""):
        """Mock of the OCR result dict consumed by _get_partner and
        _save_form.

        Includes the minimum keys needed for _save_form (Task 6) not to
        crash on its native pipeline: invoice_lines (consumed by
        _get_invoice_lines), date/due_date/total/etc. (consumed by the
        field-by-field assignment block). Mirrors the structure returned
        by IAP — see
        account_invoice_extract/tests/test_invoice_extract.py for the
        full reference shape.
        """
        return {
            "VAT_Number": {
                "selected_value": {"content": vat},
                "candidates": [],
            },
            "iban": {
                "selected_value": {"content": iban},
                "candidates": [],
            },
            "supplier": {
                "selected_value": {"content": supplier_name},
                "candidates": [],
            },
            "invoice_lines": [],
            "date": {"selected_value": {"content": ""}, "candidates": []},
            "due_date": {"selected_value": {"content": ""}, "candidates": []},
            "total": {"selected_value": {"content": 0.0}, "candidates": []},
            "subtotal": {"selected_value": {"content": 0.0}, "candidates": []},
            "invoice_id": {"selected_value": {"content": ""}, "candidates": []},
            "currency": {"selected_value": {"content": ""}, "candidates": []},
            "payment_ref": {"selected_value": {"content": ""}, "candidates": []},
            "total_tax_amount": {"selected_value": {"content": 0.0}, "words": []},
            "SWIFT_code": {"selected_value": {"content": "{}"}, "candidates": []},
            "qr-bill": {"selected_value": {"content": ""}, "candidates": []},
            "client": {"selected_value": {"content": ""}, "candidates": []},
        }

    def _new_purchase_move(self, partner=None):
        journal = self._purchase_journal()
        return self.env["account.move"].create({
            "journal_id": journal.id,
            "move_type": "in_invoice",
            "partner_id": partner.id if partner else False,
        })

    def test_get_partner_matches_by_vat_first(self):
        # Native VAT match should win — SIREN helper never invoked.
        vat_partner = self.env["res.partner"].create({
            "name": "VAT Match",
            "vat": "FR12732829320",
            "supplier_rank": 5,
        })
        move = self._new_purchase_move()
        partner, created = move._get_partner(
            self._ocr_results(vat="FR12732829320"),
        )
        self.assertEqual(partner, vat_partner)
        self.assertFalse(created)

    def test_get_partner_falls_back_to_siren(self):
        # No partner with the exact VAT, but one has a SIRET starting with
        # the SIREN derived from the VAT.
        move = self._new_purchase_move()
        partner, created = move._get_partner(
            self._ocr_results(vat="FR12732829320"),
        )
        self.assertEqual(partner, self.fr_vendor_siret)
        self.assertFalse(created)

    def test_get_partner_non_french_vat_skips_siren(self):
        # Non-FR VAT → SIREN helper skipped → falls to native path.
        # We assert it doesn't crash and doesn't return our FR vendor.
        move = self._new_purchase_move()
        partner, created = move._get_partner(
            self._ocr_results(vat="BE0477472701"),
        )
        self.assertNotEqual(partner, self.fr_vendor_siret)
        self.assertNotEqual(partner, self.fr_vendor_other_etab)

    def test_get_partner_no_vat_no_siren_attempted(self):
        # No VAT at all → SIREN helper never invoked, native path
        # (name/IBAN) takes over.
        move = self._new_purchase_move()
        # extract_partner_name is the field used by native name matching
        move.extract_partner_name = "External Vendor"
        partner, _created = move._get_partner(self._ocr_results())
        # Native fuzzy name match should find "External Vendor"
        # (note: native returns False if no supplier_rank, but for this
        # smoke test we just assert no exception)
        self.assertTrue(True)
```

- [ ] **Step 2: Run tests, confirm the relevant ones fail or pass for the wrong reason**

Expected: the SIREN-fallback test (`test_get_partner_falls_back_to_siren`) fails — without our override, the native path goes straight from VAT-miss to previous-extracts/name/etc., never trying SIREN.

- [ ] **Step 3: Implement the `_get_partner` override**

Add to `models/account_move.py`:

```python
    def _get_partner(self, ocr_results):
        vat_number_ocr = self._get_ocr_selected_value(
            ocr_results, "VAT_Number", "",
        )
        if vat_number_ocr:
            partner_vat = self._find_partner_id_with_vat(vat_number_ocr)
            if partner_vat:
                return partner_vat, False
            partner_siren = self._nu_find_partner_by_siren_from_vat(
                vat_number_ocr,
            )
            if partner_siren:
                return partner_siren, False
        return super()._get_partner(ocr_results)
```

- [ ] **Step 4: Run tests, confirm they pass**

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add nuprod_account_invoice_extract_partner
git commit -m "feat: insert SIREN match into _get_partner pipeline"
```

---

## Task 6: Override `_save_form` for recovery when partner_id is an internal user

**Files:**
- Modify: `nuprod_account_invoice_extract_partner/models/account_move.py`
- Modify: `nuprod_account_invoice_extract_partner/tests/test_extract_partner.py`

When a bill arrives with `partner_id` already pointing to an internal user (because it was created before this module was installed, or via some other code path that bypasses `message_new`), `_save_form` should clear `partner_id` before delegating to super, so the native matching can run.

- [ ] **Step 1: Append failing tests**

Append to `tests/test_extract_partner.py`:

```python
    # --- _save_form tests ---

    def test_save_form_clears_internal_partner_then_rematches(self):
        # Bill currently has partner_id = internal user. OCR data points to
        # a real vendor (via VAT). _save_form should clear the internal user
        # and let the native flow set the real vendor.
        move = self._new_purchase_move(partner=self.internal_user.partner_id)
        vat_partner = self.env["res.partner"].create({
            "name": "Real Vendor",
            "vat": "FR12732829320",
            "supplier_rank": 5,
        })
        # Drive _save_form directly with our mocked OCR results
        move._save_form(self._ocr_results(vat="FR12732829320"))
        self.assertEqual(move.partner_id, vat_partner)

    def test_save_form_keeps_external_partner(self):
        # Bill has a real external partner — _save_form must not touch
        # partner_id (super will see partner_id set and skip _get_partner
        # entirely, which is the native behavior we want here).
        move = self._new_purchase_move(partner=self.external_partner)
        move._save_form(self._ocr_results(vat="FR12732829320"))
        self.assertEqual(move.partner_id, self.external_partner)

    def test_save_form_internal_partner_no_ocr_match_leaves_empty(self):
        # Bill has partner_id = internal user, OCR finds nothing useful.
        # We clear partner_id; native finds no match; result = empty.
        # Compromise: better an empty partner_id (forces manual entry) than
        # a wrong partner_id (forwarder) that misleads accounting.
        move = self._new_purchase_move(partner=self.internal_user.partner_id)
        move._save_form(self._ocr_results())
        self.assertFalse(move.partner_id)

    def test_save_form_portal_user_partner_kept(self):
        # A portal user is treated as external — its partner_id stays.
        move = self._new_purchase_move(partner=self.portal_user.partner_id)
        move._save_form(self._ocr_results(vat="FR12732829320"))
        self.assertEqual(move.partner_id, self.portal_user.partner_id)

    def test_save_form_refund_internal_partner_cleared(self):
        # in_refund must trigger the same recovery as in_invoice.
        journal = self._purchase_journal()
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "move_type": "in_refund",
            "partner_id": self.internal_user.partner_id.id,
        })
        vat_partner = self.env["res.partner"].create({
            "name": "Refund Vendor",
            "vat": "FR12732829320",
            "supplier_rank": 5,
        })
        move._save_form(self._ocr_results(vat="FR12732829320"))
        self.assertEqual(move.partner_id, vat_partner)
```

- [ ] **Step 2: Run tests, confirm the new ones fail**

Expected: `test_save_form_clears_internal_partner_then_rematches` and `test_save_form_refund_internal_partner_cleared` fail — without our override, the native `_save_form` sees `partner_id` already set (the internal user) and never re-matches.

- [ ] **Step 3: Implement the `_save_form` override**

Add to `models/account_move.py`:

```python
    def _save_form(self, ocr_results):
        needs_override = (
            self.move_type in ("in_invoice", "in_refund")
            and self.partner_id
            and self._nu_is_internal_sender(self.partner_id.email)
        )
        if needs_override:
            self.partner_id = False
        return super()._save_form(ocr_results)
```

- [ ] **Step 4: Run tests, confirm they pass**

Expected: all 26 tests pass.

- [ ] **Step 5: Commit**

```bash
git add nuprod_account_invoice_extract_partner
git commit -m "feat: recover internal-user partner_id on OCR _save_form"
```

---

## Task 7: Conventions check and install verification

**Files:** none modified — verification only.

- [ ] **Step 1: Run the `check-odoo-structure` skill**

Invoke the skill (Nuprod conventions audit) on the new module. Expected outcome: zero non-conformities. If any are flagged, fix them inline and re-run.

- [ ] **Step 2: Full uninstall / reinstall cycle**

```bash
odoo-bin -d <DB_NAME> --addons-path=... \
  --stop-after-init -u base \
  -i nuprod_account_invoice_extract_partner
```

Confirm clean install logs (no warnings about missing dependencies, no migration scripts triggered).

- [ ] **Step 3: Run the full test suite one more time**

```bash
odoo-bin -d <DB_NAME> --addons-path=... \
  -u nuprod_account_invoice_extract_partner \
  --test-enable \
  --test-tags /nuprod_account_invoice_extract_partner \
  --stop-after-init
```

Expected: all 26 tests pass, no warnings, no deprecation notices.

- [ ] **Step 4: Manual smoke test in a dev environment**

1. Forward a real (test) PDF invoice to the `purchase` mail alias from your own Odoo user email.
2. Check the chatter on the created bill — the forward message should appear with your email as sender.
3. Wait for OCR to complete (`extract_state == 'waiting_validation'` or `'done'`).
4. Confirm `partner_id` is either empty (no match found) or set to the OCR-identified vendor — **never** to your own user partner.

If the test fails: don't commit anything else. Open the bill, inspect `extract_prefill_data` and `extract_partner_name`, log the result of `move._nu_is_internal_sender(move.partner_id.email)` to understand which path was taken.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add nuprod_account_invoice_extract_partner
git commit -m "fix: <description of any conformity or smoke-test fix>"
```

- [ ] **Step 6: Document the migration step in the README of the existing manual workaround**

Tell the user (Aerix admin) to **disable** the existing server action + automation rule that did the ilike name match — the module supersedes them. Do not delete the rules from code; the admin disables them via the UI to keep the audit trail.

---

## Final reference: complete `models/account_move.py`

For convenience when reviewing — this is what the file should look like after all tasks:

```python
import re

from odoo import api, models, tools


SIREN_FROM_VAT_FR_RE = re.compile(r"^FR[0-9A-Z]{2}([0-9]{9})$")


class AccountMove(models.Model):
    _inherit = "account.move"

    def _nu_is_internal_sender(self, email_from):
        """True if email_from resolves to an active, non-portal employee."""
        if not email_from:
            return False
        parsed = tools.email_normalize(email_from)
        if not parsed:
            return False
        user = self.env["res.users"].sudo().search(
            [
                ("active", "=", True),
                ("share", "=", False),
                ("partner_id.email_normalized", "=", parsed),
            ],
            limit=1,
        )
        return bool(user)

    def _nu_find_partner_by_siren_from_vat(self, vat_number_ocr):
        """Match a partner by SIREN derived from a French VAT number."""
        if not vat_number_ocr:
            return self.env["res.partner"]
        cleaned = re.sub(r"\s", "", vat_number_ocr.upper())
        match = SIREN_FROM_VAT_FR_RE.match(cleaned)
        if not match:
            return self.env["res.partner"]
        siren = match.group(1)
        return self.env["res.partner"].search(
            [
                *self.env["res.partner"]._check_company_domain(self.company_id),
                ("siret", "=like", f"{siren}%"),
            ],
            order="supplier_rank desc",
            limit=1,
        )

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        journal_id = (
            custom_values.get("journal_id")
            or self.env.context.get("default_journal_id")
        )
        journal = (
            self.env["account.journal"].browse(journal_id)
            if journal_id else self.env["account.journal"]
        )
        if (
            journal.type == "purchase"
            and self._nu_is_internal_sender(msg_dict.get("email_from"))
        ):
            custom_values.pop("partner_id", None)
        return super().message_new(msg_dict, custom_values=custom_values)

    def _get_partner(self, ocr_results):
        vat_number_ocr = self._get_ocr_selected_value(
            ocr_results, "VAT_Number", "",
        )
        if vat_number_ocr:
            partner_vat = self._find_partner_id_with_vat(vat_number_ocr)
            if partner_vat:
                return partner_vat, False
            partner_siren = self._nu_find_partner_by_siren_from_vat(
                vat_number_ocr,
            )
            if partner_siren:
                return partner_siren, False
        return super()._get_partner(ocr_results)

    def _save_form(self, ocr_results):
        needs_override = (
            self.move_type in ("in_invoice", "in_refund")
            and self.partner_id
            and self._nu_is_internal_sender(self.partner_id.email)
        )
        if needs_override:
            self.partner_id = False
        return super()._save_form(ocr_results)
```
