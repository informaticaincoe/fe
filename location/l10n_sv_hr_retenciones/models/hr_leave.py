from odoo import api, fields, models
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # vacation_type = fields.Selection([
    #     ('total', 'Vacaciones completas'),
    #     ('partial', 'Vacaciones parciales'),
    # ], string="Tipo de vacaciones")

    vacation_full = fields.Boolean(
        string="Vacaciones completas",
        help="Si está marcado, las vacaciones son completas; si no, son parciales."
    )

    @api.constrains('vacation_full', 'request_date_from', 'request_date_to', 'number_of_days')
    def _check_partial_vacation_days(self):
        _logger.info("=== Validación del tiempo personal ejecutada")
        # Detectar si estamos en instalación / carga de datos
        install_context = (
                self.env.context.get('module_install') or
                self.env.context.get('install_mode') or
                self.env.context.get('import_file') or
                self.env.context.get('test_enable') or
                # Detectar si hay módulos en proceso de instalación
                bool(self.env['ir.module.module'].sudo().search([('state', '=', 'to install')], limit=1))
        )

        if install_context:
            _logger.info("Saltando validación de vacaciones durante instalación/carga masiva")
            return

        for leave in self:
            # Solo aplica si NO son vacaciones completas
            _logger.info("Son vacaciones completas? %s", leave.vacation_full)
            if not leave.vacation_full:
                if leave.request_date_from and leave.request_date_to:
                    # Redondeamos hacia arriba para evitar que 7.5 días pase como válido
                    days = int(leave.number_of_days) if leave.number_of_days.is_integer() else int(
                        leave.number_of_days) + 1

                    if days > 8:
                        raise ValidationError(
                            f"Las vacaciones parciales no pueden exceder 8 días. "
                            f"Has seleccionado {days} días."
                        )
