# Configuration

The system is built in a way to allow you
to change its configuration at runtime.

All services need to define and expose a schema of their configuration.
This schema is used to build a form in the dashboard that allows you to
change the configuration of the service.

![Configuration form example](assets/configuration.png){ loading=lazy } Configuration form example

Also, all the default implementations of services store their state on disk
on exit, and load it back on startup.
So you can get back to the same state after a restart.
