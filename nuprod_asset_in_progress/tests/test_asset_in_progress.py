from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account_asset.tests.common import TestAccountAssetCommon


@tagged('post_install', '-at_install')
class TestAssetInProgress(TestAccountAssetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Comptes : en-cours 23x, définitif 205x, et un 21x non-en-cours.
        cls.account_23 = cls.env['account.account'].create({
            'name': "Immobilisations en cours",
            'code': '232000',
            'account_type': 'asset_fixed',
        })
        cls.account_205 = cls.env['account.account'].create({
            'name': "Concessions et droits similaires",
            'code': '205000',
            'account_type': 'asset_fixed',
        })
        cls.account_21 = cls.env['account.account'].create({
            'name': "Installations techniques",
            'code': '215000',
            'account_type': 'asset_fixed',
        })

        cls.journal_misc = cls.company_data['default_journal_misc']

        cls.mapping = cls.env['nu.asset.transfer.map'].create({
            'nu_company_id': cls.company.id,
            'nu_in_progress_account_id': cls.account_23.id,
            'nu_target_account_id': cls.account_205.id,
            'nu_journal_id': cls.journal_misc.id,
        })

    def _new_in_progress_asset(self, **kwargs):
        """Asset issu du compte 23x mappé, avec une date de mise en service."""
        vals = {
            'account_asset_id': self.account_23.id,
            'prorata_date': '2024-06-01',  # ≠ acquisition_date (2020-02-01)
        }
        vals.update(kwargs)
        return self.create_asset(10000, 'yearly', 5, **vals)

    # ------------------------------------------------------------------
    # §9.1 — Accès au code par société (anti-régression du bug `.code`)
    # ------------------------------------------------------------------
    def test_code_for_company(self):
        self.assertEqual(
            self.account_23._nu_code_for_company(self.company), '232000')

    # ------------------------------------------------------------------
    # §9.2 — Détection
    # ------------------------------------------------------------------
    def test_detection_in_progress_true(self):
        asset = self._new_in_progress_asset()
        self.assertTrue(asset.nu_is_in_progress)
        self.assertEqual(asset.nu_in_progress_account_id, self.account_23)

    def test_detection_in_progress_false(self):
        asset = self.create_asset(
            10000, 'yearly', 5, account_asset_id=self.account_21.id)
        self.assertFalse(asset.nu_is_in_progress)
        self.assertFalse(asset.nu_in_progress_account_id)

    # ------------------------------------------------------------------
    # §9.3 — Garde-fou date
    # ------------------------------------------------------------------
    def test_guard_date_blocks(self):
        # prorata_date == acquisition_date et pas de dérogation → UserError.
        asset = self.create_asset(
            10000, 'yearly', 5, account_asset_id=self.account_23.id,
            prorata_date='2020-02-01')
        self.assertEqual(asset.prorata_date, asset.acquisition_date)
        with self.assertRaises(UserError):
            asset.validate()
        # prorata_date n'a jamais été vidée (NOT NULL).
        self.assertTrue(asset.prorata_date)

    def test_guard_date_derogation(self):
        asset = self.create_asset(
            10000, 'yearly', 5, account_asset_id=self.account_23.id,
            prorata_date='2020-02-01', nu_is_force_in_service=True)
        asset.validate()
        self.assertTrue(asset.nu_transfer_move_id)

    # ------------------------------------------------------------------
    # §9.4 — Génération de l'OD
    # ------------------------------------------------------------------
    def test_transfer_move_generated_and_balanced(self):
        asset = self._new_in_progress_asset()
        asset.validate()
        move = asset.nu_transfer_move_id
        self.assertTrue(move, "Une OD de virement doit être générée.")
        self.assertEqual(move.move_type, 'entry')
        self.assertEqual(move.journal_id, self.journal_misc)
        self.assertEqual(move.date, asset.prorata_date)

        debit_line = move.line_ids.filtered(lambda l: l.debit)
        credit_line = move.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(debit_line.account_id, self.account_205)
        self.assertEqual(credit_line.account_id, self.account_23)
        self.assertEqual(debit_line.debit, asset.original_value)
        self.assertEqual(credit_line.credit, asset.original_value)
        self.assertEqual(
            sum(move.line_ids.mapped('debit')),
            sum(move.line_ids.mapped('credit')))

    # ------------------------------------------------------------------
    # §9.5 — Idempotence
    # ------------------------------------------------------------------
    def test_idempotent(self):
        asset = self._new_in_progress_asset()
        asset.validate()
        first_move = asset.nu_transfer_move_id
        self.assertTrue(first_move)
        # Relancer la génération ne crée pas de 2ᵉ OD.
        again = asset._nu_generate_transfer_move()
        self.assertEqual(again, first_move)
        self.assertEqual(asset.nu_transfer_move_id, first_move)

    # ------------------------------------------------------------------
    # §9.6 — Mapping manquant
    # ------------------------------------------------------------------
    def test_missing_mapping_raises(self):
        self.mapping.nu_is_active = False
        asset = self._new_in_progress_asset()
        with self.assertRaises(UserError):
            asset.validate()

    # ------------------------------------------------------------------
    # §9.7 — Mode posté vs brouillon
    # ------------------------------------------------------------------
    def test_draft_by_default(self):
        asset = self._new_in_progress_asset()
        asset.validate()
        self.assertEqual(asset.nu_transfer_move_id.state, 'draft')

    def test_auto_post_param(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'nuprod_asset_in_progress.auto_post', 'True')
        asset = self._new_in_progress_asset()
        asset.validate()
        self.assertEqual(asset.nu_transfer_move_id.state, 'posted')

    # ------------------------------------------------------------------
    # §9.8 — Analytique reportée
    # ------------------------------------------------------------------
    def test_analytic_distribution_carried(self):
        plan = self.env['account.analytic.plan'].create({'name': 'Plan test'})
        analytic = self.env['account.analytic.account'].create({
            'name': 'CC_Commercial', 'plan_id': plan.id})
        asset = self._new_in_progress_asset()
        asset.analytic_distribution = {str(analytic.id): 100}
        asset.validate()
        for line in asset.nu_transfer_move_id.line_ids:
            self.assertEqual(line.analytic_distribution, {str(analytic.id): 100})

    # ------------------------------------------------------------------
    # Mapping : contrainte compte 23x
    # ------------------------------------------------------------------
    def test_mapping_requires_23x_account(self):
        with self.assertRaises(ValidationError):
            self.env['nu.asset.transfer.map'].create({
                'nu_company_id': self.company.id,
                'nu_in_progress_account_id': self.account_21.id,  # 21x, pas 23x
                'nu_target_account_id': self.account_205.id,
                'nu_journal_id': self.journal_misc.id,
            })


@tagged('post_install', '-at_install')
class TestAssetRoutingAndAnalytic(TestAccountAssetCommon):
    """2.1 routage multi-cibles par modèle + 2.3 axes analytiques obligatoires."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal_misc = cls.company_data['default_journal_misc']

        def acc(code, name):
            return cls.env['account.account'].create({
                'name': name, 'code': code, 'account_type': 'asset_fixed'})

        cls.account_231 = acc('231000', "Immo corporelles en cours")
        cls.account_218 = acc('218300', "Matériel informatique")
        cls.account_213 = acc('213000', "Constructions")

        # Un modèle d'immobilisation pour discriminer.
        cls.model_info = cls.env['account.asset'].create({
            'name': "Modèle Matériel informatique",
            'state': 'model',
            'account_depreciation_id': cls.company_data['default_account_assets'].id,
            'account_depreciation_expense_id': cls.company_data['default_account_expense'].id,
            'journal_id': cls.journal_misc.id,
            'method_number': 3, 'method_period': '12', 'method': 'linear',
        })

        # 231000 → 218300 SI modèle "informatique" ; sinon (générique) → 213000.
        Map = cls.env['nu.asset.transfer.map']
        cls.map_info = Map.create({
            'nu_company_id': cls.company.id,
            'nu_in_progress_account_id': cls.account_231.id,
            'nu_target_account_id': cls.account_218.id,
            'nu_journal_id': cls.journal_misc.id,
            'nu_asset_model_id': cls.model_info.id,
        })
        cls.map_generic = Map.create({
            'nu_company_id': cls.company.id,
            'nu_in_progress_account_id': cls.account_231.id,
            'nu_target_account_id': cls.account_213.id,
            'nu_journal_id': cls.journal_misc.id,
        })

        # Plans analytiques pour 2.3.
        Plan = cls.env['account.analytic.plan']
        cls.plan_capex = Plan.create({'name': 'CAPEX'})
        cls.plan_cc = Plan.create({'name': 'Cost_Center'})
        Aacc = cls.env['account.analytic.account']
        cls.aa_capex = Aacc.create({'name': 'Projet X', 'plan_id': cls.plan_capex.id})
        cls.aa_cc = Aacc.create({'name': 'CC_Prod', 'plan_id': cls.plan_cc.id})

    def _asset_231(self, **kwargs):
        vals = {'account_asset_id': self.account_231.id, 'prorata_date': '2024-06-01'}
        vals.update(kwargs)
        return self.create_asset(10000, 'yearly', 5, **vals)

    # ---- 2.1 routage ----
    def test_multi_target_same_account_allowed(self):
        # Les deux mappings (même 231000, modèle différent/absent) coexistent.
        self.assertTrue(self.map_info.id and self.map_generic.id)
        self.assertEqual(self.map_info.nu_in_progress_account_id,
                         self.map_generic.nu_in_progress_account_id)

    def test_routing_by_model(self):
        asset = self._asset_231(model_id=self.model_info.id)
        asset.validate()
        debit_line = asset.nu_transfer_move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(debit_line.account_id, self.account_218)

    def test_routing_fallback_generic(self):
        asset = self._asset_231()  # pas de modèle → ligne générique
        asset.validate()
        debit_line = asset.nu_transfer_move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(debit_line.account_id, self.account_213)

    def test_duplicate_generic_blocked(self):
        with self.assertRaises(ValidationError):
            self.env['nu.asset.transfer.map'].create({
                'nu_company_id': self.company.id,
                'nu_in_progress_account_id': self.account_231.id,
                'nu_target_account_id': self.account_218.id,
                'nu_journal_id': self.journal_misc.id,
            })  # 2ᵉ ligne générique (sans modèle) sur le même 231000

    # ---- 2.3 axes analytiques obligatoires ----
    def _require_plans(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'nuprod_asset_in_progress.required_analytic_plan_ids',
            '%s,%s' % (self.plan_capex.id, self.plan_cc.id))

    def test_analytic_required_blocks(self):
        self._require_plans()
        asset = self._asset_231(model_id=self.model_info.id)
        with self.assertRaises(UserError):
            asset.validate()

    def test_analytic_required_satisfied(self):
        self._require_plans()
        asset = self._asset_231(model_id=self.model_info.id)
        asset.analytic_distribution = {
            str(self.aa_capex.id): 100, str(self.aa_cc.id): 100}
        asset.validate()
        self.assertTrue(asset.nu_transfer_move_id)

    def test_analytic_not_required_by_default(self):
        # Sans paramètre, aucune contrainte analytique.
        asset = self._asset_231(model_id=self.model_info.id)
        asset.validate()
        self.assertTrue(asset.nu_transfer_move_id)
