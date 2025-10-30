from odoo import fields, models, api, _
from odoo.exceptions import UserError

class SvtaxOverrideWizard(models.TransientModel):
    _name = 'sv.tax.override.wizzard'
    _desciption = 'Sleccionar cuientas alternativas para impuestos'

    move_id = fields.Many2one(
        'account.move',
        required=True,
        string='Asiento Contable',
        ondelete='cascade'
    )
    line_ids = fields.Many2many(
        'sv.tax.override.wizzard.line',
        'wizard_id',
        string='Líneas de impuesto a ajustar'
    )

    @api.model
    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No hay líneas de impuestos que ajustar."))
        for wl in self.line_ids:
            if not wl.account_id:
                raise UserError(_("selecciones una cuenta para el impuesto %s") % (wl.tax_id.display_name,))
            # Cambiar SOLO la linea de impuesto de esta factura
            wl.tax_move_line_id.write({'account_id': wl.account_id.id})
        # Reintentar la validacion sin volver a abrir el asistente
        return self.move_id.with_context(sv_skip_tax_override=True).action_post()

class SvTaxOverrideWizardLine(models.TransientModel):
    _name = 'sv.tax.override.wizzard.line'
    _description = 'Línea de impuesto a ajustar en el asistente de cuentas alternativas'

    wizard_id = fields.Many2one(
        'sv.tax.override.wizzard',
        required=True,
        string='Asistente de ajuste de cuentas',
        ondelete='cascade'
    )
    tax_move_line_id = fields.Many2one(
        'account.move.line',
        required=True,
        string='Línea de impuesto',
        ondelete='cascade'
    )
    tax_id = fields.Many2one(
        related='tax_move_line_id.tax_line_id',
        store=False,
        readonly=True
    )
    default_account_id = fields.Many2one(related='tax_move_line_id.tax_repartition_line_id.account_id',
                                         store=False, readonly=True, string='Cuenta por defecto')
    allowed_account_ids = fields.Many2many('account.account', string='Cuentas permitidas')
    account_id = fields.Many2one('account.account', string='Cuenta a usar', domain="[('id','in',allowed_account_ids)]")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)

        # cargar allowed_account_ids desde el impuesto
        if vals.get('tax_move_line_id'):
            line = self.env['account.move.line'].browse(vals['tax_move_line_id'])
            tax = line.tax_line_id
            allowed = tax.sv_sencodary_account_ids.mapped('account_id').ids

            # si no hay configuradas, al menos permitir escoger cuenta del pasivo/Activo
            if not allowed:
                allowed = self.env['account.account'].search([('company_id','=',line.company_id.id)]).ids
            vals['allowed_account_ids']= [(6, 0, allowed)]
        return vals
    