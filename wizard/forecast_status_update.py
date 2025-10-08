from odoo import models, fields, _
from odoo.exceptions import UserError


class ForecastStatusUpdate(models.TransientModel):
    _name = "forecast.status.update"
    _description = "Forecast Status Update"

    def validate(self):
        active_ids = self._context.get('active_ids')
        forecast_id = self.env['backlog.stages'].search([
            ('stages_type', '=', 'forecast')
        ], limit=1)

        if active_ids:
            order_line = self.env['sale.order.line'].browse(active_ids).filtered(lambda l: not l.backlog_state_id)
            if order_line:
                for l in order_line:
                    if not l.backlog_state_id:
                        l.backlog_state_id = forecast_id.id
                return {'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'type': 'success',
                            'title': _("Status"),
                            'message': "success update all record...",
                            'next': {
                                'type': 'ir.actions.act_window_close'
                            },
                        }}
            else:
                return {'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'type': 'success',
                            'title': _("Status"),
                            'message': "Not found any record...",
                            'next': {
                                'type': 'ir.actions.act_window_close'
                            },
                        }}

