
from odoo import models, fields, api, _

class ReplanWizard(models.TransientModel):
	_name = 'replan.wizard'
	_description = 'Replan Wizard'

	date = fields.Date('Replan Date')

	def action_confirm(self):
		active_id = self._context.get('active_id')
		order_line = self.env['sale.order.line'].browse(active_id)
		order_line.date_deadline = self.date
		order_line.replanning_count = order_line.replanning_count + 1
		body = f"<b>Date :- {self.date} <br/>The replanning count will be changed by {self.env.user.name}.<br/>This count number {order_line.replanning_count}.</b>"
		order_line.message_post(body=body)