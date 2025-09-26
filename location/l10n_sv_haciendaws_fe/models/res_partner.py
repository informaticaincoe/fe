from odoo import fields, models, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario",
        help="Seleccione el diario por defecto para este cliente",
        domain=lambda self: self._get_allowed_journals_domain()
    )

    def _get_allowed_journals_domain(self):
        # Tomar configuración de la compañía actual
        config = self.env['res.configuration'].sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        if config and config.journal_ids:
            return [('id', 'in', config.journal_ids.ids)]
        return []