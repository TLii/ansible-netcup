#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright: Tuomas Liinamaa <tlii@iki.fi>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
---

name: netcup

short_description: Create inventory dynamically from Netcup SCP webservice

description:
    - This inventory plugin allows you to create a dynamic inventory from servers hosted by Netcup via Netcup SCP WebService.
    - Each server will be added as a single host, connectable by its first public IP.
    - Inventory will include all virtual servers, ie. both RS and VPS servers as well as older generation storage servers.
    - Configuration file MUST end with netcup.yaml or netcup.yml.

notes:
    - The plugin utilizes Netcup SCP webservice functionality. You must enable it and set an access password on Netcup Server Control Panel.
    - As of writing (30.7.2024), the Netcup SCP WebService doesn't provide the vServer hostname that you can set on the SCP website.
    - For virtual private network interfaces only MAC addresses and adapter types are available. No IP configuration is done on the SCP and hence such is not available for this plugin.
    - If you want to use ansible within LAN, you must figure out another way to determine correct IP addresses for each host. You could use ansible_host_suffix option and a LAN-resolvable domain name, but you must figure out the details yourself.

author:
    - Tuomas Liinamaa (@TLii)

requirements:
    - zeep => 4.2.0

version_added: "1.0.0"

options:
    plugin:
        description: Ensure only proper Netcup inventory files are processed.
        required: true
        choices: ['tlii.netcup.netcup', 'netcup']

    customer_id:
        option-name: Netcup Customer ID
        description:
            - Customer ID used to login to Netcup SCP and, hence, the Webservice.
        required: True
        type: str
        env:
            - name: NETCUP_CUSTOMER_ID

    password:
        option-name: Webservice password
        description:
            - Password for Webservice access. Note that this password is different from the password used to login to SCP. Webservice password must be explicitly set in the SCP.
        required: True
        type: str
        no_log: true
        env:
            - name: NETCUP_WS_PASSWORD

    wsdl_url:
        option-name: Webservice description url
        description:
            - Description URL for Netcup webservice. The default value should be fine.
        required: false
        default: "https://www.servercontrolpanel.de/WSEndUser?wsdl"
        env:
            - name: NETCUP_WSDL_URL

    group:
        option-name: Add servers to this group
        description:
            - The group all servers are automatically added to.
        type: str
        required: false
        default: netcup
        env:
            - name: NETCUP_GROUP

    ansible_host_type:
        option-name: Ansible host type
        description:
            - Defines which address should Ansible connect. 
            - The default is 'ip', in which case Ansible will connect to the primary external IP the WebService provides.
            - Use 'name' to connect using the server name, ie. the server's nickname combined with hostname_prefix and hostname_suffix.
            - Use 'suffix' to use only ansible_host_suffix or, if not provided, hostname_suffix, but no prefix. This could be used to force a LAN resolvable address for connection.
        type: str
        required: false
        default: ip
        choices:
            - 'ip'
            - 'name'
            - 'suffix'
        env:
            - name: NETCUP_ANSIBLE_HOST_TYPE

    ansible_host_suffix:
        option-name: Ansible host suffix
        description:
            - Suffix to be added to the server's nickname/name instead of the host-suffix.
        type: str
        required: false
        default: ""
        env:
            - name: NETCUP_ANSIBLE_HOST_SUFFIX

    hostname_prefix:
        option-name: Server name prefix
        description:
            - All servers get an Ansible name based on server nickname, if it is present, and based on server name (usually in the form of v[0-9]*).
            - If you wish to prepend this nickname with a static value, you can provide a prefix to be added to each name.
            - Note: ALL characters, including a possible dot, dash or other special character between the prefix and the nickname, must be included.
        type: str
        required: False
        default: ""
        env:
            - name: NETCUP_HOSTNAME_PREFIX

    hostname_suffix:
        option-name: Server name suffix
        description:
            - All servers get an Ansible name based on server nickname, if it is present, and based on server name (usually in the form of v[0-9]*).
            - If you wish to append this nickname with a static value, you can provide a suffix to be added to each name.
            - This could be useful to e.g. create fqdn based names.
            - Note: ALL characters, including a possible dot, dash or other special character between the name and the suffix, must be included.
        type: str
        required: False
        default: ""
        env:
            - name: NETCUP_HOSTNAME_SUFFIX



seealso:
    - name: Netcup HelpCenter - SCP Webservice
      description: Netcup documentation for WebService
      link: "https://helpcenter.netcup.com/en/wiki/server/scp-webservice/"

'''
EXAMPLES = '''
---
# Basic example
# inventory/01-netcup.yml
plugin: netcup
customer_id: 1234
password: awesomepassword

'''
from zeep import Client as ZClient
from ansible.errors import AnsibleParserError
#from ansible.module_utils.six import string_types
#from ansible.module_utils.common.text.converters import to_native, to_text
from ansible.plugins.inventory import BaseInventoryPlugin


class InventoryModule(BaseInventoryPlugin):
    NAME = 'tlii.netcup.netcup'

    def __init__(self):

        super(InventoryModule, self).__init__()

    def _get_server_list(self, wsdl_url, username, password):
        client = ZClient(wsdl_url)

        try:
            server_list = client.service.getVServers(
                loginName = username,
                password = password
            )
        except Exception as err:
            raise AnsibleParserError(
                'Unable to get server list: {err}') from err

        return server_list

    def _get_server_info(self, wsdl_url, username, password, server_name):
        client = ZClient(wsdl_url)
        try:
            server_info = client.service.getVServerInformation(
                loginName = username,
                password = password,
                vservername = server_name,
                language = 'en'
            )
        except Exception as err:
            raise AnsibleParserError(
                'Unable to get server information: {err}') from err

        return server_info

    def _parse_server(self, server_data):
        srv_prefix = self.get_option('hostname_prefix')
        servername = srv_prefix

        if len(server_data['vServerNickname']) > 0:
            servername = servername + server_data['vServerNickname']
        else:
            servername = servername + server_data['vServerName']

        srv_suffix = self.get_option('hostname_suffix')
        servername = servername + srv_suffix

        if server_data['status'] == 'online':

            self.inventory.add_host(servername)

            match self.get_option('ansible_host_type'):
                case 'ip':
                    self.inventory.set_variable(
                        servername,
                        'ansible_host',
                        server_data['ips'][0]
                    )
                case 'name':
                    self.inventory.set_variable(
                        servername,
                        'ansible_host',
                        servername
                    )
                case 'suffix':
                    self.inventory.set_variable(
                        servername,
                        'ansible_host',
                        server_data['ips'][0]
                    )

            server_vars = {
                'server_name': server_data['vServerName'],
                'server_nickname': server_data['vServerNickname'],
                'reboot_recommended': server_data['rebootRecommended'],
                'status': server_data['status'],
            }

            for hostvar, ws_var in server_vars.items():
                self.inventory.set_variable(servername, 'netcup_' + hostvar, ws_var)

            self.inventory.add_child(self.get_option('group'), servername)

    def verify_file(self, path):
        ''' return true/false if this is possibly a valid file for this plugin to consume '''
        valid = False
        if super(InventoryModule, self).verify_file(path):
            if path.endswith(('netcup.yaml', 'netcup.yml')):
                valid = True
        return valid

    def parse(self, inventory, loader, path, cache):
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        self._read_config_data(path)

        try:
            wsdl_url = self.get_option('wsdl_url')
            wsdl_login = self.get_option('customer_id')
            wsdl_password = self.get_option('password')
        except Exception as err:
            raise AnsibleParserError(
                f'All correct options required: {err}') from err

        server_list = self._get_server_list(wsdl_url, wsdl_login, wsdl_password)

        if not server_list:
            raise AnsibleParserError('Did not receive a server list from Webservice.')
        if len(server_list) == 0:
            raise AnsibleParserError('Empty server list')

        self.inventory.add_group(self.get_option('group'))

        for server in server_list:
            self._parse_server(self._get_server_info(wsdl_url, wsdl_login, wsdl_password, server))
