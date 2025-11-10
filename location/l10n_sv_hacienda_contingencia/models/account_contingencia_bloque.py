from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountContingenciaBloque(models.Model):
    _name = "account.contingencia.bloque"
    _description = "Bloque de 100 facturas en contingencia"

    name = fields.Char(string="Bloque", required=True)
    contingencia_id = fields.Many2one("account.contingencia1", string="Contingencia", ondelete="cascade")
    factura_ids = fields.Many2many("account.move", string="Facturas")
    cantidad = fields.Integer(string="Cantidad", compute="_compute_cantidad", store=True)
    company_id = fields.Many2one('res.company', string="Empresa", required=True, default=lambda self: self.env.company)
    bloque_activo = fields.Boolean(string="Bloque Activo", copy=False, default=True)

    @api.depends("factura_ids")
    def _compute_cantidad(self):
        for bloque in self:
            bloque.cantidad = len(bloque.factura_ids)

    @api.model
    def generar_nombre_bloque(self):
        # Genera un nombre para el bloque, por ejemplo, con el formato 'BLOQUE-001', 'BLOQUE-002', etc.
        last_block = self.search([], order="id desc", limit=1)
        new_block_number = last_block.id + 1 if last_block else 1
        return f"BLOQUE-{str(new_block_number).zfill(3)}"

    def action_ver_facturas_bloque(self):
        return {
            'name': 'Documentos Electrónicos del Bloque',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.factura_ids.ids)],
            'context': dict(self.env.context),
            'views': [
                (self.env.ref('l10n_sv_hacienda_contingencia.view_account_move_bloque_list').id, 'list'),
                (self.env.ref('account.view_move_form').id, 'form')
            ],
        }
