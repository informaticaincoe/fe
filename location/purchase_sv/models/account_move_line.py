from odoo import api, fields, models, _

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
        """Calcula automáticamente el 1% del subtotal si apply_percepcion está activo."""
        for line in self:
            # Verificamos si es una factura de compra
            tipo_doc = line.move_id.journal_id.sit_tipo_documento if line.move_id.journal_id else None
            if line.move_id.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and (not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE):
                #---- PERCEPCION 1%
                if line.apply_percepcion:
                    line.percepcion_amount = round(line.price_subtotal * 0.01, 2)
                    _logger.info(
                        "SIT | Línea %s: apply_percepcion=TRUE, price_subtotal=%s, percepcion_amount calculado=%s",
                        line.name, line.price_subtotal, line.percepcion_amount
                    )
                else:
                    line.percepcion_amount = 0.0
                    _logger.info(
                        "SIT | Línea %s: apply_percepcion=FALSE, percepcion_amount reiniciado a 0",
                        line.name
                    )

                # ---- RETENCION 1%
                if line.apply_retencion:
                    line.retencion_amount = round(line.price_subtotal * 0.01, 2)
                    _logger.info(
                        "SIT | Línea %s: apply_retencion=TRUE, price_subtotal=%s, retencion_amount calculado=%s",
                        line.name, line.price_subtotal, line.percepcion_amount
                    )
                else:
                    line.retencion_amount = 0.0
                    _logger.info(
                        "SIT | Línea %s: apply_retencion=FALSE, retencion_amount reiniciado a 0",
                        line.name
                    )

                # --- RENTA ---
                if line.renta_percentage > 0:
                    line.renta_amount = round(line.price_subtotal * line.renta_percentage / 100, 2)
                    _logger.info(
                        "SIT | Línea %s: renta_percentage=%s%%, price_subtotal=%s, renta_amount calculado=%s",
                        line.name, line.renta_percentage, line.price_subtotal, line.renta_amount
                    )
                else:
                    line.renta_amount = 0.0
                    _logger.info(
                        "SIT | Línea %s: renta_percentage=0, renta_amount reiniciado a 0", line.name
                    )
        # Luego de calcular cada línea, actualizamos los totales del move
        # self.mapped('move_id')._update_totales_move()
        # Recalcular totales en la cabecera automáticamente
        self._trigger_update_move_totals()

    @api.onchange('percepcion_amount', 'retencion_amount', 'renta_amount')
    def _onchange_line_totals(self):
        """
        Recalcula los totales de la cabecera cuando cambian los valores
        de la línea (aplica percepción, retención o renta) en compras o notas de crédito.
        """
        for line in self:
            move = line.move_id
            if move and move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and \
                    (
                            not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE):
                _logger.info("SIT | Onchange línea ID=%s para move_id=%s", line.id, move.id)
                _logger.info(
                    "SIT | Valores línea -> Percepción=%.2f | Retención IVA=%.2f | Renta=%.2f",
                    line.percepcion_amount, line.retencion_amount, line.renta_amount
                )

                move._compute_totales_retencion_percepcion()

                _logger.info(
                    "SIT | Totales move_id=%s recalculados -> Percepción=%.2f | Retención IVA=%.2f | Renta=%.2f",
                    move.id, move.percepcion_amount, move.retencion_iva_amount, move.retencion_renta_amount
                )

    def _trigger_update_move_totals(self):
        """Llama a la función de la cabecera solo para compras y notas de crédito."""
        moves_to_update = self.mapped('move_id').filtered(
            lambda m: m.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and
                      (not m.journal_id.sit_tipo_documento or m.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)
        )
        for move in moves_to_update:
            move._update_totales_move()

    # @api.onchange('move_id')
    # def _onchange_move_id_update_totales(self):
    #     """
    #     Este método se ejecuta cuando cambia el movimiento (move_id)
    #     relacionado con la línea. Se utiliza para recalcular los totales
    #     de percepción, retención IVA y renta en el encabezado (account.move).
    #
    #     Aplica únicamente a documentos de compra y sus notas:
    #     - Facturas de compra: move_type = 'in_invoice'
    #     - Notas de crédito de compra: move_type = 'in_refund'
    #     """
    #     for line in self:
    #         move = line.move_id
    #         if not move:
    #             continue
    #         if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and
    #                 move.journal_id and (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
    #             _logger.info("SIT | _onchange_move_id_update_totales → Recalculando totales para move_id=%s", move.id)
    #             move._update_totales_move()

    def unlink(self):
        """
        Sobrescribe la eliminación de líneas (unlink) para recalcular
        automáticamente los totales en el encabezado del documento.

        Solo aplica para documentos de compra y notas de crédito.
        Al eliminar líneas con percepción o retención, el total en el
        account.move se actualiza correctamente (evita valores residuales).
        """
        moves_to_update = self.mapped('move_id').filtered(
            lambda m: m.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and
                      m.journal_id and (not m.journal_id.sit_tipo_documento or m.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)
        )

        _logger.info("SIT | unlink → Eliminando líneas %s asociadas a moves %s (solo compras y notas de crédito).", self.ids, moves_to_update.ids)

        res = super().unlink()

        # Recalcular totales del move después de la eliminación
        for move in moves_to_update:
            _logger.info("SIT | unlink → Recalculando totales para move_id=%s tras eliminar líneas", move.id)
            move._update_totales_move()
        return res
