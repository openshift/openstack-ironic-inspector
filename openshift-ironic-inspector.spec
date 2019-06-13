# Using Python 2 as Python 3 won't work on centos 7 because
# of missing dependencies
%global pyver 2
%global service ironic-inspector
%global modulename ironic_inspector
%{!?upstream_version: %global upstream_version %{version}}

Name:       openshift-ironic-inspector
Summary:    Hardware introspection service for Ironic
Version:    XXX
Release:    1%{?dist}
License:    ASL 2.0
URL:        https://launchpad.net/ironic-inspector

Source0:    ironic-inspector.tar.gz
Source1:    openshift-ironic-inspector.service
Source2:    openshift-ironic-inspector-dnsmasq.service
Source3:    dnsmasq.conf
Source4:    ironic-inspector-rootwrap-sudoers
Source5:    ironic-inspector.logrotate
Source6:    ironic-inspector-dist.conf

BuildArch:  noarch
BuildRequires: openstack-macros
BuildRequires: python%{pyver}-devel
BuildRequires: python%{pyver}-pbr
BuildRequires: python%{pyver}-stestr
BuildRequires: systemd
# All these are required to run tests during check step
BuildRequires: python%{pyver}-mock
BuildRequires: python%{pyver}-alembic
BuildRequires: python%{pyver}-automaton
BuildRequires: python%{pyver}-babel
BuildRequires: python%{pyver}-eventlet
BuildRequires: python%{pyver}-fixtures
BuildRequires: python%{pyver}-futurist
BuildRequires: python%{pyver}-ironicclient
BuildRequires: python%{pyver}-jsonschema
BuildRequires: python%{pyver}-keystoneauth1
BuildRequires: python%{pyver}-keystonemiddleware
BuildRequires: python%{pyver}-netaddr
BuildRequires: python%{pyver}-oslo-concurrency
BuildRequires: python%{pyver}-oslo-config
BuildRequires: python%{pyver}-oslo-context
BuildRequires: python%{pyver}-oslo-db
BuildRequires: python%{pyver}-oslo-i18n
BuildRequires: python%{pyver}-oslo-log
BuildRequires: python%{pyver}-oslo-messaging
BuildRequires: python%{pyver}-oslo-middleware
BuildRequires: python%{pyver}-oslo-policy
BuildRequires: python%{pyver}-oslo-serialization
BuildRequires: python%{pyver}-oslo-utils
BuildRequires: python%{pyver}-oslotest
BuildRequires: python%{pyver}-six
BuildRequires: python%{pyver}-sqlalchemy
BuildRequires: python%{pyver}-stevedore
BuildRequires: python%{pyver}-swiftclient
BuildRequires: python%{pyver}-testscenarios
BuildRequires: python%{pyver}-testresources

Requires: dnsmasq
%{?systemd_requires}

Requires: python%{pyver}-pbr
Requires: python%{pyver}-alembic
Requires: python%{pyver}-automaton
Requires: python%{pyver}-babel
Requires: python%{pyver}-eventlet
Requires: python%{pyver}-futurist
Requires: python%{pyver}-ironicclient >= 2.3.0
Requires: python%{pyver}-jsonschema
Requires: python%{pyver}-keystoneauth1 >= 3.4.0
Requires: python%{pyver}-keystonemiddleware >= 4.17.0
Requires: python%{pyver}-netaddr
Requires: python%{pyver}-oslo-concurrency >= 3.26.0
Requires: python%{pyver}-oslo-config >= 2:5.2.0
Requires: python%{pyver}-oslo-context >= 2.19.2
Requires: python%{pyver}-oslo-db >= 4.27.0
Requires: python%{pyver}-oslo-i18n >= 3.15.3
Requires: python%{pyver}-oslo-log >= 3.36.0
Requires: python%{pyver}-oslo-messaging >= 5.32.0
Requires: python%{pyver}-oslo-middleware >= 3.31.0
Requires: python%{pyver}-oslo-policy >= 1.30.0
Requires: python%{pyver}-oslo-rootwrap >= 5.8.0
Requires: python%{pyver}-oslo-serialization >= 2.18.0
Requires: python%{pyver}-oslo-service >= 1.24.0
Requires: python%{pyver}-oslo-utils >= 3.33.0
Requires: python%{pyver}-six
Requires: python%{pyver}-sqlalchemy
Requires: python%{pyver}-stevedore
Requires: python%{pyver}-swiftclient >= 3.2.0

Requires: python-construct >= 2.8.10
Requires: python-flask
Requires: python-ironic-lib >= 2.5.0
Requires: python-jsonpath-rw
Requires: python-retrying >= 1.2.3
Requires: pytz

BuildRequires: python-construct
BuildRequires: python-flask
BuildRequires: python-ironic-lib
BuildRequires: python-jsonpath-rw
BuildRequires: python-retrying
BuildRequires: pytz

%description
Ironic Inspector is an auxiliary service for discovering hardware properties
for a node managed by Ironic. Hardware introspection or hardware
properties discovery is a process of getting hardware parameters required for
scheduling from a bare metal node, given it’s power management credentials
(e.g. IPMI address, user name and password).

# logs configuration
install -d -m 750 %{buildroot}%{_localstatedir}/log/ironic-inspector
install -d -m 750 %{buildroot}%{_localstatedir}/log/ironic-inspector/ramdisk
install -p -D -m 644 %{SOURCE5} %{buildroot}%{_sysconfdir}/logrotate.d/openshift-ironic-inspector

# install systemd scripts
mkdir -p %{buildroot}%{_unitdir}
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_unitdir}
install -p -D -m 644 %{SOURCE2} %{buildroot}%{_unitdir}

# install sudoers file
mkdir -p %{buildroot}%{_sysconfdir}/sudoers.d
install -p -D -m 440 %{SOURCE4} %{buildroot}%{_sysconfdir}/sudoers.d/ironic-inspector

# generate example configuration files
install -d -m 750 %{buildroot}%{_sysconfdir}/ironic-inspector
export PYTHONPATH=.
oslo-config-generator-%{pyver} --config-file tools/config-generator.conf --output-file %{buildroot}/%{_sysconfdir}/ironic-inspector/inspector.conf
oslopolicy-sample-generator-%{pyver} --config-file tools/policy-generator.conf --output-file %{buildroot}/%{_sysconfdir}/ironic-inspector/policy.json

# configuration contains passwords, thus 640
chmod 0640 %{buildroot}/%{_sysconfdir}/ironic-inspector/inspector.conf
install -p -D -m 640 %{SOURCE6} %{buildroot}/%{_sysconfdir}/ironic-inspector/inspector-dist.conf
install -p -D -m 644 %{SOURCE3} %{buildroot}/%{_sysconfdir}/ironic-inspector/dnsmasq.conf

# rootwrap configuration
mkdir -p %{buildroot}%{_sysconfdir}/ironic-inspector/rootwrap.d
install -p -D -m 640 rootwrap.conf %{buildroot}/%{_sysconfdir}/ironic-inspector/rootwrap.conf
install -p -D -m 640 rootwrap.d/* %{buildroot}/%{_sysconfdir}/ironic-inspector/rootwrap.d/

# shared state directory
mkdir -p %{buildroot}%{_sharedstatedir}/ironic-inspector

# shared state directory for the dnsmasq PXE filter and the dnsmasq service
mkdir -p %{buildroot}%{_sharedstatedir}/ironic-inspector/dhcp-hostsdir

%check
PYTHON=%{pyver_bin} stestr-%{pyver} run --test-path ironic_inspector.test.unit

%files
%doc README.rst
%license LICENSE
%config(noreplace) %attr(-,root,ironic-inspector) %{_sysconfdir}/ironic-inspector
%config(noreplace) %{_sysconfdir}/logrotate.d/openshift-ironic-inspector
%{_sysconfdir}/sudoers.d/ironic-inspector
%{pyver_sitelib}/%{modulename}
%{pyver_sitelib}/%{modulename}-*.egg-info
%exclude %{pyver_sitelib}/%{modulename}/test
%{_bindir}/ironic-inspector
%{_bindir}/ironic-inspector-rootwrap
%{_bindir}/ironic-inspector-dbsync
%{_bindir}/ironic-inspector-migrate-data
%{_unitdir}/openshift-ironic-inspector.service
%{_unitdir}/openshift-ironic-inspector-dnsmasq.service
%attr(-,ironic-inspector,ironic-inspector) %{_sharedstatedir}/ironic-inspector
%attr(-,ironic-inspector,ironic-inspector) %{_sharedstatedir}/ironic-inspector/dhcp-hostsdir
%attr(-,ironic-inspector,ironic-inspector) %{_localstatedir}/log/ironic-inspector
%attr(-,ironic-inspector,ironic-inspector) %{_localstatedir}/log/ironic-inspector/ramdisk/
%doc %{_mandir}/man8/ironic-inspector.8.gz
%exclude %{pyver_sitelib}/%{modulename}_tests.egg-info

%files -n python%{pyver}-%{service}-tests
%license LICENSE
%{pyver_sitelib}/%{modulename}/test

%pre
getent group ironic-inspector >/dev/null || groupadd -r ironic-inspector
getent passwd ironic-inspector >/dev/null || \
    useradd -r -g ironic-inspector -d %{_sharedstatedir}/ironic-inspector -s /sbin/nologin \
-c "OpenShift Ironic Inspector Daemons" ironic-inspector
exit 0

%post
%systemd_post openshift-ironic-inspector.service
%systemd_post openshift-ironic-inspector-dnsmasq.service

%preun
%systemd_preun openshift-ironic-inspector.service
%systemd_preun openshift-ironic-inspector-dnsmasq.service

%postun
%systemd_postun_with_restart openshift-ironic-inspector.service
%systemd_postun_with_restart openshift-ironic-inspector-dnsmasq.service

%changelog
