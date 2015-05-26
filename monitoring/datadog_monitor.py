#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Author: Ashley Penney <apenney@ntoggle.com>
# Based primarily on the datadog_event module,
# thanks to Artūras 'arturaz' Šlajus.

DOCUMENTATION = '''
---
module: datadog_monitor
short_description: Creates monitors within Datadog
description:
- "Creates monitors withinin Datadog"
- "Uses the http://docs.datadoghq.com/api/#monitors API."
version_added: "0.1"
author: '"Ashley Penney" <apenney@ntoggle.com>'
notes: []
requirements: [urllib2]
options:
    api_key:
        description: ["Your DataDog API key."]
        required: true
        default: null
    app_key:
        description: ["Your DataDog app key."]
        required: true
        default: null
    type:
        description: ["The monitor type."]
        required: true
        default: null
        choices: ['metric alert', 'service check']
    name:
        description: ["Name of the monitor"]
        required: true
        default: null
    query:
        description: ["The query of the monitor."]
        required: true
        default: null
    message:
        description: ["The message to include with notifications for the monitor."]
        required: false
        default: null
    silenced:
        description: ["Dictionary of scopes to timestamps, which will be muted."]
        required: false
        default: null
    notify_no_data:
        description: ["Will this monitor alert when data stops reporting."]
        required: false
        default: False
    no_data_timeframe:
        description: ["Number of minutes before a monitor will notify when data stops reporting."]
        required: false
        default: 2x timeframe for metric, 2 minutes for service
    timeout_h:
        description: ["Number of hours of the monitor not reporting data before automatic resolve."]
        required: false
        default: null
    renotify_interval:
        description: ["Number of minutes after the last notification before monitor re-notifies."]
        required: false
        default: null
    escalation_message:
        description: ["A message to include with re-notifications"]
        required: false
        default: null
    notify_audit:
        description: ["Will tagged users be notified on changes to this monitor"]
        required: false
        default: False
    thresholds:
        description: ["Dictionary of thresholds by status."]
        required: false
        default: {'ok': 1, 'critical': 1, 'warning': 1}
'''

EXAMPLES = '''
# Create a metric monitor
datadog_monitor:
  type: "metric alert"
  name: "Test monitor"
  query: "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"
  message: "Arbitary alert message."
  api_key: "6873258723457823548234234234"
  app_key: "3248923456767823753287723821"
  silenced:
    'role:db': 1412798116
    'role:web': 1412798512

# Create a service monitor
datadog_monitor:
  type: "service"
  name: "Test check"
  query: '"check".over(tags).last(count).count_by_status()'
  message: "Arbitary alert message."
  api_key: "6873258723457823548234234234"
  app_key: "3248923456767823753287723821"
  thresholds:
    ok: 1
    critical: 2
    warning: 1
'''

OPTIONS = ['silenced', 'notify_no_data', 'no_data_timeframe', 'timeout_h',
           'renotify_interval', 'escalation_message', 'notify_audit',
           'thresholds']


def main():
    module = AnsibleModule(
        argument_spec=dict(
            api_key=dict(required=True),
            app_key=dict(required=True),
            type=dict(required=True),
            query=dict(required=True),
            name=dict(required=True),
            message=dict(required=False, default=None),
            silenced=dict(required=False, default=None),
            notify_no_data=dict(required=False, default=False),
            no_data_timeframe=dict(required=False, default=None),
            timeout_h=dict(required=False, default=None),
            renotify_interval=dict(required=False, default=None),
            escalation_message=dict(required=False, default=None),
            notify_audit=dict(required=False, default=None),
            thresholds=dict(required=False, default=None),
        )
    )

    post_monitor(module)


def installed(module):
    uri = "https://app.datadoghq.com/api/v1/monitor?api_key={0}&application_key={1}".format(module.params['api_key'], module.params['app_key'])

    headers = {"Content-Type": "application/json"}
    (response, info) = fetch_url(module, uri, headers=headers)
    if info['status'] == 200:
        installed = False
        body = response.read()
        monitors = json.loads(body)
        for monitor in monitors:
            if monitor['name'] == module.params['name']:
                installed = True
    # If we have any failures from fetching all monitors assume it's installed
    # so we don't add multiple copies in the case of transient failure
    else:
        installed = False

    return installed


def post_monitor(module):
    uri = "https://app.datadoghq.com/api/v1/monitor?api_key={0}&application_key={1}".format(module.params['api_key'], module.params['app_key'])

    # Mandatory requirements
    body = dict(
        type=module.params['type'],
        query=module.params['query'],
        name=module.params['name'],
    )

    # Thesholds may only be set with service type
    if module.params['type'] == 'metric alert' and module.params['thresholds'] is not None:
        module.fail_json(msg="thresholds may not be set for metric monitors")

    if installed(module):
        module.exit_json(changed=False)
    else:
        for param in OPTIONS:
            if module.params[param] is not None:
                body[param] = module.params[param]

        json_body = module.jsonify(body)
        headers = {"Content-Type": "application/json"}

        (response, info) = fetch_url(module, uri, data=json_body, headers=headers)
        if info['status'] == 200:
            response_body = response.read()
            response_json = module.from_json(response_body)
            if response_json['id'] is not None:
                module.exit_json(changed=True)
            else:
                module.fail_json(msg=response)
        else:
            module.fail_json(**info)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *

main()
