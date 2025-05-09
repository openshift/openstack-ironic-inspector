#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.from oslo_config import cfg

from oslo_config import cfg

from ironic_inspector.conf import accelerators
from ironic_inspector.conf import capabilities
from ironic_inspector.conf import coordination
from ironic_inspector.conf import default
from ironic_inspector.conf import discovery
from ironic_inspector.conf import dnsmasq_pxe_filter
from ironic_inspector.conf import exception
from ironic_inspector.conf import extra_hardware
from ironic_inspector.conf import healthcheck
from ironic_inspector.conf import iptables
from ironic_inspector.conf import ironic
from ironic_inspector.conf import mdns
from ironic_inspector.conf import pci_devices
from ironic_inspector.conf import port_physnet
from ironic_inspector.conf import processing
from ironic_inspector.conf import pxe_filter
from ironic_inspector.conf import service_catalog
from ironic_inspector.conf import swift


CONF = cfg.CONF


accelerators.register_opts(CONF)
capabilities.register_opts(CONF)
coordination.register_opts(CONF)
discovery.register_opts(CONF)
default.register_opts(CONF)
dnsmasq_pxe_filter.register_opts(CONF)
exception.register_opts(CONF)
extra_hardware.register_opts(CONF)
healthcheck.register_opts(CONF)
iptables.register_opts(CONF)
ironic.register_opts(CONF)
mdns.register_opts(CONF)
pci_devices.register_opts(CONF)
port_physnet.register_opts(CONF)
processing.register_opts(CONF)
pxe_filter.register_opts(CONF)
service_catalog.register_opts(CONF)
swift.register_opts(CONF)
