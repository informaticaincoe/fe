# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

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
            return self.env['ir.sequence'].create(seq_vals)

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
        return seq

    def create_sequence(self, refund):
        """Versión recordset. Con FE OFF, crea secuencias simples; con FE ON, añade prefijos."""
        self.ensure_one()
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
            seq._get_current_sequence().sudo().number_next = (self.refund_sequence_number_next if refund else self.sequence_number_next) or 1
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
        seq._get_current_sequence().sudo().number_next = (self.refund_sequence_number_next if refund else self.sequence_number_next) or 1
        return seq

    def create_journal_sequence(self):
        for journal in self:
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

    def _inverse_seq_number_next(self):
        for journal in self:
            if journal.sequence_id and journal.sequence_number_next:
                sequence = journal.sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.sequence_number_next

    @api.depends('refund_sequence_id.use_date_range', 'refund_sequence_id.number_next_actual')
    def _compute_refund_seq_number_next(self):
        for journal in self:
            if not journal.refund_sequence_id:
                journal.refund_sequence_number_next = 1
                continue
            sequence = journal.refund_sequence_id._get_current_sequence()
            journal.refund_sequence_number_next = sequence.number_next_actual

    def _inverse_refund_seq_number_next(self):
        for journal in self:
            if journal.refund_sequence_id and journal.refund_sequence_number_next:
                sequence = journal.refund_sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.refund_sequence_number_next

    # -------------------- PREFIJO --------------------

    @api.model
    def _get_sequence_prefix(self, code, refund=False):
        """Devuelve un prefix SEGURO. Siempre retorna str. No depende del decorador."""
        # Si FE OFF, devuelve algo simple (sin placeholders) para evitar interpolaciones.
        if not self.env.company.sit_facturacion:
            base = (code or 'JOURNAL').upper()
            return ('R' + base + '/') if refund else (base + '/')

        # FE ON: usa dte_prefix si existe; si no, code.
        base = (getattr(self, 'dte_prefix', None) or code or 'DTE').upper()
        if refund:
            base = 'R' + base
        # Puedes mantener %(range_year)s si tu _get_prefix_suffix está tolerante
        return base + '/%(range_year)s/'

    # -------------------- CREATE / WRITE --------------------

    @api.model
    def create(self, vals):
        # Core: crear diario
        journal = super(AccountJournal, self.with_context(mail_create_nolog=True)).create(vals)

        # Si no hay secuencias, créalas (comportamiento consistente ON/OFF)
        if not journal.sequence_id:
            journal.sequence_id = journal.sudo()._create_sequence(vals).id
        if not journal.refund_sequence_id:
            journal.refund_sequence_id = journal.sudo()._create_sequence(vals, refund=True).id

        return journal

    def write(self, vals):
        res = super().write(vals)

        # Mantener prefijos alineados cuando FE ON y se cambie dte_prefix
        if self.env.company.sit_facturacion and 'dte_prefix' in vals:
            for journal in self:
                new_pref = (journal.dte_prefix or journal.code or 'DTE').upper()
                if journal.sequence_id:
                    journal.sequence_id.write({'prefix': new_pref + '/%(range_year)s/'})
                if journal.refund_sequence_id:
                    journal.refund_sequence_id.write({'prefix': 'R' + new_pref + '/%(range_year)s/'})
        return res
