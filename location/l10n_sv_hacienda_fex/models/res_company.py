from odoo import fields, models, api, _
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    account_exportacion_id = fields.Many2one(
        'account.account',
        string='Cuenta Fact. Exportación',
        help='Cuenta contable predeterminada para los asientos contables de seguro y flete para facturas de exportación'
    )
