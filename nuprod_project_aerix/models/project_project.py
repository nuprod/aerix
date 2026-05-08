from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    nu_analytic_subplan_id = fields.Many2one(
        'account.analytic.plan',
        string='Sous-plan analytique',
        domain=lambda self: self._domain_nu_analytic_subplan(),
        help="Sous-plan du plan analytique 'Project' à appliquer au compte "
             "analytique créé pour ce projet.",
    )

    @api.model
    def _domain_nu_analytic_subplan(self):
        project_plan, _other_plans = self.env['account.analytic.plan']._get_all_plans()
        return [('root_id', '=', project_plan.id), ('parent_id', '!=', False)]

    @api.model
    def _get_values_analytic_account_batch(self, project_vals_list):
        vals_list = super()._get_values_analytic_account_batch(project_vals_list)
        for project_vals, vals in zip(project_vals_list, vals_list):
            subplan_id = project_vals.get('nu_analytic_subplan_id')
            if isinstance(subplan_id, (list, tuple)):
                subplan_id = subplan_id[0] if subplan_id else False
            if subplan_id:
                vals['plan_id'] = subplan_id
        return vals_list

    def _create_analytic_account(self):
        super()._create_analytic_account()
        for project in self:
            if project.nu_analytic_subplan_id and project.account_id \
                    and project.account_id.plan_id != project.nu_analytic_subplan_id:
                project.account_id.plan_id = project.nu_analytic_subplan_id
