# l10n_sv_haciendaws_fe/models/ir_sequence_ext.py
from odoo import models, fields
from odoo.tools import frozendict
from odoo.exceptions import UserError
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)

class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    def _get_prefix_suffix(self, date=None, date_range=None):
        """
        NUNCA retornar bool/None. Siempre una tupla (prefix, suffix).
        Si la FE está desactivada, delega al super() para comportamiento estándar.
        """
        # Usa env.company (más claro que self.company_id aquí)
        # if not self.env.company.sit_facturacion:
        #     return super()._get_prefix_suffix(date=date, date_range=date_range)

        # --- Detectar si la secuencia tiene variables DTE ---
        dte_vars = ['%(dte)s', '%(estable)s', '%(punto_venta)s', '%(tipo_dte)s']
        use_dte_logic = any(var in (self.prefix or '') + (self.suffix or '') for var in dte_vars)

        if not use_dte_logic:
            # No es DTE → flujo estándar de Odoo
            return super()._get_prefix_suffix(date=date, date_range=date_range)

        def _interpolate(s, d):
            return (s % d) if s else ''

        def _interpolation_dict():
            # Usa env.context (preferible a self._context)
            tz_name = self.env.context.get('tz') or 'UTC'
            now = range_date = effective_date = datetime.now(pytz.timezone(tz_name))

            if date or self.env.context.get('ir_sequence_date'):
                effective_date = fields.Datetime.from_string(date or self.env.context.get('ir_sequence_date'))
            if date_range or self.env.context.get('ir_sequence_date_range'):
                range_date = fields.Datetime.from_string(date_range or self.env.context.get('ir_sequence_date_range'))

            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S',
            }
            res = {}
            for key, fmt in sequences.items():
                res[key] = effective_date.strftime(fmt)
                res['range_' + key] = range_date.strftime(fmt)
                res['current_' + key] = now.strftime(fmt)

            # Variables DTE personalizadas (poner defaults seguros)
            ctx = self.env.context
            res['dte'] = ctx.get('dte', '')
            res['estable'] = ctx.get('estable', '')
            res['punto_venta'] = ctx.get('punto_venta', '')
            res['tipo_dte'] = ctx.get('tipo_dte', '')
            return frozendict(res)

        self.ensure_one()
        d = _interpolation_dict()
        try:
            interpolated_prefix = _interpolate(self.prefix, d)
            interpolated_suffix = _interpolate(self.suffix, d)
        except (ValueError, TypeError, KeyError) as e:
            # Mensaje claro y NUNCA retornes False aquí
            raise UserError('Secuencia mal definida "%s": %s' % (self.name, str(e)))

        # Siempre devuelve tupla de strings (posiblemente vacíos)
        return interpolated_prefix or '', interpolated_suffix or ''
