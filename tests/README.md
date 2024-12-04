# Tests for the `xgit` xontrib

The tests are divided into two main groups:

* [pure/](pure/README.md): These tests modify no state, require no cleanup, and can be run in parallel.
* [impure/](impure/README.md): These tests modify various state, require cleanup, and cannot be run in parallel.

A locking fixture is applied at the package scope for pure, and function scope for impure tests, to ensure impure tests run isolated from pure and from each other.
