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


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_send_payslip_email_batch(self):
        # Permite seleccionar varios lotes a la vez
        slips = self.mapped('slip_ids')
        if not slips:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Boletas de pago', 'message': 'El lote no contiene boletas.',
                           'type': 'warning', 'sticky': True}
            }

        sent = 0
        failed = []

        for slip in slips:
            try:
                res = slip.action_send_payslip_email()
                # Tu método individual devuelve un display_notification; si es warning/danger lo tomamos como fallo
                if isinstance(res, dict) and res.get('tag') == 'display_notification':
                    p = (res.get('params') or {})
                    level = p.get('type')
                    if level in ('warning', 'danger'):
                        failed.append(f"• {slip.name}: {p.get('message') or 'falló el envío'}")
                        continue
                # Si no hay excepción y no fue warning/danger, lo contamos como enviado
                sent += 1
            except Exception as e:
                failed.append(f"• {slip.name}: {str(e)}")

        title = "Envío de boletas por lote"
        if failed:
            msg = f"Enviadas **{sent}**. Fallaron **{len(failed)}**:\n\n" + "\n".join(failed[:5])
            if len(failed) > 5:
                msg += f"\n... y {len(failed) - 5} más."
            level, sticky = 'warning', True
        else:
            msg, level, sticky = f"Se enviaron {sent} boletas con éxito.", 'success', False

        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': title, 'message': msg, 'type': level, 'sticky': sticky}
        }
