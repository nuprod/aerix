from odoo import models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    def _nu_code_for_company(self, company):
        """Retourne le code comptable de ce compte pour ``company``.

        Point d'accès UNIQUE au code comptable dans tout le module.

        En Odoo 17+, ``account.account.code`` n'est plus un champ stocké : c'est
        un computed ``@api.depends_context('company')`` basé sur ``code_store``
        (jsonb indexé par *root company*). Il ne faut donc jamais lire le jsonb à
        la main ni coder en dur une clé. Le seul accès fiable est
        ``with_company(company).code`` (Odoo gère la résolution root company +
        l'invalidation de cache). C'est exactement ce que cette méthode encapsule,
        pour router tout le module dessus et fermer la porte au bug historique
        (server action qui testait ``original_account.code`` inexistant).

        :param company: ``res.company`` pour laquelle lire le code.
        :return: le code (str) ou ``''`` si non défini pour cette société.
        """
        self.ensure_one()
        return self.with_company(company).code or ''
