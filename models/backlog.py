from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date
from lxml import etree
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class BacklogStages(models.Model):
    _name = "backlog.stages"
    _description = "Back Log Stages"

    sequence = fields.Integer(default=50)
    name = fields.Char(required=True, translate=True)
    stages_type = fields.Selection(
        [
            ("forecast", "Forecast"),
            ("planning", " Planning"),
            ("provisioned", "Provisioned"),
            ("invoiced", "Invoiced"),
        ],
        default="forecast",
        string="Stages",
    )

    @api.constrains("stages_type")
    def check_stages_type(self):
        stage_id = self.search(
            [("stages_type", "=", self.stages_type), ("id", "!=", self.id)]
        )
        stages_dict = {
            "forecast": "Forecast",
            "planning": "Planning",
            "provisioned": "Provisioned",
            "invoiced": "Invoiced",
        }
        if stage_id:
            raise UserError(
                _("Stage ' %s ' Already Exist !!!")
                % (stages_dict.get(self.stages_type))
            )


class BacklogManage(models.Model):
    _name = "backlog.manage"
    _description = "Back Log Manage"


class MailActivityType(models.Model):
    _inherit = "mail.activity.type"

    is_todo = fields.Boolean("Is To Do")


class kvz_backlog_lines(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "mail.activity.mixin", "mail.thread", "utm.mixin"]

    def get_currency_id(self):
        convert_currency_id = self.env["res.currency"].search(
            [("name", "=", "CLP")], limit=1
        )
        return convert_currency_id.id if convert_currency_id else False

    project_manager = fields.Many2one(
        "res.users",
        string="Project Manager",
        required=False,
        related="project_id.user_id",
        # readonly=True,copy=False,states={'draft': [('readonly', False)]},
        check_company=True,
    )
    current_user_id = fields.Boolean(
        string="Current Users", compute="compute_get_users"
    )
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        related="order_partner_id.country_id",
        readonly=True,
    )
    service_id = fields.Many2one(
        "account.analytic.account",
        string="Service",
        ondelete="set null",
        check_company=True,
    )
    project_id = fields.Many2one(
        related="order_id.project_id", store=True, string="Project", check_company=True
    )
    backlog_state_id = fields.Many2one(
        "backlog.stages",
        string="Stage",
        required=False,
        readonly=False,
        copy=False,
        tracking=True,
        group_expand="_read_group_stage_ids",
    )
    forecast_date = fields.Date(
        string="Due Date",
        required=False,
        index=True,
        readonly=False,
        # states={'draft': [('readonly', False),('required', False)]},
        copy=False,
        tracking=True,
    )
    # Currency from sale_order_line currency_id
    # Amount in currency from sale_order_line price_total
    clp_price_total = fields.Monetary(
        string="Price total CLP",
        compute="compute_clp_currency",
        store=True,
        help="Monto en CLP con IVA.",
    )
    clp_price_subtotal = fields.Monetary(
        string="Price Subtotal CLP",
        compute="compute_clp_currency",
        store=True,
        help="Monto en CLP sin IVA.",
    )

    state = fields.Selection(
        related="order_id.state", store=True, string="Order Status"
    )
    is_hide_forecast = fields.Boolean("Is Hide Forecast")
    stages_type = fields.Selection(related="backlog_state_id.stages_type")

    @api.model
    def _get_bklg_state_list(self):
        base_list = [
            ("forecast", "Forecast"),
            ("planning", " Planning"),
            ("high_risk", "High Risk"),
            ("pending_risk", "Pending Risk"),
            ("sent_to_provision", "Sent to Provision"),
            ("sent_to_invoicing", "Sent to Invoicing"),
            ("provisioned", "Provisioned"),
            ("invoiced", "Invoiced"),
            ("frozen", "Frozen"),
        ]
        if self.env.user.has_group(
            "kvz_backlog.group_project_manager"
        ) and not self.env.user.has_group("kvz_backlog.group_backlog_users"):
            base_list.remove(("forecast", "Forecast"))
            base_list.remove(("sent_to_provision", "Sent to Provision"))
            base_list.remove(("provisioned", "Provisioned"))
            base_list.remove(("invoiced", "Invoiced"))
            base_list.remove(("frozen", "Frozen"))
        return base_list

    bklg_state = fields.Selection(
        string="State", selection="_get_bklg_state_list", copy=False, default=False
    )

    cpl_currency_id = fields.Many2one(
        "res.currency", string="Currency", default=get_currency_id
    )
    income_recognition_date = fields.Date("Recognition Date")
    replanning_count = fields.Integer("Replanning Count", default=0, readonly=True)
    amount_us = fields.Float(
        string="Subtotal USD", compute="_compute_amount_us", store=True
    )
    user_id = fields.Many2one(
        related="order_id.user_id", store=True, string="Salesperson"
    )
    business_line = fields.Char("Business Line")
    date_deadline = fields.Date("Deadline Date", copy=False)
    is_required_date = fields.Boolean("Is Required Date")

    def compute_get_users(self):
        for rec in self:
            if not rec.bklg_state:
                if rec.project_manager and rec.project_manager.id == self.env.uid:
                    rec.current_user_id = True
                elif rec.stages_type == "planning":
                    rec.current_user_id = False
                else:
                    rec.current_user_id = False
            else:
                rec.current_user_id = True

    @api.onchange("bklg_state")
    def onchage_on_bklg_state(self):
        for rec in self:
            if rec._context.get("manualy_change"):
                if self.order_id.project_line_ids:
                    manager_ids = self.order_id.project_line_ids.mapped("user_id.id")
                    if (
                        self.env.user.id not in manager_ids
                        and not self.project_manager.id == self.env.user.id
                    ):
                        raise UserError(
                            _(
                                "You are not allowed to make changes, please contact the Project Manager!"
                            )
                        )
                rec.replanning_count += 1
                # if rec.bklg_state == "sent_to_provision":
                # 	return {
                # 		'name': "Send To Provision",
                # 		'type': 'ir.actions.act_window',
                # 		'view_type': 'form',
                # 		'view_mode': 'form',
                # 		'res_model': 'forecast.wizard',
                # 		'target': 'new',
                # 		'context':{'button':'send_invoicing'}
                # 	}
                # elif rec.bklg_state == "sent_to_invoicing":
                # 	return {
                # 		'name': "Send To Invoicing",
                # 		'type': 'ir.actions.act_window',
                # 		'view_type': 'form',
                # 		'view_mode': 'form',
                # 		'res_model': 'forecast.wizard',
                # 		'target': 'new',
                # 		'context':{'button':'send_invoicing'}
                # 	}
                if rec.bklg_state == "provisioned":
                    rec.action_provision()
                elif rec.bklg_state == "invoiced":
                    rec.action_invoice()
                else:
                    rec.is_required_date = True
                    rec.date_deadline = False
            else:
                rec.is_required_date = False

    def write(self, vals):
        if vals.get("date_deadline"):
            if self.is_required_date or vals.get("is_required_date"):
                vals.update({"is_required_date": False})
            body = f"<b>Date Deadline :- {vals.get('date_deadline')} <br/> Re-Change Deadline Date by {self.env.user.name}.<br/></b>"
            self.message_post(body=body)
        if vals.get("bklg_state") and vals.get("date_deadline"):
            new_date = datetime.strptime(vals.get("date_deadline"), "%Y-%m-%d").date()
            if (
                new_date != self.date_deadline
                or vals.get("bklg_state") != self.bklg_state
            ):
                vals.update({"replanning_count": self.replanning_count + 1})
        if (
            vals.get("bklg_state")
            and vals.get("bklg_state") == "sent_to_invoicing"
            and vals.get("bklg_state") != self.bklg_state
        ):
            if not vals.get("date_deadline"):
                raise UserError(_("Please set date deadline first!"))
            activity_type_id = (
                self.env["mail.activity.type"]
                .sudo()
                .search([("is_todo", "=", True)], limit=1)
            )
            date_deadline = datetime.strptime(
                vals.get("date_deadline"), "%Y-%m-%d"
            ).date()
            model_id = (
                self.env["ir.model"]
                .sudo()
                .search([("model", "=", "sale.order.line")], limit=1)
            )

            # send activity to backlog manager group
            user_ids = self.env.ref("kvz_backlog.group_backlog_manager").users.ids
            user_id = user_ids[0] if user_ids else False

            if activity_type_id and user_id:
                activity_vals = {
                    "user_id": user_id,
                    "user_ids": user_ids,
                    "activity_type_id": activity_type_id.id,
                    "res_id": self.id,
                    "res_model": "sale.order.line",
                    "res_model_id": model_id.id,
                    "date_deadline": date_deadline,
                    "res_name": self.name + ": Sent to Invoicing",
                    "summary": " Sent to Invoicing  => ",
                }
                self.env["mail.activity"].create(activity_vals)
            self.message_post(
                body=f"<b> Sent to Invoicing by {self.env.user.name}.<br/></b>"
            )
        return super(kvz_backlog_lines, self).write(vals)

    @api.constrains("bklg_state", "backlog_state_id", "state")
    def _check_validate_status(self):
        for rec in self:
            user = self.env.user
            if (
                not user.has_group("kvz_backlog.group_head_of_sales")
                and not user.has_group("kvz_backlog.group_business_owner")
                and rec.project_manager.id != user.id
                and not user.has_group("kvz_backlog.group_project_manager")
                and rec.order_id.user_id.id != user.id
            ):
                if rec.state in ["draft", "sent"] and (
                    rec.backlog_state_id or rec.bklg_state
                ):
                    raise ValidationError(
                        """This Backlog Kuvasz only Business Owner or Head of Sale can changes \n Becuase this order status is {status} and 'Estado backlog is blank!!""".format(
                            status=rec.state
                        )
                    )

    def action_unforecast(self):
        for rec in self:
            rec.update(
                {
                    "date_deadline": False,
                    "forecast_date": False,
                    "bklg_state": False,
                    "stages_type": False,
                    "backlog_state_id": False,
                }
            )
            body = f"<b>Date  :- {date.today()} <br/> has been made clear all(using Unforecast button) by {self.env.user.name}.<br/></b>"
            rec.message_post(body=body)
        # refresh the current view
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return self.env["backlog.stages"].search([])

    # Compute on Nivel Riesgo
    @api.depends(
        "price_total",
        "price_subtotal",
        "currency_id",
        "forecast_date",
        "create_date",
        "order_id.company_id",
        "invoice_status",
        "bklg_state",
    )
    def compute_clp_currency(self):
        clp_currency = self.env.ref("base.CLP", raise_if_not_found=False)

        if not clp_currency:
            for rec in self:
                rec.clp_price_total = 0.0
                rec.clp_price_subtotal = 0.0
            return

        for rec in self:
            # Skip computation if already invoiced or provisioned
            if rec.invoice_status == "invoiced" or rec.bklg_state == "provisioned":
                continue

            # If currency is already CLP, no conversion needed
            if rec.currency_id == clp_currency:
                rec.clp_price_total = rec.price_total
                rec.clp_price_subtotal = rec.price_subtotal
                continue

            company = rec.order_id.company_id or self.env.company
            rate_date = (
                rec.forecast_date or rec.create_date or fields.Date.context_today(rec)
            )

            rec.clp_price_total = rec.currency_id._convert(
                rec.price_total,
                clp_currency,
                company,
                rate_date,
            )
            rec.clp_price_subtotal = rec.currency_id._convert(
                rec.price_subtotal,
                clp_currency,
                company,
                rate_date,
            )

    @api.depends(
        "price_total",
        "price_subtotal",
        "currency_id",
        "forecast_date",
        "create_date",
        "order_id.company_id",
        "bklg_state",
    )
    def _compute_amount_us(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        clp = self.env.ref("base.CLP", raise_if_not_found=False)

        if not usd:
            for rec in self:
                rec.amount_us = 0.0
            return

        for rec in self:
            # Skip computation if provisioned
            if rec.bklg_state == "provisioned":
                continue

            # If currency is already USD, no conversion needed
            if rec.currency_id == usd:
                rec.amount_us = rec.price_subtotal
                continue

            company = rec.order_id.company_id or self.env.company
            rate_date = (
                rec.forecast_date or rec.create_date or fields.Date.context_today(rec)
            )

            # Special handling for CLP → USD using inverse rate
            if rec.currency_id == clp and clp:
                # Use round=False to get exact conversion, then round manually if needed
                rec.amount_us = rec.currency_id._convert(
                    rec.price_subtotal,
                    usd,
                    company,
                    rate_date,
                    round=False,  # Odoo 17 parameter for precise conversion
                )
            else:
                
                rec.amount_us = rec.currency_id._convert(
                    rec.price_subtotal,
                    usd,
                    company,
                    rate_date,
                )

    def action_invoice(self):
        stage_invoiced = self.env["backlog.stages"].search(
            [("stages_type", "=", "invoiced")], limit=1
        )
        for rec in self:
            rec.sudo().write(
                {
                    "income_recognition_date": fields.Date.context_today(self),
                    "backlog_state_id": stage_invoiced.id if stage_invoiced else False,
                    "bklg_state": "invoiced",
                }
            )

    def action_provision(self):
        """Mark lines as provisioned and freeze currency amounts"""
        stage_provisioned = self.env["backlog.stages"].search(
            [("stages_type", "=", "provisioned")], limit=1
        )

        if not stage_provisioned:
            _logger.warning("Etapa 'Provisionado' no encontrada.")
            return
        
        self.sudo().write(
            {
                "income_recognition_date": fields.Date.context_today(self),
                "backlog_state_id": stage_provisioned.id,
                "bklg_state": "provisioned",
            }
        )

        for rec in self:
            rec.message_post(
                body=Markup(
                    _("Moved to Provisioned stage by <b><i>%s</i></b>.") 
                    % self.env.user.name
                )
            )

    def action_reverse_provision(self):
        """Reverse provision and force recalculation of currency amounts"""
        stage_planning = self.env["backlog.stages"].search(
            [("stages_type", "=", "planning")], limit=1
        )

        if not stage_planning:
            _logger.warning("Etapa 'Planning' no encontrada.")
            return

        # First update the state to trigger recomputation
        self.sudo().write(
            {
                "income_recognition_date": False,
                "backlog_state_id": stage_planning.id,
                "bklg_state": "planning",
                "initial_provisioned_amount": 0.0,
                "initial_provisioned_amount_datetime": False,
            }
        )

        # Force recomputation of currency fields
        self._compute_amount_us()
        self.compute_clp_currency()

        for rec in self:
            rec.message_post(
                body=Markup(
                    f"Reversed provision by <b><i>{self.env.user.name}</i></b>. Currency amounts recalculated."
                )
            )

    @api.model
    def fields_view_get(
        self, view_id=None, view_type=None, toolbar=False, submenu=False
    ):
        res = super(kvz_backlog_lines, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        if view_type == "form" and self._context.get("params"):
            if self._context["params"].get("id"):
                record_id = self._context["params"]["id"]
                record = self.env["sale.order.line"].search([("id", "=", record_id)])
                # allow salesperson to see the unforecast button
                if record.user_id.id == self.env.uid:
                    doc = etree.XML(res["arch"])
                    nodes = doc.xpath("//button[@name='action_unforecast']")
                    # check if unforecast button should be visible
                    if record.stages_type == "forecast":
                        for node in nodes:
                            node.set("invisible", "0")
                            node.set("modifiers", '{"invisible": false}')
                    res["arch"] = etree.tostring(doc)
        return res
