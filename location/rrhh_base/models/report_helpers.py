# -*- coding: utf-8 -*-
from odoo import models, api

class ReportHelpers(models.AbstractModel):
    _name = 'report.rrhh_base.report_helpers'
    _description = 'Funciones auxiliares para reportes de RRHH'

    @api.model
    def horas_a_decimal(self, valor):
        """Convierte 'HH:MM' o float como string a decimal"""
        if not valor:
            return 0.0
        if isinstance(valor, (int, float)):
            return float(valor)
        try:
            if ':' in valor:
                horas, minutos = valor.strip().split(':')
                return int(horas) + int(minutos) / 60
            return float(valor)
        except Exception:
            return 0.0
