
from odoo import models, fields, api, _
from markupsafe import Markup

class ReplanWizard(models.TransientModel):
	_name = 'replan.wizard'
	_description = 'Replan Wizard'

	date = fields.Date('Replan Date')

	def action_confirm(self):
		active_id = self._context.get('active_id')
		order_line = self.env['sale.order.line'].browse(active_id)
		order_line.date_deadline = self.date
		order_line.replanning_count = order_line.replanning_count + 1
		body = Markup("<b>Date :- {} <br/>The replanning count will be changed by {}.<br/>This count number {}.</b>").format(self.date, self.env.user.name, order_line.replanning_count)
		order_line.message_post(body=body)