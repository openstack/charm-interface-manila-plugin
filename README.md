# Overview

This interface provides a mechanism for 'plugins' to the the Manila charm to
provide configuration sections/parts to to the Manila charm.

It is intended to be used to enable manila share backends to be configured
independently of the main charm, so that vendors/maintainers can supply their
own backend configuration charms as the project continues.

# Manila usage

This interface is used between the Manila charm (share backend role or all) to
provide the manila service user auth details to backend configuraiton charms,
and to obtain configuration information that needs to be written into 8
No explicit handler is required to consume this interface in charms
that consume this interface.

The interface provides `manila-plugin.connected` and `manila-plugin.available`
states.

## For a Manila backend subordinate charm

A Manila subordinate charm uses this interface to configure the manila
configuration files to 'plugin' its functionality.  e.g. the generic backend
needs authentication information (the manila service user) so that it can
generate the configuration information for nova, neutron and cinder as part of
the backend configuration in manila.conf.

The generic charm then needs to set the configuration that the manila principal
charm will use to write the manila.conf and other files.  i.e. the manila charm
will fold in the data presented into the its configuration information.

## How the conversation 'goes' between the principal (manila) and subordinate

 1. Juju connects the two charms.
 2. When the 'requires' side connects (hook
    `{requires:manila-plugin}-relation-joined` fires), the Manila principal
    charm will receive the state({relation_name}.connected).
 3. When the 'provides' side connect (hook
    `{provides:manila-plugin}-relation-joined` fires) the subordinate charm
    will receive the state({relation_name}.connected).
 4. When the Manila charm has received keystone authentication information it
    will set that on the relation, and on receipt the 'provides' side will set
    the `{relation_name}.available` state.  This allows the providing
    charm (subordinate backend) to use this information.
 5. If the subordinate needs the auth info, then it should block until
    `{relation_name}.available` is available.
 6. The subordinate should present its configuration information on the
    interface, which will be received on the 'requires' side.  This will set
    the `{relation_name}.available`.
 7. If either side changes 'their' data (e.g. the data they set on the
    interface), then the receiving side will set the `{relation_name}.changed`
    state.  IF the consuming charm uses the `...changed` state, it MUST remove
    it as otherwise it will not 'receive' it again.

The important points are:

 - the `...available` state indicates the _first_ time that the data from the
     _other_ side of the interface.
 - the `...changed` state indicates the _next_ and subsequent times that data
     from the _other_ side has changed.  This may not be important to the
     subordinate, but Manila will use this to rewrite the configuration files.
 - If the subordinate consumes the `...changed` state, then it must remove it
     at the end of processing, so that it can 'see' it the next time it is set.


# metadata

To consume this interface in your charm or layer, add the following to
`layer.yaml`:

```yaml
includes: ['interface:manila-plugin']
```

and add a provides interface of type `manila` to your charm or layers
`metadata.yaml`:

```yaml
provides:
  manila:
    interface: manila-plugin
    scope: container
```

Please see the example 'Manila generic backend' charm for an example of how to
author a manila backend configuration charm.

# Bugs

Please report bugs on
[Launchpad](https://bugs.launchpad.net/openstack-charms/+filebug).

For development questions please refer to the OpenStack
[Charm Guide](https://github.com/openstack/charm-guide).
