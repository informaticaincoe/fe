from odoo import fields, models, api

import logging
_logger = logging.getLogger(__name__)

from odoo.exceptions import ValidationError

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils sv hacienda - res_configuration")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class ResConfiguration(models.Model):
    _name = "res.configuration"
    _description = 'Service Configuration Parameters'

    _check_company_auto = True  # Activar la validación automática por empresa (multiempresa)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, help="Company used for the configuration")
    #url = fields.Char(string='URL del Servicio')
    pwd = fields.Char(string='Contraseña')
    value_type = fields.Selection([
        ('text', 'Texto'),
        ('int', 'Número Entero'),
        ('float', 'Decimal'),
        ('bool', 'Booleano'),
        ('json', 'JSON'),
    ], string='Tipo de Valor', default='text')
    value_text = fields.Text(string='Valor')
    description = fields.Text(string='Descripción')
    create_date = fields.Datetime(string='Fecha de creación', readonly=True)
    active = fields.Boolean(default=True)
    clave = fields.Text(string='Clave')

    sit_journal_ids_str = fields.Char(string="Diarios permitidos")
    journal_ids = fields.Many2many(
        "account.journal",
        string="Diarios permitidos",
        compute="_compute_sit_journal_ids",
        inverse="_inverse_sit_journal_ids"
    )

    @api.constrains('journal_ids')
    def _check_max_journals(self):
        """
        Valida que no se seleccionen más de 3 diarios permitidos.

        Esta restricción se aplica cada vez que se modifican los diarios (`journal_ids`)
        en la configuración de la empresa.

        Excepción:
            - Si se seleccionan más de 3 diarios, se lanza un ValidationError
              con el mensaje "Debe seleccionar hasta 3 diarios como máximo."
        """
        for record in self:
            valor = config_utils.get_config_value(self.env, 'cant_diarios', record.company_id.id) if config_utils else 3
            cantidad_diarios = int(valor or 3)

            if len(record.journal_ids) > cantidad_diarios:
                raise ValidationError("Debe seleccionar hasta 3 diarios como máximo.")

    def _compute_sit_journal_ids(self):
        """
        Computa los diarios seleccionados a partir del campo `sit_journal_ids_str`.

        `sit_journal_ids_str` almacena los IDs de los diarios como una cadena
        separada por comas. Este método convierte esa cadena en registros
        de `account.journal` y los asigna al campo `journal_ids` (campo Many2many
        computado) para su uso en la interfaz.

        Ejemplo:
            sit_journal_ids_str = "1,3,5"  ->  journal_ids = [journal_1, journal_3, journal_5]
        """
        for rec in self:
            if rec.sit_journal_ids_str:
                ids = [int(i) for i in rec.sit_journal_ids_str.split(",") if i]
                rec.journal_ids = self.env["account.journal"].browse(ids)
            else:
                rec.journal_ids = False

    def _inverse_sit_journal_ids(self):
        """
        Guarda los diarios seleccionados en `sit_journal_ids_str`.

        Este método es el inverso del campo `journal_ids`. Convierte los registros
        seleccionados en una cadena de IDs separados por comas, que es el valor
        realmente almacenado en la base de datos (`sit_journal_ids_str`).

        Ejemplo:
            journal_ids = [journal_1, journal_3, journal_5]  ->  sit_journal_ids_str = "1,3,5"
        """
        for rec in self:
            if rec.journal_ids:
                rec.sit_journal_ids_str = ",".join(str(j.id) for j in rec.journal_ids)
            else:
                rec.sit_journal_ids_str = ""

    def action_open_configuration(self):
        current_company = self.env.company
        allowed_companies = self.env.context.get("allowed_company_ids", [current_company.id])  # todas las empresas accesibles al usuario

        _logger.info(">>> Usuario: %s", self.env.user.name)
        _logger.info(">>> Compañía activa en UI: %s (ID: %s)", current_company.name, current_company.id)
        _logger.info(">>> Compañías seleccionadas en el switch (allowed_companies): %s", allowed_companies)

        # Buscar registros visibles según multiempresa
        records_allowed = self.sudo().with_context(check_company=False).search(
            [('company_id', 'in', allowed_companies)]
        )

        if current_company.id not in allowed_companies:
            raise UserError(
                "La compañía activa es '%s', pero los registros que quieres actualizar "
                "pertenecen a '%s'.\nPor favor, cambia la compañía activa arriba a la derecha."
                % (current_company.name, ", ".join(r.company_id.name for r in records_allowed))
            )

        action = {
            'type': 'ir.actions.act_window',
            'name': 'Configuraciones Empresa',
            'res_model': 'res.configuration',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('company_id', 'in', allowed_companies)],
            'context': {
                'check_company': True,  # respeta multiempresa
                'allowed_company_ids': allowed_companies,  # dinámico según el switch
                'default_company_id': current_company.id,  # preselecciona en formularios
                'search_default_company_id': current_company.id,  # aplica filtro inicial
            },
        }

        _logger.info(">>> Acción devuelta: %s", action)
        return action
