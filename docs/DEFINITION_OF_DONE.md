# Definition of Done and No-Vanity Rule

A feature is done only when it is implemented, wired to a reachable entry point, authorized, tested, documented, and verified in the environment relevant to the claim.

The following do not count as completion by themselves:

- a document describing unimplemented behavior
- a visible control without a real handler and backend contract
- an endpoint with no product or operator purpose
- a mocked provider represented as live
- a health response represented as deployment proof
- a local test represented as real-user, accessibility, backup, provider, or target-environment evidence

Every feature change must identify its owner boundary, state transitions, failure UX, retry safety, audit/privacy effect, and verification evidence. Work that only improves appearance or counts without advancing a user or operator outcome is rejected as vanity work.
