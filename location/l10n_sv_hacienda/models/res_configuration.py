from odoo import fields, models, api

import logging
_logger = logging.getLogger(__name__)

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
