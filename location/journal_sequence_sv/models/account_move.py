# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    name = fields.Char(string='Number', required=True, readonly=False, copy=False, default='/')


    def _get_sequence(self):
        """Resuelve la secuencia a usar respetando el core si FE está OFF."""
        self.ensure_one()
        if not self.env.company.sit_facturacion:
            return super()._get_sequence()

        journal = self.journal_id
        # Si es normal o no hay refund_sequence -> principal
        if self.move_type in ('entry', 'out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') or not journal.refund_sequence:
            return journal.sequence_id
        # Si es NC y existe refund_sequence -> refund
        if journal.refund_sequence_id:
            return journal.refund_sequence_id
        return journal.sequence_id  # fallback seguro


    @api.model
    def _get_standard_sequence(self):
        """Devuelve la secuencia estándar (no-DTE) para el diario."""
        self.ensure_one()
        if not self.env.company.sit_facturacion:
            # respetar core; si no existe en tu versión, puedes retornar self.journal_id.sequence_id
            try:
                return super()._get_standard_sequence()
            except AttributeError:
                pass
        journal = self.journal_id
        if self.move_type in ('entry', 'out_invoice', 'in_invoice', 'out_receipt',
                              'in_receipt') or not journal.refund_sequence:
            return journal.sequence_id
        return journal.refund_sequence_id or journal.sequence_id


    def _post(self, soft=True):

        if not self.env.company.sit_facturacion:
            return super()._post(soft=soft)

        # 1) Solo asigno la secuencia estándar para diarios NO sale
        non_sales = self.filtered(lambda m: m.journal_id.type != 'sale')
        for move in non_sales:
            _logger.info("Revisando move %s con diario %s (%s)", move.id, move.journal_id.name, move.journal_id.type)

            if not (move.company_id and move.company_id.sit_facturacion) or not move.journal_id.sit_tipo_documento:
                _logger.warning("Move %s omitido: sin company_id.sit_facturacion y sin tipo de documento en el diario %s", move.id, move.journal_id.id)
                continue

            _logger.info("Move %s pasa validaciones, continúa con el flujo", move.id)
            if move.name == '/':
                journal = move.journal_id
                if not journal:
                    raise UserError(_('Debe seleccionar un Diario antes de confirmar el documento.'))
                sequence = move._get_standard_sequence()
                if not sequence:
                    raise UserError(
                        _('Por favor defina una secuencia para el Diario "%s".') %
                        journal.display_name
                    )
                # Asigno el siguiente número de la secuencia normal
                move.name = sequence.with_context(
                    ir_sequence_date=move.date
                ).next_by_id()

        # 2) Delego al super(), de modo que:
        #    - los diarios sale pasen a tu flujo DTE (con “DTE-…”)
        #    - todo lo demás continúe con la lógica de Odoo
        return super(AccountMove, self)._post(soft=soft)

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        """Resetea nombre y deja que el core compute lo demás; si FE OFF, no toques nada extra."""
        _logger.info("SIT-ONCHANGE: Iniciando onchange_journal_id para move_id=%s, journal_id=%s", self.id,
                     self.journal_id.id if self.journal_id else None)

        # Llama primero al core por si tiene lógica propia
        try:
            super(AccountMove, self).onchange_journal_id()
            _logger.info("SIT-ONCHANGE: super().onchange_journal_id ejecutado, name=%s", self.name)
        except AttributeError:
            _logger.warning("SIT-ONCHANGE: super().onchange_journal_id no existe en esta versión")

        # Si quieres forzar reset del nombre cuando FE ON:
        if self.env.company.sit_facturacion:
            _logger.info("SIT-ONCHANGE: FE activado, reseteando name a '/' (antes name=%s)", self.name)
            self.name = '/'
            try:
                _logger.info("SIT-ONCHANGE: llamando a _compute_name()")
                self._compute_name()
                _logger.info("SIT-ONCHANGE: _compute_name() ejecutado, name=%s", self.name)
            except Exception as e:
                _logger.error("SIT-ONCHANGE: Error ejecutando _compute_name(): %s", e)

    def _constrains_date_sequence(self):
        return

    def write(self, vals):
        # para evitar que pongan name = False
        if 'name' in vals and vals['name'] is False:
            vals['name'] = '/'
        return super().write(vals)