# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    sequence_id = fields.Many2one(
        'ir.sequence',
        string='Entry Sequence',
        help="Numbering for journal entries of this journal."
    )
    sequence_number_next = fields.Integer(
        string='Next Number',
        help='Next sequence number to be used.',
        compute='_compute_seq_number_next',
        inverse='_inverse_seq_number_next'
    )
    refund_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Credit Note Entry Sequence',
        help="Numbering for credit note entries."
    )
    refund_sequence_number_next = fields.Integer(
        string='Credit Notes Next Number',
        help='Next sequence number for credit notes.',
        compute='_compute_refund_seq_number_next',
        inverse='_inverse_refund_seq_number_next'
    )

    dte_prefix = fields.Char(
        string="Prefijo DTE",
        default="DTE",
        help="Prefijo usado al generar el número de control del DTE."
    )

    # -------------------- CREACIÓN DE SECUENCIAS --------------------

    @api.model
    def _create_sequence(self, vals, refund=False):
        """Crea una secuencia tolerante. Si FE está OFF, usa el flujo estándar de Odoo si existe."""
        _logger.info("📌 _create_sequence llamada con vals=%s refund=%s FE=%s",
                     vals, refund, self.env.company.sit_facturacion)

        if not self.env.company.sit_facturacion:
            # Delegar al comportamiento estándar si tu versión lo espera; si no existe, crea simple.
            code = vals.get('code') or vals.get('name') or 'JOURNAL'
            seq_vals = {
                'name': _('%s Sequence') % (refund and f"{code}: Refund" or code),
                'implementation': 'no_gap',
                'padding': 4,
                'number_increment': 1,
                'use_date_range': True,
            }
            if 'company_id' in vals:
                seq_vals['company_id'] = vals['company_id']
            seq = self.env['ir.sequence'].create(seq_vals)
            _logger.info("✅ Secuencia creada (FE OFF): %s", seq)
            return seq

        # FE ON → tu lógica con prefijos
        code = vals.get('code') or vals.get('name') or 'JOURNAL'
        prefix = self._get_sequence_prefix(code, refund=refund)
        seq_name = refund and f"{code}: Refund" or code
        seq_vals = {
            'name': _('%s Sequence') % seq_name,
            'implementation': 'no_gap',
            'prefix': prefix,
            'padding': 4,
            'number_increment': 1,
            'use_date_range': True,
        }
        if 'company_id' in vals:
            seq_vals['company_id'] = vals['company_id']
        seq = self.env['ir.sequence'].create(seq_vals)
        seq_range = seq._get_current_sequence()
        start = (
                refund and (vals.get('refund_sequence_number_next') or 1)
                or (vals.get('sequence_number_next') or 1)
        )
        seq_range.sudo().number_next = start
        _logger.info("✅ Secuencia creada (FE ON): %s con prefix=%s start=%s", seq, prefix, start)
        return seq

    def create_sequence(self, refund):
        """Versión recordset. Con FE OFF, crea secuencias simples; con FE ON, añade prefijos."""
        self.ensure_one()
        _logger.info("📌 create_sequence llamada en diario=%s refund=%s FE=%s",
                     self.display_name, refund, self.env.company.sit_facturacion)

        if not self.env.company.sit_facturacion:
            seq_vals = {
                'name': _('%s Sequence') % (refund and f"{self.code}: Refund" or self.code),
                'implementation': 'no_gap',
                'padding': 4,
                'number_increment': 1,
                'use_date_range': True,
                'company_id': self.company_id.id,
            }
            seq = self.env['ir.sequence'].create(seq_vals)
            seq._get_current_sequence().sudo().number_next = (
                                                                 self.refund_sequence_number_next if refund else self.sequence_number_next) or 1
            _logger.info("✅ Secuencia recordset creada (FE OFF): %s", seq)
            return seq

        prefix = self._get_sequence_prefix(self.code, refund=refund)
        seq_name = refund and self.code + _(': Refund') or self.code
        seq_vals = {
            'name': _('%s Sequence') % seq_name,
            'implementation': 'no_gap',
            'prefix': prefix,
            'padding': 4,
            'number_increment': 1,
            'use_date_range': True,
            'company_id': self.company_id.id,
        }
        seq = self.env['ir.sequence'].create(seq_vals)
        seq._get_current_sequence().sudo().number_next = (
                                                             self.refund_sequence_number_next if refund else self.sequence_number_next) or 1
        _logger.info("✅ Secuencia recordset creada (FE ON): %s con prefix=%s", seq, prefix)
        return seq

    def create_journal_sequence(self):
        for journal in self:
            _logger.info("📌 Creando secuencias para diario=%s", journal.display_name)
            if not journal.sequence_id:
                journal.sequence_id = journal.create_sequence(refund=False).id
            if not journal.refund_sequence_id:
                journal.refund_sequence_id = journal.create_sequence(refund=True).id

    # -------------------- COMPUTES / INVERSES (NO ROMPER) --------------------

    @api.depends('sequence_id.use_date_range', 'sequence_id.number_next_actual')
    def _compute_seq_number_next(self):
        for journal in self:
            if not journal.sequence_id:
                journal.sequence_number_next = 1
                continue
            sequence = journal.sequence_id._get_current_sequence()
            journal.sequence_number_next = sequence.number_next_actual
            _logger.debug("🔄 _compute_seq_number_next diario=%s next=%s", journal.display_name, journal.sequence_number_next)

    def _inverse_seq_number_next(self):
        for journal in self:
            if journal.sequence_id and journal.sequence_number_next:
                sequence = journal.sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.sequence_number_next
                _logger.debug("✏️ _inverse_seq_number_next diario=%s next=%s",
                              journal.display_name, journal.sequence_number_next)

    @api.depends('refund_sequence_id.use_date_range', 'refund_sequence_id.number_next_actual')
    def _compute_refund_seq_number_next(self):
        for journal in self:
            if not journal.refund_sequence_id:
                journal.refund_sequence_number_next = 1
                continue
            sequence = journal.refund_sequence_id._get_current_sequence()
            journal.refund_sequence_number_next = sequence.number_next_actual
            _logger.debug("🔄 _compute_refund_seq_number_next diario=%s next=%s",
                          journal.display_name, journal.refund_sequence_number_next)

    def _inverse_refund_seq_number_next(self):
        for journal in self:
            if journal.refund_sequence_id and journal.refund_sequence_number_next:
                sequence = journal.refund_sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.refund_sequence_number_next
                _logger.debug("✏️ _inverse_refund_seq_number_next diario=%s next=%s",
                              journal.display_name, journal.refund_sequence_number_next)

    # -------------------- PREFIJO --------------------

    @api.model
    def _get_sequence_prefix(self, code, refund=False):
        """Devuelve un prefix SEGURO. Siempre retorna str. No depende del decorador."""
        # Si FE OFF, devuelve algo simple (sin placeholders) para evitar interpolaciones.
        if not self.env.company.sit_facturacion:
            base = (code or 'JOURNAL').upper()
            pref = ('R' + base + '/') if refund else (base + '/')
            _logger.debug("ℹ️ Prefix generado (FE OFF): %s", pref)
            return pref

        # FE ON: usa dte_prefix si existe; si no, code.
        base = (getattr(self, 'dte_prefix', None) or code or 'DTE').upper()
        if refund:
            base = 'R' + base
        # Puedes mantener %(range_year)s si tu _get_prefix_suffix está tolerante
        pref = base + '/%(range_year)s/'
        _logger.debug("ℹ️ Prefix generado (FE ON): %s", pref)
        return pref

    # -------------------- CREATE / WRITE --------------------

    @api.model_create_multi  # @api.model
    def create(self, vals_list):
        _logger.info("🆕 Creando diario con vals=%s", vals_list)
        # Core: crear diarios
        journals = super(AccountJournal, self.with_context(mail_create_nolog=True)).create(vals_list)

        for vals, journal in zip(vals_list, journals):
            # Si no hay secuencias, créalas (comportamiento consistente ON/OFF)
            if not journal.sequence_id:
                journal.sequence_id = journal.sudo()._create_sequence(vals).id
            if not journal.refund_sequence_id:
                journal.refund_sequence_id = journal.sudo()._create_sequence(vals, refund=True).id

            _logger.info("✅ Diario creado: %s (SEQ=%s, REFUND_SEQ=%s)",
                         journal.display_name, journal.sequence_id, journal.refund_sequence_id)
        return journals

    def write(self, vals):
        _logger.info("✏️ Actualizando diario=%s con vals=%s", self.display_name, vals)
        res = super().write(vals)

        # Mantener prefijos alineados cuando FE ON y se cambie dte_prefix
        if self.env.company.sit_facturacion and 'dte_prefix' in vals:
            for journal in self:
                new_pref = (journal.dte_prefix or journal.code or 'DTE').upper()
                if journal.sequence_id:
                    journal.sequence_id.write({'prefix': new_pref + '/%(range_year)s/'})
                if journal.refund_sequence_id:
                    journal.refund_sequence_id.write({'prefix': 'R' + new_pref + '/%(range_year)s/'})
                    _logger.info("🔄 Prefijos actualizados diario=%s nuevo_pref=%s",
                                 journal.display_name, new_pref)
        return res
