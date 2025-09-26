from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrSalaryAttachmentMassStateWizard(models.TransientModel):
    _name = 'hr.salary.attachment.mass.state.wizard'
    _description = 'Actualizar estado masivo de deducciones salariales'

    state = fields.Selection(
        [('open', 'En proceso'), ('close', 'Terminado'), ('cancel', 'Cancelado')],
        required=True, default='close', string='Nuevo estado'
    )
    end_date = fields.Date(string='Fecha de finalización', default=fields.Date.context_today)

    def _resolve_state_value(self, model):
        """Ajusta el valor del estado según el selection real del modelo."""
        sel_keys = [k for k, _ in model._fields['state'].selection]
        val = self.state
        if val in sel_keys:
            return val
        # tolera distintas grafías (cancel/canceled/cancelled)
        alt = {'cancel': 'cancelled', 'cancelled': 'cancel', 'close': 'close', 'open': 'open'} # Añadimos 'open' aquí para mayor seguridad
        if alt.get(val) in sel_keys:
            return alt[val]
        raise UserError(("El estado '%s' no existe en %s") % (val, model._name))

    def action_apply(self):
        attachments = self.env['hr.salary.attachment'].browse(self.env.context.get('active_ids', []))
        if not attachments:
            return {'type': 'ir.actions.act_window_close'}

        new_state = self._resolve_state_value(self.env['hr.salary.attachment'])

        # Ahora el código maneja los tres estados posibles
        if new_state == 'close':
            try:
                attachments.action_done()
            except Exception:
                attachments.write({'state': new_state})
        elif new_state == 'open':  # Nuevo bloque para el estado 'open'
            try:
                attachments.action_open()  # Intenta llamar a un método de acción si existe
            except Exception:
                attachments.write({'state': new_state})
        else:  # cancel/cancelled
            try:
                attachments.action_cancel()
            except Exception:
                attachments.write({'state': new_state})

        return {'type': 'ir.actions.act_window_close'}