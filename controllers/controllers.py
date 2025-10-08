# from odoo import http


# class KvzBacklog(http.Controller):
#     @http.route('/kvz_backlog/kvz_backlog', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/kvz_backlog/kvz_backlog/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('kvz_backlog.listing', {
#             'root': '/kvz_backlog/kvz_backlog',
#             'objects': http.request.env['kvz_backlog.kvz_backlog'].search([]),
#         })

#     @http.route('/kvz_backlog/kvz_backlog/objects/<model("kvz_backlog.kvz_backlog"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('kvz_backlog.object', {
#             'object': obj
#         })
