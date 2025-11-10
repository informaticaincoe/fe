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


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    primer_nombre = fields.Char(
        string = 'Primer Nombre',
        required=True,
        store = True
    )

    segundo_nombre = fields.Char(
        string='Segundo Nombre',
        store=True
    )

    primer_apellido = fields.Char(
        string='Primer apellido',
        required=True,
        store=True
    )

    segundo_apellido = fields.Char(
        string='Segundo apellido',
        store=True
    )

    apellido_casada = fields.Char(
        string='Apellido de casada',
        store=True
    )