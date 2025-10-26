from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round

import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [purchase-account_move_line]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    apply_percepcion = fields.Boolean(
        string="Percepción 1%",
        default=False,
    )

    percepcion_amount = fields.Monetary(
        string="Monto percepción",
        currency_field='currency_id',
        readonly=True,
        store=True,
        compute='_compute_percepcion_retencion_amount'
    )

    apply_retencion = fields.Boolean(
        string="Retencion IVA",
        default=False,
    )

    retencion_amount = fields.Monetary(
        string="Monto retención IVA",
        currency_field='currency_id',
        readonly=True,
        store=True,
        compute='_compute_percepcion_retencion_amount'
    )

    renta_percentage = fields.Float(
        string="% Renta",
        digits=(5, 2),
        default=0.0,
        help="Porcentaje de renta que se aplicará al subtotal de la línea"
    )

    renta_amount = fields.Monetary(
        string="Renta",
        currency_field='currency_id',
        store=True,
    )

    @api.depends('apply_percepcion', 'apply_retencion', 'renta_percentage', 'price_subtotal')
    def _compute_percepcion_retencion_amount(self):
        """Calcula los montos de percepción, retención y renta sobre el subtotal de la línea.
        - Aplica solo a facturas de proveedor (IN_INVOICE, IN_REFUND) que no sean FSE.
        - Usa los porcentajes configurados en 'percepcion' y 'retencion_iva'.
        - Si renta_percentage > 0, calcula el monto correspondiente.
        - Reinicia a 0 los montos cuando no aplican.
        """
        for line in self:
            # Verificamos si es una factura de compra
            tipo_doc = line.move_id.journal_id.sit_tipo_documento if line.move_id.journal_id else None
            if line.move_id.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and (not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE):
                #---- PERCEPCION 1%
                if line.apply_percepcion:
                    porc_percepcion = config_utils.get_config_value(self.env, 'percepcion', self.company_id.id)
                    # Validar que el valor exista y sea numérico
                    try:
                        porc_percepcion = float(porc_percepcion)
                        porc_percepcion = porc_percepcion / 100.0
                    except (TypeError, ValueError):
                        porc_percepcion = 0.0

                    line.percepcion_amount = float_round(line.price_subtotal * porc_percepcion, precision_rounding=move.currency_id.rounding)
                    _logger.info("SIT | Línea %s: apply_percepcion=TRUE, price_subtotal=%s, percepcion_amount calculado=%s",
                                 line.name, line.price_subtotal, line.percepcion_amount)
                else:
                    line.percepcion_amount = 0.0
                    _logger.info("SIT | Línea %s: apply_percepcion=FALSE, percepcion_amount reiniciado a 0", line.name)

                # ---- RETENCION 1%
                if line.apply_retencion:
                    porc_retencion = config_utils.get_config_value(self.env, 'retencion_iva', self.company_id.id)
                    # Validar que el valor exista y sea numérico
                    try:
                        porc_retencion = float(porc_retencion)
                        porc_retencion = porc_retencion / 100.0
                    except (TypeError, ValueError):
                        porc_retencion = 0.0

                    line.retencion_amount = float_round(line.price_subtotal * porc_retencion, precision_rounding=move.currency_id.rounding)
                    _logger.info("SIT | Línea %s: apply_retencion=TRUE, price_subtotal=%s, retencion_amount calculado=%s",
                                 line.name, line.price_subtotal, line.percepcion_amount)
                else:
                    line.retencion_amount = 0.0
                    _logger.info("SIT | Línea %s: apply_retencion=FALSE, retencion_amount reiniciado a 0", line.name)

                # --- RENTA ---
                if line.renta_percentage > 0:
                    line.renta_amount = round(line.price_subtotal * line.renta_percentage / 100, 2)
                    _logger.info("SIT | Línea %s: renta_percentage=%s%%, price_subtotal=%s, renta_amount calculado=%s",
                                 line.name, line.renta_percentage, line.price_subtotal, line.renta_amount)
                else:
                    line.renta_amount = 0.0
                    _logger.info("SIT | Línea %s: renta_percentage=0, renta_amount reiniciado a 0", line.name)

    # @api.onchange('percepcion_amount', 'retencion_amount', 'renta_amount')
    # def _onchange_line_totals(self):
    #     """
    #     Recalcula los totales de la cabecera cuando cambian los valores
    #     de la línea (aplica percepción, retención o renta) en compras o notas de crédito.
    #     """
    #     for line in self:
    #         move = line.move_id
    #         if (move and move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and move.journal_id
    #                 and (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
    #             _logger.info("SIT | Onchange línea ID=%s para move_id=%s", line.id, move.id)
    #             _logger.info("SIT | Valores línea -> Percepción=%.2f | Retención IVA=%.2f | Renta=%.2f",
    #                          line.percepcion_amount, line.retencion_amount, line.renta_amount)
    #
    #             move._compute_totales_retencion_percepcion()
    #
    #             _logger.info("SIT | Totales move_id=%s recalculados -> Percepción=%.2f | Retención IVA=%.2f | Renta=%.2f",
    #                          move.id, move.percepcion_amount, move.retencion_iva_amount, move.retencion_renta_amount)
