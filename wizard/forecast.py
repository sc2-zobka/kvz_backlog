from odoo import models, fields, api, _
from markupsafe import Markup


class ForecastWizard(models.TransientModel):
    _name = "forecast.wizard"
    _description = "Forecast Wizard"

    date = fields.Date("Due Date")

    def action_confirm(self):
        active_id = self._context.get("active_id")
        button = self._context.get("button")
        order_line = self.env["sale.order.line"].browse(active_id)
        order_line.date_deadline = self.date
        activity_type_id = (
            self.env["mail.activity.type"]
            .sudo()
            .search([("is_todo", "=", True)], limit=1)
        )
        model_id = (
            self.env["ir.model"]
            .sudo()
            .search([("model", "=", "sale.order.line")], limit=1)
        )
        # if not button == 'forecast':
        order_line.replanning_count = order_line.replanning_count + 1
        vals = {}
        if activity_type_id:
            # send activity to backlog manager group
            user_ids = self.env.ref("kvz_backlog.group_backlog_manager").users.ids
            user_id = user_ids[0] if user_ids else False

            vals = {
                "user_id": user_id,
                "user_ids": user_ids,
                "activity_type_id": activity_type_id.id,
                "res_id": order_line.id,
                "res_model": "sale.order.line",
                "res_model_id": model_id.id,
                "date_deadline": self.date,
            }
        if button == "forecast":
            order_line.is_hide_forecast = True
            backlog_state_id = self.env["kvz_backlog.stages"].search(
                [("stages_type", "=", "forecast")]
            )
            order_line.backlog_state_id = backlog_state_id.id
            order_line.bklg_state = "forecast"

        elif button == "Unforecast":
            if activity_type_id:
                vals.update(
                    {
                        "res_name": order_line.name + ": Unforecast",
                        "summary": " Unforecast  => ",
                    }
                )
                self.env["mail.activity"].create(vals)

        elif button == "send_invoicing":
            backlog_state_id = self.env["kvz_backlog.stages"].search(
                [("stages_type", "=", "planning")]
            )
            order_line.backlog_state_id = backlog_state_id.id
            order_line.bklg_state = "sent_to_invoicing"
            if activity_type_id:
                vals.update(
                    {
                        "res_name": order_line.name + ": Sent to Invoicing",
                        "summary": " Sent to Invoicing  => ",
                    }
                )
                self.env["mail.activity"].create(vals)

        elif button == "send_provisioning":
            backlog_state_id = self.env["kvz_backlog.stages"].search(
                [("stages_type", "=", "planning")]
            )
            order_line.backlog_state_id = backlog_state_id.id
            order_line.bklg_state = "sent_to_provision"
            if activity_type_id:
                vals.update(
                    {
                        "res_name": order_line.name + ": Sent to Provision",
                        "summary": " Sent to Provision  => ",
                    }
                )
                self.env["mail.activity"].create(vals)
            body = Markup("<b> Sent to Provision by {}.<br/></b>").format(
                self.env.user.name
            )
            order_line.message_post(body=body)
