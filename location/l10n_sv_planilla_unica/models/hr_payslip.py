from odoo import _, api, fields, models
import logging
from lxml import etree
from datetime import date
from email.utils import parseaddr, formataddr
import base64, re
try:
    import unicodedata
except Exception:
    unicodedata = None

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    primer_nombre = fields.Char(
        string='Primer nombre',
        related='employee_id.primer_nombre',
        readonly=True,
    )

    sgundo_nombre = fields.Char(
        string='Segundo nombre',
        related='employee_id.segundo_nombre',
        readonly=True,
    )

    primer_apellido = fields.Char(
        string='Primer apellido',
        related='employee_id.primer_apellido',
        readonly=True,
    )

    sgundo_apellido = fields.Char(
        string='Segundo apellido',
        related='employee_id.segundo_apellido',
        readonly=True,
    )
