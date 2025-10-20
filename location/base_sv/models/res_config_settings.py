# models/res_config_settings.py
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    email_from_quedan = fields.Char(related='company_id.email_from_quedan', readonly=False)
    smtp_quedan_id = fields.Many2one(related='company_id.smtp_quedan_id', readonly=False)

    email_from_invoice = fields.Char(related='company_id.email_from_invoice', readonly=False)
    smtp_invoice_id = fields.Many2one(related='company_id.smtp_invoice_id', readonly=False)

    email_from_payslip = fields.Char(related='company_id.email_from_payslip', readonly=False)
    smtp_payslip_id = fields.Many2one(related='company_id.smtp_payslip_id', readonly=False)
