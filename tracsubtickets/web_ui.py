# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Takashi Ito
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the authors nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from trac.config import Option, IntOption, ChoiceOption, ListOption
from trac.core import Component, implements
from trac.web.api import IRequestFilter
from trac.web.chrome import ITemplateProvider, add_stylesheet, add_script, add_script_data
from trac.util.html import html as tag
from trac.ticket.api import ITicketManipulator
from trac.ticket.model import Ticket
from trac.ticket.model import Type as TicketType
from trac.resource import ResourceNotFound
from trac.util.translation import domain_functions
import os
import json

from tracsubtickets.api import NUMBERS_RE, _

# i18n support for plugins
_, tag_, N_, add_domain = domain_functions('tracsubtickets',
                                           '_', 'tag_', 'N_', 'add_domain')

# Get Trac's core translations
_, core_tag_, core_N_, add_core_domain = domain_functions('trac',
                                           '_', 'tag_', 'N_', 'add_domain')

class SubTicketsModule(Component):

    implements(IRequestFilter, ITicketManipulator, ITemplateProvider)

    # Simple Options

    opt_skip_validation = ListOption(
        'subtickets', 'skip_closure_validation', default=[], doc=_("""
         Normally, reopening a child with a `closed` parent will be
         refused and closing a parent with non-`closed` children will also
         be refused. Adding either of `reopen` or `resolve` to this option will
         make Subtickets skip this validation for the respective action.
         Separate by comma if both actions are listed.

         Caveat: This functionality will be made workflow-independent in a
         future release of !SubTicketsPlugin.
         """))

    opt_recursion_depth = IntOption(
        'subtickets', 'recursion_depth', default=-1, doc=_("""
         Limit the number of recursive levels when listing subtickets.
         Default is infinity, represented by`-1`. The value zero (0)
         limits the listing to immediate children.
         """))

    opt_add_style = ChoiceOption('subtickets', 'add_style', ['button', 'link'],
                                 doc=_("""
         Choose whether to make `Add` look like a button (default) or a link
         """)
                                 )

    opt_owner_url = Option('subtickets', 'owner_url',
                           doc=_("""
                           Currently undocumented.
                           """)
                           )

    # Per-ticket type options -- all initialised in __init__()

    opt_inherit_fields = dict()
    opt_columns = dict()

    def _add_per_ticket_type_option(self, ticket_type):

        self.opt_inherit_fields[ticket_type] = ListOption(
            'subtickets', 'type.%s.child_inherits' % ticket_type, default='',
            doc=_("""Comma-separated list of ticket fields whose values are
            to be copied from a parent ticket into a newly created
            child ticket.
            """))

        self.opt_columns[ticket_type] = ListOption(
            'subtickets', 'type.%s.table_columns' % ticket_type,
            default='status,owner', doc=_("""
             Comma-separated list of ticket fields whose values are to be
             shown for each child ticket in the subtickets list
             """))

    def __init__(self):
        # The following initialisations must happen inside init()
        # in order to be able to access self.env
        for tt in TicketType.select(self.env):
            self._add_per_ticket_type_option(tt.name)

    # ITemplateProvider methods

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('subtickets', resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        return []

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        try:
            # Use empty string if path_info is None
            path = req.path_info or ''
            self.log.debug('Processing request path: %s', path)

            # Process ticket page
            if '/ticket/' in path:
                if data and 'ticket' in data:
                    ticket = data['ticket']
                    self.log.debug('Processing ticket #%s', ticket.id)

                    parents = ticket['parents'] or ''
                    ids = set(NUMBERS_RE.findall(parents))

                    if len(parents) > 0:
                        self._append_parent_links(req, data, ids)

                    # Prepare subticket data for display
                    if ticket.exists:
                        data['subtickets'] = []

                        # Recursively get child tickets
                        children_data = self._get_children_data(ticket.id)
                        self.log.debug('Found children data: %s', children_data)

                        # Flatten child ticket data for display
                        self._flatten_children_data(children_data, data['subtickets'], 0)
                        self.log.debug('Final subtickets data: %s', data.get('subtickets', []))

                        add_stylesheet(req, 'subtickets/css/subtickets.css')

                        # Get internationalized column names
                        column_names = {
                            'id': _('Ticket'),
                            'summary': _('Summary'),
                            'status': _('Status'),
                            'type': _('Type'),
                            'priority': _('Priority'),
                            'owner': _('Owner')
                        }

                        # Pass subticket data to JavaScript
                        js_data = {
                            'tracSubticketsData': data['subtickets'],
                            'columnNames': column_names
                        }
                        add_script_data(req, js_data)

                        # Load subtickets.js after setting the data
                        add_script(req, 'subtickets/js/subtickets.js')

            # Process admin page
            if '/admin/ticket/type' in path \
                    and data \
                    and set(['add', 'name']).issubset(data.keys()) \
                    and data['add'] == 'Add':
                self._add_per_ticket_type_option(data['name'])

        except Exception as e:
            self.log.error('Error in post_process_request: %s', str(e))
            self.log.error('Request path: %r, Template: %r', getattr(req, 'path_info', None), template)
            raise

        return template, data, content_type

    def _get_children_data(self, parent_id):
        """Recursively retrieve child ticket data"""
        children_data = []

        for parent, child in self.env.db_query("""
                SELECT parent, child FROM subtickets WHERE parent=%s
                """, (parent_id,)):
            try:
                child_ticket = Ticket(self.env, child)
                child_data = {
                    'id': child,
                    'summary': child_ticket['summary'],
                    'status': child_ticket['status'],
                    'type': child_ticket['type'],
                    'priority': child_ticket['priority'],
                    'owner': child_ticket['owner'],
                    'href': self.env.href.ticket(child),
                    'children': self._get_children_data(child)
                }
                children_data.append(child_data)
            except ResourceNotFound:
                self.log.warning('Child ticket #%s not found', child)
                continue

        return children_data

    def _flatten_children_data(self, children_data, result, level):
        """Flatten recursive child ticket data for display"""
        for child in children_data:
            # Add level information
            child['level'] = level
            result.append(child)

            # Process recursively if there are child tickets
            if child['children'] and len(child['children']) > 0:
                self._flatten_children_data(child['children'], result, level + 1)

    def _append_parent_links(self, req, data, ids):
        links = []
        for id in sorted(ids, key=lambda x: int(x)):
            try:
                ticket = Ticket(self.env, id)
                elem = tag.a('#%s' % id,
                             href=req.href.ticket(id),
                             class_='%s ticket' % ticket['status'],
                             title=ticket['summary'])
                if len(links) > 0:
                    links.append(', ')
                links.append(elem)
            except ResourceNotFound:
                pass
        for field in data.get('fields', ''):
            if field.get('name') == 'parents':
                field['rendered'] = tag.span(*links)

    # ITicketManipulator methods

    def prepare_ticket(self, req, ticket, fields, actions):
        pass

    def get_children(self, parent_id, depth=0):
        children = {}

        for parent, child in self.env.db_query("""
                SELECT parent, child FROM subtickets WHERE parent=%s
                """, (parent_id, )):
            children[child] = None

        if self.opt_recursion_depth > depth or self.opt_recursion_depth == -1:
            for id in children:
                children[id] = self.get_children(id, depth + 1)

        return children

    def validate_ticket(self, req, ticket):
        action = req.args.get('action')

        if action in self.opt_skip_validation:
            return

        if action == 'resolve':

            for parent, child in self.env.db_query("""
                    SELECT parent, child FROM subtickets WHERE parent=%s
                    """, (ticket.id, )):
                if Ticket(self.env, child)['status'] != 'closed':
                    yield None, _("""Cannot close/resolve because child
                         ticket #%(child)s is still open""",
                                  child=child)

        elif action == 'reopen':
            ids = set(NUMBERS_RE.findall(ticket['parents'] or ''))
            for id in ids:
                if Ticket(self.env, id)['status'] == 'closed':
                    msg = _("Cannot reopen because parent ticket #%(id)s "
                            "is closed", id=id)
                    yield None, msg
