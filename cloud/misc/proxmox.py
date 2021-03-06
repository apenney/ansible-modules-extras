#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: proxmox
short_description: management of instances in Proxmox VE cluster
description:
  - allows you to create/delete/stop instances in Proxmox VE cluster
version_added: "2.0"
options:
  api_host:
    description:
      - the host of the Proxmox VE cluster
    default: null
    required: true
  api_user:
    description:
      - the user to authenticate with
    default: null
    required: true
  api_password:
    description:
      - the password to authenticate with
      - you can use PROXMOX_PASSWORD environment variable
    default: null
    required: false
  vmid:
    description:
      - the instance id
    default: null
    required: true
  https_verify_ssl:
    description:
      - enable / disable https certificate verification
    default: false
    required: false
    type: boolean
  node:
    description:
      - Proxmox VE node, when new VM will be created
      - required only for state="present"
      - for another states will be autodiscovered
    default: null
    required: false
  password:
    description:
      - the instance root password
      - required only for state="present"
    default: null
    required: false
  hostname:
    description:
      - the instance hostname
      - required only for state="present"
    default: null
    required: false
  ostemplate:
    description:
      - the template for VM creating
      - required only for state="present"
    default: null
    required: false
  disk:
    description:
      - hard disk size in GB for instance
    default: 3
    required: false
  cpus:
    description:
      - numbers of allocated cpus for instance
    default: 1
    required: false
  memory:
    description:
      - memory size in MB for instance
    default: 512
    required: false
  swap:
    description:
      - swap memory size in MB for instance
    default: 0
    required: false
  netif:
    description:
      - specifies network interfaces for the container
    default: null
    required: false
    type: string
  ip_address:
    description:
      - specifies the address the container will be assigned
    default: null
    required: false
    type: string
  onboot:
    description:
      - specifies whether a VM will be started during system bootup
    default: false
    required: false
    type: boolean
  storage:
    description:
      - target storage
    default: 'local'
    required: false
    type: string
  cpuunits:
    description:
      - CPU weight for a VM
    default: 1000
    required: false
    type: integer
  nameserver:
    description:
      - sets DNS server IP address for a container
    default: null
    required: false
    type: string
  searchdomain:
    description:
      - sets DNS search domain for a container
    default: null
    required: false
    type: string
  timeout:
    description:
      - timeout for operations
    default: 30
    required: false
    type: integer
  force:
    description:
      - forcing operations
      - can be used only with states "present", "stopped", "restarted"
      - with state="present" force option allow to overwrite existing container
      - with states "stopped", "restarted" allow to force stop instance
    default: false
    required: false
    type: boolean
  state:
    description:
     - Indicate desired state of the instance
    choices: ['present', 'started', 'absent', 'stopped', 'restarted']
    default: present
notes:
  - Requires proxmoxer and requests modules on host. This modules can be installed with pip.
requirements: [ "proxmoxer", "requests" ]
author: Sergei Antipov
'''

import os
import time

try:
  from proxmoxer import ProxmoxAPI
  HAS_PROXMOXER = True
except ImportError:
  HAS_PROXMOXER = False

def get_instance(proxmox, vmid):
  return [ vm for vm in proxmox.cluster.resources.get(type='vm') if vm['vmid'] == int(vmid) ]

def content_check(proxmox, node, ostemplate, storage):
  return [ True for cnt in proxmox.nodes(node).storage(storage).content.get() if cnt['volid'] == ostemplate ]

def node_check(proxmox, node):
  return [ True for nd in proxmox.nodes.get() if nd['node'] == node ]

def create_instance(module, proxmox, vmid, node, disk, storage, cpus, memory, swap, timeout, **kwargs):
  proxmox_node = proxmox.nodes(node)
  taskid = proxmox_node.openvz.create(vmid=vmid, storage=storage, memory=memory, swap=swap,
                             cpus=cpus, disk=disk, **kwargs)

  while timeout:
    if ( proxmox_node.tasks(taskid).status.get()['status'] == 'stopped'
        and proxmox_node.tasks(taskid).status.get()['exitstatus'] == 'OK' ):
      return True
    timeout = timeout - 1
    if timeout == 0:
      module.fail_json(msg='Reached timeout while waiting for creating VM. Last line in task before timeout: %s'
                       % proxmox_node.tasks(taskid).log.get()[:1])

    time.sleep(1)

def start_instance(module, proxmox, vm, vmid, timeout):
  taskid = proxmox.nodes(vm[0]['node']).openvz(vmid).status.start.post()
  while timeout:
    if ( proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['status'] == 'stopped'
        and proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['exitstatus'] == 'OK' ):
      return True
    timeout = timeout - 1
    if timeout == 0:
      module.fail_json(msg='Reached timeout while waiting for starting VM. Last line in task before timeout: %s'
                       % proxmox.nodes(vm[0]['node']).tasks(taskid).log.get()[:1])

    time.sleep(1)
  return False

def stop_instance(module, proxmox, vm, vmid, timeout, force):
  if force:
    taskid = proxmox.nodes(vm[0]['node']).openvz(vmid).status.shutdown.post(forceStop=1)
  else:
    taskid = proxmox.nodes(vm[0]['node']).openvz(vmid).status.shutdown.post()
  while timeout:
    if ( proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['status'] == 'stopped'
        and proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['exitstatus'] == 'OK' ):
      return True
    timeout = timeout - 1
    if timeout == 0:
      module.fail_json(msg='Reached timeout while waiting for stopping VM. Last line in task before timeout: %s'
                       % proxmox_node.tasks(taskid).log.get()[:1])

    time.sleep(1)
  return False

def umount_instance(module, proxmox, vm, vmid, timeout):
  taskid = proxmox.nodes(vm[0]['node']).openvz(vmid).status.umount.post()
  while timeout:
    if ( proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['status'] == 'stopped'
        and proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['exitstatus'] == 'OK' ):
      return True
    timeout = timeout - 1
    if timeout == 0:
      module.fail_json(msg='Reached timeout while waiting for unmounting VM. Last line in task before timeout: %s'
                       % proxmox_node.tasks(taskid).log.get()[:1])

    time.sleep(1)
  return False

def main():
  module = AnsibleModule(
    argument_spec = dict(
      api_host = dict(required=True),
      api_user = dict(required=True),
      api_password = dict(),
      vmid = dict(required=True),
      https_verify_ssl = dict(type='bool', choices=BOOLEANS, default='no'),
      node = dict(),
      password = dict(),
      hostname = dict(),
      ostemplate = dict(),
      disk = dict(type='int', default=3),
      cpus = dict(type='int', default=1),
      memory = dict(type='int', default=512),
      swap = dict(type='int', default=0),
      netif = dict(),
      ip_address = dict(),
      onboot = dict(type='bool', choices=BOOLEANS, default='no'),
      storage = dict(default='local'),
      cpuunits = dict(type='int', default=1000),
      nameserver = dict(),
      searchdomain = dict(),
      timeout = dict(type='int', default=30),
      force = dict(type='bool', choices=BOOLEANS, default='no'),
      state = dict(default='present', choices=['present', 'absent', 'stopped', 'started', 'restarted']),
    )
  )

  if not HAS_PROXMOXER:
    module.fail_json(msg='proxmoxer required for this module')

  state = module.params['state']
  api_user = module.params['api_user']
  api_host = module.params['api_host']
  api_password = module.params['api_password']
  vmid = module.params['vmid']
  https_verify_ssl = module.params['https_verify_ssl']
  node = module.params['node']
  disk = module.params['disk']
  cpus = module.params['cpus']
  memory = module.params['memory']
  swap = module.params['swap']
  storage = module.params['storage']
  timeout = module.params['timeout']

  # If password not set get it from PROXMOX_PASSWORD env
  if not api_password:
    try:
      api_password = os.environ['PROXMOX_PASSWORD']
    except KeyError, e:
      module.fail_json(msg='You should set api_password param or use PROXMOX_PASSWORD environment variable')

  try:
    proxmox = ProxmoxAPI(api_host, user=api_user, password=api_password, verify_ssl=https_verify_ssl)
  except Exception, e:
    module.fail_json(msg='authorization on proxmox cluster failed with exception: %s' % e)

  if state == 'present':
    try:
      if get_instance(proxmox, vmid) and not module.params['force']:
        module.exit_json(changed=False, msg="VM with vmid = %s is already exists" % vmid)
      elif not (node, module.params['hostname'] and module.params['password'] and module.params['ostemplate']):
        module.fail_json(msg='node, hostname, password and ostemplate are mandatory for creating vm')
      elif not node_check(proxmox, node):
        module.fail_json(msg="node '%s' not exists in cluster" % node)
      elif not content_check(proxmox, node, module.params['ostemplate'], storage):
        module.fail_json(msg="ostemplate '%s' not exists on node %s and storage %s"
                         % (module.params['ostemplate'], node, storage))

      create_instance(module, proxmox, vmid, node, disk, storage, cpus, memory, swap, timeout,
                      password = module.params['password'],
                      hostname = module.params['hostname'],
                      ostemplate = module.params['ostemplate'],
                      netif = module.params['netif'],
                      ip_address = module.params['ip_address'],
                      onboot = int(module.params['onboot']),
                      cpuunits = module.params['cpuunits'],
                      nameserver = module.params['nameserver'],
                      searchdomain = module.params['searchdomain'],
                      force = int(module.params['force']))

      module.exit_json(changed=True, msg="deployed VM %s from template %s"  % (vmid, module.params['ostemplate']))
    except Exception, e:
      module.fail_json(msg="creation of VM %s failed with exception: %s" % ( vmid, e ))

  elif state == 'started':
    try:
      vm = get_instance(proxmox, vmid)
      if not vm:
        module.fail_json(msg='VM with vmid = %s not exists in cluster' % vmid)
      if proxmox.nodes(vm[0]['node']).openvz(vmid).status.current.get()['status'] == 'running':
        module.exit_json(changed=False, msg="VM %s is already running" % vmid)

      if start_instance(module, proxmox, vm, vmid, timeout):
        module.exit_json(changed=True, msg="VM %s started" % vmid)
    except Exception, e:
      module.fail_json(msg="starting of VM %s failed with exception: %s" % ( vmid, e ))

  elif state == 'stopped':
    try:
      vm = get_instance(proxmox, vmid)
      if not vm:
        module.fail_json(msg='VM with vmid = %s not exists in cluster' % vmid)

      if proxmox.nodes(vm[0]['node']).openvz(vmid).status.current.get()['status'] == 'mounted':
        if module.params['force']:
          if umount_instance(module, proxmox, vm, vmid, timeout):
            module.exit_json(changed=True, msg="VM %s is shutting down" % vmid)
        else:
          module.exit_json(changed=False, msg=("VM %s is already shutdown, but mounted. "
                                               "You can use force option to umount it.") % vmid)

      if proxmox.nodes(vm[0]['node']).openvz(vmid).status.current.get()['status'] == 'stopped':
        module.exit_json(changed=False, msg="VM %s is already shutdown" % vmid)

      if stop_instance(module, proxmox, vm, vmid, timeout, force = module.params['force']):
        module.exit_json(changed=True, msg="VM %s is shutting down" % vmid)
    except Exception, e:
      module.fail_json(msg="stopping of VM %s failed with exception: %s" % ( vmid, e ))

  elif state == 'restarted':
    try:
      vm = get_instance(proxmox, vmid)
      if not vm:
        module.fail_json(msg='VM with vmid = %s not exists in cluster' % vmid)
      if ( proxmox.nodes(vm[0]['node']).openvz(vmid).status.current.get()['status'] == 'stopped'
          or proxmox.nodes(vm[0]['node']).openvz(vmid).status.current.get()['status'] == 'mounted' ):
        module.exit_json(changed=False, msg="VM %s is not running" % vmid)

      if ( stop_instance(module, proxmox, vm, vmid, timeout, force = module.params['force']) and
          start_instance(module, proxmox, vm, vmid, timeout) ):
        module.exit_json(changed=True, msg="VM %s is restarted" % vmid)
    except Exception, e:
      module.fail_json(msg="restarting of VM %s failed with exception: %s" % ( vmid, e ))

  elif state == 'absent':
    try:
      vm = get_instance(proxmox, vmid)
      if not vm:
        module.exit_json(changed=False, msg="VM %s does not exist" % vmid)

      if proxmox.nodes(vm[0]['node']).openvz(vmid).status.current.get()['status'] == 'running':
        module.exit_json(changed=False, msg="VM %s is running. Stop it before deletion." % vmid)

      if proxmox.nodes(vm[0]['node']).openvz(vmid).status.current.get()['status'] == 'mounted':
        module.exit_json(changed=False, msg="VM %s is mounted. Stop it with force option before deletion." % vmid)

      taskid = proxmox.nodes(vm[0]['node']).openvz.delete(vmid)
      while timeout:
        if ( proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['status'] == 'stopped'
            and proxmox.nodes(vm[0]['node']).tasks(taskid).status.get()['exitstatus'] == 'OK' ):
          module.exit_json(changed=True, msg="VM %s removed" % vmid)
        timeout = timeout - 1
        if timeout == 0:
          module.fail_json(msg='Reached timeout while waiting for removing VM. Last line in task before timeout: %s'
                           % proxmox_node.tasks(taskid).log.get()[:1])

        time.sleep(1)
    except Exception, e:
      module.fail_json(msg="deletion of VM %s failed with exception: %s" % ( vmid, e ))

# import module snippets
from ansible.module_utils.basic import *
main()
