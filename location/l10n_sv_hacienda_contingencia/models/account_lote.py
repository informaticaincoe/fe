##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
import base64
import pyqrcode
import qrcode
import os
from PIL import Image
import io

import logging
import sys
import traceback

_logger = logging.getLogger(__name__)

class sit_account_lote(models.Model):
    _name = 'account.lote'
    _description = 'Lote de Facturas'

    fechaHoraTransmision = fields.Datetime(
        copy=False,
        string="Fecha/Hora de Transmisión",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    # --------CAMPOS LOTE --------------------

    hacienda_estado_lote = fields.Char(
        copy=False,
        string="Estado Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_idEnvio_lote = fields.Char(
        copy=False,
        string="Id de Envio Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_fhProcesamiento_lote = fields.Datetime(
        copy=False,
        string="Fecha de Procesamiento de Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_codigoLote_lote = fields.Char(
        copy=False,
        string="Codigo de Lote",
        readonly=True,
    )
    hacienda_codigoMsg_lote = fields.Char(
        copy=False,
        string="Codigo de Mensaje",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_descripcionMsg_lote = fields.Char(
        copy=False,
        string="Descripción de Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Nuevo'),
            ('posted', 'Validado'),
            ('posted_lote', 'Lote Validado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado',
        required=True,
        readonly=True,
        # copy=False,
        tracking=True,
        default='draft',
    )

    error_log = fields.Text(string="Error técnico Contingencia", readonly=True)

    sit_contingencia = fields.Many2one('account.contingencia1', string="Contingencia asociada al lote")

    move_ids = fields.One2many(
        comodel_name='account.move',
        inverse_name='sit_lote_contingencia',
        string='Facturas Relacionadas'
    )

    lote_recibido_mh = fields.Boolean(string="Lote recibido por MH", copy=False)
    lote_activo = fields.Boolean(string="Contingencia Activa", copy=False, default=True)

    sit_json_respuesta = fields.Text("Json de Respuesta", default="")

    name = fields.Char(
        readonly=True,  # Solo lectura
        copy=False,
        string="Identificacion del lote",
    )

    def action_ver_facturas(self):
        return {
            'name': 'Facturas del Lote',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('sit_lote_contingencia', '=', self.id)],
            'context': dict(self.env.context),
            'views': [(self.env.ref('l10n_sv_hacienda_contingencia.view_account_move_lote_list').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
        }
