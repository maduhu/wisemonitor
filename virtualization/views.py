import os
import sys
import json

from tornado import web
from tornado import gen

from common.init import *

from xenserver import get_vm_info
from xenserver import get_xenserver_host
from xenserver import get_xenserver_host_all
from xenserver import get_xenserver_vm_all
from logger import logger

import settings
from settings import MOTOR_DB as DB


@gen.coroutine
def parse_perfdata(cursor, callback):
    fields_data = []
    yield cursor.fetch_next
    record = cursor.next_object()
    data = record['data']
    callback(data)


class XenServer_VMs_Chart_Handler(WiseHandler):
    @web.asynchronous
    @gen.coroutine
    def get(self, uuid, ttype):
        print uuid,ttype
        cursor = DB.virtual_host.find({"uuid": uuid, "type": ttype})
        yield parse_perfdata(cursor, self.on_parse_finished)
    
    def on_parse_finished(self, data):
        self.render("virtualization/xenserver_vm_chart.html", data=data)


class XenServer_Get_Host(WiseHandler):
    def get(self, xen_host):
        host = get_xenserver_host(xen_host)
        self.render("virtualization/xenserver_host.html", host=host)


class XenServer_Get_ALL(WiseHandler):
    def get(self):
        hosts = get_xenserver_host_all()
        self.render("virtualization/xenserver_all_hosts.html", xenserver_list=hosts)


class XenServer_Get_ALL_vms(WiseHandler):
    def get(self, host):
        vms = get_xenserver_vm_all(host)
        self.render("virtualization/xenserver_all_vms.html", vms=vms, host_address=host)


class XenServer_Get_VM_Console(WiseHandler):
    def get(self, host, vm_ref):
        vm_info = get_vm_info(host, vm_ref)
        self.render("virtualization/xenserver_console.html",
                    novnc_host=settings.NOVNC_SERVER_IP,
                    novnc_port = settings.NOVNC_SERVER_PORT,
                    vm_ref=vm_ref, host_address=host, vm_info=vm_info)

