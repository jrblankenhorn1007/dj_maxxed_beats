# Coordinator assignment (summary)

Implement the complete Copilot onboarding path across CLI discovery, private
SDK setup, runtime configuration refresh, platform launchers, Windows package
wrappers, tests, and user instructions. These pieces share one end-to-end
contract and must be verified together.

The default request is two workers. The Resource Manager reported no spare
agent slots, and splitting the runtime/configuration, package, and user path
would create overlapping assumptions; no child assignment was dispatched.
The coordinator owns this single branch.
